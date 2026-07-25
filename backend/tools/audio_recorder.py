"""
MailMind AI Developer CLI Voice Client - Live Microphone Audio Recorder.

Architectural Decision Rationale:
---------------------------------
1. Live Hardware Capture: Uses `sounddevice.InputStream` to capture low-latency microphone audio.
2. In-Memory PCM Streaming: Converts NumPy float32/int16 frames directly to 16-bit 16000Hz mono raw PCM bytes
   and pushes them into an `asyncio.Queue`. Performs zero disk I/O or temporary file creation.
3. Thread-Safe Loop Bridge: Pushes audio buffers from sounddevice's C audio thread to asyncio event loop.
"""

import asyncio
from typing import Any

import numpy as np
import sounddevice as sd

from tools.config import VoiceClientConfig


class AudioRecorder:
    """
    Captures microphone audio live and streams 16-bit mono 16000Hz PCM byte chunks into an asyncio queue.
    """

    def __init__(self, config: VoiceClientConfig) -> None:
        self.config: VoiceClientConfig = config
        self.queue: asyncio.Queue[bytes] = asyncio.Queue()
        self._stream: sd.InputStream | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._is_recording: bool = False

    def _audio_callback(
        self, indata: np.ndarray, frames: int, time_info: Any, status: sd.CallbackFlags
    ) -> None:
        """
        Hardware C-thread callback function executed per audio chunk.
        Converts NumPy array to 16-bit PCM binary bytes and schedules insertion into asyncio queue.
        """
        if status:
            pass  # Suppress non-critical buffer overflow/underflow warnings in CLI

        if not self._is_recording or self._loop is None:
            return

        # Convert float32 [-1.0, 1.0] to int16 [-32768, 32767] if input format is float32
        if indata.dtype == np.float32:
            pcm_data = (indata * 32767.0).astype(np.int16)
        else:
            pcm_data = indata.astype(np.int16)

        pcm_bytes = pcm_data.tobytes()

        # Thread-safe queue insertion onto asyncio event loop
        self._loop.call_soon_threadsafe(self.queue.put_nowait, pcm_bytes)

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        """
        Starts microphone capture InputStream.

        :param loop: Active asyncio event loop.
        """
        if self._is_recording:
            return

        self._loop = loop
        self._is_recording = True

        self._stream = sd.InputStream(
            samplerate=self.config.sample_rate,
            channels=self.config.channels,
            dtype="int16",
            blocksize=self.config.chunk_size_samples,
            device=self.config.device_index,
            callback=self._audio_callback,
        )
        self._stream.start()

    def stop(self) -> None:
        """
        Stops microphone capture InputStream.
        """
        self._is_recording = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except (OSError, sd.PortAudioError):
                pass
            self._stream = None

    async def get_frame(self) -> bytes:
        """
        Asynchronously retrieves next raw 16-bit PCM binary frame from the recording queue.
        """
        return await self.queue.get()
