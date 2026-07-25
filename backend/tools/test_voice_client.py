"""
MailMind AI - Developer CLI Voice Client Entrypoint.

Usage:
------
python tools/test_voice_client.py [--url ws://localhost:8000/ws/voice]

Architectural Decision Rationale:
---------------------------------
1. Modular Dependency Injection: Assembles AudioRecorder, TerminalUI, MessageHandler, and WebSocketManager.
2. Clean Signal Handling: Intercepts Ctrl+C (KeyboardInterrupt) and closes audio input streams and sockets.
"""

import argparse
import asyncio
import os
import sys

# Ensure backend root directory is in sys.path
backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

from tools.audio_recorder import AudioRecorder
from tools.config import VoiceClientConfig
from tools.message_handler import MessageHandler
from tools.terminal_ui import TerminalUI
from tools.websocket_manager import WebSocketManager


class VoiceClient:
    """
    Developer Voice Client top-level orchestrator.
    """

    def __init__(self, config: VoiceClientConfig) -> None:
        self.config: VoiceClientConfig = config
        self.ui: TerminalUI = TerminalUI()
        self.message_handler: MessageHandler = MessageHandler(ui=self.ui)
        self.recorder: AudioRecorder = AudioRecorder(config=self.config)
        self.ws_manager: WebSocketManager = WebSocketManager(
            config=self.config,
            recorder=self.recorder,
            message_handler=self.message_handler,
            ui=self.ui,
        )

    async def start(self) -> None:
        """
        Starts the CLI Voice Client application.
        """
        self.ui.print_header(
            server_url=self.config.server_url,
            sample_rate=self.config.sample_rate,
        )

        try:
            await self.ws_manager.start()
        except (KeyboardInterrupt, asyncio.CancelledError):
            self.stop()

    def stop(self) -> None:
        """
        Stops connection and recording cleanly.
        """
        self.ws_manager.stop()
        self.ui.print_status("CLOSED", message="Voice Client stopped.")


def parse_args() -> argparse.Namespace:
    """
    Parses CLI flags.
    """
    parser = argparse.ArgumentParser(
        description="MailMind AI Developer CLI Voice Client"
    )
    parser.add_argument(
        "--url",
        type=str,
        default="ws://localhost:8000/ws/voice",
        help="Target WebSocket endpoint URL (default: ws://localhost:8000/ws/voice)",
    )
    parser.add_argument(
        "--rate",
        type=int,
        default=16000,
        help="Audio sample rate in Hz (default: 16000)",
    )
    parser.add_argument(
        "--device",
        type=int,
        default=None,
        help="Optional microphone device index",
    )
    return parser.parse_args()


def main() -> None:
    """
    CLI Entrypoint.
    """
    args = parse_args()
    config = VoiceClientConfig(
        server_url=args.url,
        sample_rate=args.rate,
        device_index=args.device,
    )
    client = VoiceClient(config=config)

    try:
        asyncio.run(client.start())
    except KeyboardInterrupt:
        client.stop()
        sys.exit(0)


if __name__ == "__main__":
    main()
