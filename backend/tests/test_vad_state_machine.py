"""
Unit tests for VAD finite state machine and state model transitions.
"""

from app.models.vad_state import VADSessionState, VADState


def test_vad_session_state_initialization():
    """
    Tests initial VADSessionState properties and defaults.
    """
    state = VADSessionState()
    assert state.state == VADState.IDLE
    assert state.speech_started is False
    assert state.speech_duration_ms == 0.0
    assert state.silence_duration_ms == 0.0
    assert state.utterance_counter == 0
    assert state.ready_for_transcription is False


def test_vad_state_transitions():
    """
    Tests deterministic VADState transition helper and side-effects.
    """
    state = VADSessionState()

    # Transition to VOICE_STARTED
    state.transition_to(VADState.VOICE_STARTED)
    assert state.state == VADState.VOICE_STARTED

    # Transition to VOICE_ACTIVE
    state.transition_to(VADState.VOICE_ACTIVE)
    assert state.state == VADState.VOICE_ACTIVE

    # Transition to SILENCE_DETECTED
    state.transition_to(VADState.SILENCE_DETECTED)
    assert state.state == VADState.SILENCE_DETECTED

    # Transition to UTTERANCE_COMPLETE
    state.transition_to(VADState.UTTERANCE_COMPLETE)
    assert state.state == VADState.UTTERANCE_COMPLETE
    assert state.ready_for_transcription is True
    assert state.utterance_counter == 1
    assert state.speech_started is False

    # Mark utterance consumed
    state.mark_utterance_consumed()
    assert state.state == VADState.IDLE
    assert state.ready_for_transcription is False
    assert state.speech_duration_ms == 0.0
    assert state.silence_duration_ms == 0.0
    # Utterance counter persists
    assert state.utterance_counter == 1


def test_vad_state_reset():
    """
    Tests reset_session_vad helper method.
    """
    state = VADSessionState()
    state.transition_to(VADState.VOICE_ACTIVE)
    state.speech_duration_ms = 1200.0
    state.silence_duration_ms = 400.0

    state.reset_session_vad()
    assert state.state == VADState.IDLE
    assert state.speech_duration_ms == 0.0
    assert state.silence_duration_ms == 0.0
    assert state.ready_for_transcription is False
