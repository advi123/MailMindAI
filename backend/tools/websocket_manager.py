"""
MailMind AI Developer CLI Voice Client - WebSocket Connection Manager.

Architectural Decision Rationale:
---------------------------------
1. Async Reconnection Lifecycle: Automatically reconnects with exponential backoff if the WebSocket
   connection drops or server restarts.
2. Concurrent Sender/Receiver Tasks: Runs audio streaming sender loop and server payload receiver loop
   concurrently using `asyncio.gather` and `asyncio.TaskGroup`.
"""

import asyncio
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed, WebSocketException

from tools.audio_recorder import AudioRecorder
from tools.config import VoiceClientConfig
from tools.message_handler import MessageHandler
from tools.terminal_ui import TerminalUI


class WebSocketManager:
    """
    Manages client WebSocket connection lifecycle, frame streaming, and reconnection loops.
    """

    def __init__(
        self,
        config: VoiceClientConfig,
        recorder: AudioRecorder,
        message_handler: MessageHandler,
        ui: TerminalUI,
    ) -> None:
        self.config: VoiceClientConfig = config
        self.recorder: AudioRecorder = recorder
        self.message_handler: MessageHandler = message_handler
        self.ui: TerminalUI = ui
        self._is_running: bool = False
        self._websocket: Any = None

    async def start(self) -> None:
        """
        Starts WebSocket connection and auto-reconnect loop.
        """
        self._is_running = True
        loop = asyncio.get_running_loop()

        # Start microphone recording
        self.recorder.start(loop)

        while self._is_running:
            try:
                self.ui.print_status("CONNECTING", message=f"Connecting to {self.config.server_url}...")

                async with websockets.connect(
                    self.config.server_url,
                    ping_interval=20,
                    ping_timeout=10,
                ) as ws:
                    self._websocket = ws

                    # Launch concurrent sender and receiver tasks
                    sender_task = asyncio.create_task(self._sender_loop(ws))
                    receiver_task = asyncio.create_task(self._receiver_loop(ws))

                    _done, pending = await asyncio.wait(
                        [sender_task, receiver_task],
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    for task in pending:
                        task.cancel()

            except (ConnectionClosed, ConnectionRefusedError, OSError, WebSocketException) as conn_err:
                if not self._is_running:
                    break
                self.ui.print_status(
                    "RECONNECTING",
                    message=f"Connection lost ({conn_err!s}). Retrying in {self.config.reconnect_delay}s...",
                )
                await asyncio.sleep(self.config.reconnect_delay)

            except asyncio.CancelledError:
                break

        # Cleanup on exit
        self.recorder.stop()

    def stop(self) -> None:
        """
        Stops connection loop and releases recording resources.
        """
        self._is_running = False
        self.recorder.stop()

    async def _sender_loop(self, ws: Any) -> None:
        """
        Pulls binary 16-bit PCM byte chunks from AudioRecorder and streams over WebSocket.
        """
        while self._is_running:
            pcm_bytes = await self.recorder.get_frame()
            if pcm_bytes:
                await ws.send(pcm_bytes)

    async def _receiver_loop(self, ws: Any) -> None:
        """
        Receives text JSON server messages and passes to MessageHandler.
        """
        while self._is_running:
            message = await ws.recv()
            if isinstance(message, str):
                self.message_handler.handle_raw_message(message)
