"""
Unit tests for VADService signal energy calculations and frame processing logic.
"""

import math
import struct

from app.models.vad_state import VADEvent, VADSessionState, VADState
from app.services.vad_service import VADService, vad_service


def create_pcm_silence(duration_ms: int = 50, sample_rate: int = 16000) -> bytes:
    """Helper creating raw PCM silence frame (0 amplitude)."""
    sample_count = int(sample_rate * (duration_ms / 1000.0))
    return b"\x00\x00" * sample_count


def create_pcm_sine_voice(duration_ms: int = 50, sample_rate: int = 16000, frequency: int = 440, amplitude: int = 12000) -> bytes:
    """Helper creating synthetic PCM audio frame simulating active voice signal."""
    sample_count = int(sample_rate * (duration_ms / 1000.0))
    samples = [int(amplitude * math.sin(2 * math.pi * frequency * i / sample_rate)) for i in range(sample_count)]
    return struct.pack(f"<{sample_count}h", *samples)


def test_vad_service_rms_calculation():
    """
    Tests PCM RMS signal energy calculation on silence vs synthetic speech audio.
    """
    silence = create_pcm_silence(50)
    voice = create_pcm_sine_voice(50)

    rms_silence = vad_service.calculate_pcm_rms(silence)
    rms_voice = vad_service.calculate_pcm_rms(voice)

    assert rms_silence == 0.0
    assert rms_voice > 0.1  # Significant energy for 12000 amplitude

    assert vad_service.is_voice_detected(silence) is False
    assert vad_service.is_voice_detected(voice) is True


def test_calculate_frame_duration_ms():
    """
    Tests frame duration calculation math (16kHz 16-bit mono PCM).
    """
    # 32,000 bytes = 1.0 second = 1000 ms
    frame_1s = b"\x00" * 32000
    duration_ms = vad_service.calculate_frame_duration_ms(frame_1s)
    assert duration_ms == 1000.0

    # 1600 bytes = 50 ms
    frame_50ms = b"\x00" * 1600
    assert vad_service.calculate_frame_duration_ms(frame_50ms) == 50.0


def test_process_audio_frame_silence_only():
    """
    Tests processing continuous silence frames: state remains IDLE, no false positive triggers.
    """
    service = VADService()
    state = VADSessionState()
    silence_frame = create_pcm_silence(50)  # 50ms silence

    for _ in range(10):  # 500ms of silence
        current_state, event, meta = service.process_audio_frame(silence_frame, state, "test_session")
        assert current_state == VADState.IDLE
        assert event is None
        assert meta["has_voice"] is False
        assert state.ready_for_transcription is False


def test_process_audio_frame_speech_only():
    """
    Tests processing continuous speech frames: IDLE -> VOICE_STARTED -> VOICE_ACTIVE.
    """
    service = VADService()
    state = VADSessionState()
    voice_frame = create_pcm_sine_voice(50)  # 50ms voice frame

    # First 4 frames = 200ms < 250ms min threshold -> IDLE
    for _ in range(4):
        c_state, event, meta = service.process_audio_frame(voice_frame, state, "test_session")
        assert meta["has_voice"] is True

    # 5th frame = 250ms threshold reached -> VOICE_STARTED
    c_state, event, meta = service.process_audio_frame(voice_frame, state, "test_session")
    assert c_state == VADState.VOICE_STARTED
    assert event == VADEvent.VOICE_STARTED

    # 6th frame -> VOICE_ACTIVE
    c_state, event, meta = service.process_audio_frame(voice_frame, state, "test_session")
    assert c_state == VADState.VOICE_ACTIVE
    assert event == VADEvent.VOICE_CONTINUING
