"""
MailMind AI - Voice WebSocket Endpoint.

Architectural Decision Rationale & Audio Pipeline Integration:
----------------------------------------------------------------------
1. Multiplexed Control & Streaming Data Channels: Over a single persistent WebSocket connection (`/ws/voice`),
   the endpoint automatically differentiates between:
   - Text JSON Control Frames (ping/pong, state events, buffer/VAD/conversation clearing)
   - Binary Audio Bytes Streams (raw PCM audio frame chunks)
2. Integrated Voice Pipeline (Milestone 6 Conversation Intelligence):
   Binary Bytes -> AudioStreamService -> Session AudioBuffer
                                      -> VADService (Updates VADState)
   When VAD detects an Utterance Complete boundary:
   - Exports accumulated raw PCM bytes from `session.audio_buffer`
   - Calls `stt_service.transcribe(pcm_bytes)` (Orchestrates injected STT Provider strategy)
   - On STT transcript -> Calls `conversation_service.process_transcript(session_id, transcript_text)`
   - Emits WebSocket Event:
     Success -> {"type": "conversation_ready", "session_id": ..., "turn": ..., "history_length": ..., "latest_message": ..., "prompt": ...}
     Failure -> {"type": "transcription_failed", "session_id": ..., "reason": ...}
   - Resets `session.audio_buffer` and `session.vad_state` for the next conversation turn.
   - Resilient: The WebSocket connection is NEVER closed on transcription failures.
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import settings
from app.core.exceptions import AppValidationError
from app.core.logging import get_logger
from app.services.audio_stream_service import audio_stream_service
from app.services.connection_manager import connection_manager
from app.services.conversation_service import conversation_service
from app.services.stt_service import stt_service
from app.services.vad_service import vad_service

logger = get_logger("api.endpoints.voice")

router = APIRouter()


@router.websocket("/ws/voice")
async def voice_websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket endpoint supporting real-time binary audio streaming, VAD utterance boundary detection,
    Speech-To-Text (STT) transcription, and Conversation Intelligence prompt assembly.

    Lifecycle:
    1. Connection Handshake: Accepts socket connection and assigns a unique `session_id`.
    2. Connection Established Event: Emits welcome JSON payload containing `session_id`.
    3. Stream Receive Loop: Receives text JSON control messages or raw binary audio frames.
    4. Utterance Processing: On VAD completion, invokes STT service, passes transcript to Conversation Engine,
       emits `conversation_ready` JSON event, and resets session audio buffer.
    5. Disconnection Cleanup: Closes connection cleanly, clears audio buffer, and deletes conversation memory session.
    """
    session = await connection_manager.connect(websocket)
    session_id = session.session_id

    try:
        # Step 1: Send initial connection_established acknowledgment payload
        welcome_payload = {
            "type": "connection_established",
            "session_id": session_id,
            "status": "connected",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "message": "Connected to MailMind AI Voice Engine",
        }
        await websocket.send_json(welcome_payload)

        # Step 2: Main WebSocket multiplexed receive loop (JSON Control + Binary Audio)
        while True:
            message = await websocket.receive()

            # Handle Disconnect Signal
            if message.get("type") == "websocket.disconnect":
                break

            # Handle Text / JSON Control Frames
            if "text" in message and message["text"] is not None:
                raw_text = message["text"]
                try:
                    payload = json.loads(raw_text)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid non-JSON frame received from session ID {session_id}")
                    error_response = {
                        "type": "error",
                        "code": "INVALID_JSON",
                        "message": "Text frame payload must be a valid JSON object.",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    await websocket.send_json(error_response)
                    continue

                event_type = payload.get("type", "").lower()

                # Handle Heartbeat / Ping Action
                if event_type in ["ping", "heartbeat"]:
                    ack_response = await connection_manager.handle_heartbeat(session_id)
                    await websocket.send_json(ack_response)

                # Handle Text Audio Frame Placeholder (For backward compatibility with text JSON clients)
                elif event_type == "audio_frame":
                    frame_ack = {
                        "type": "audio_frame_ack",
                        "session_id": session_id,
                        "status": "received",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    await websocket.send_json(frame_ack)

                # Handle Clear Session Audio Buffer Action
                elif event_type == "clear_buffer":
                    session.audio_buffer.clear()
                    vad_service.reset(session.vad_state)
                    logger.info(f"AudioBuffer and VADState explicitly cleared for session ID {session_id}")
                    await websocket.send_json({
                        "type": "buffer_cleared",
                        "session_id": session_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                # Handle Reset VAD & Conversation Memory State Action
                elif event_type == "reset_conversation":
                    conversation_service.memory_service.reset_session(session_id)
                    session.audio_buffer.clear()
                    vad_service.reset(session.vad_state)
                    logger.info(f"Conversation memory and VADState reset for session ID {session_id}")
                    await websocket.send_json({
                        "type": "conversation_reset",
                        "session_id": session_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                # Handle Reset VAD State Action
                elif event_type == "reset_vad":
                    vad_service.reset(session.vad_state)
                    logger.info(f"VADState explicitly reset for session ID {session_id}")
                    await websocket.send_json({
                        "type": "vad_reset",
                        "session_id": session_id,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })

                else:
                    logger.warning(
                        f"Unknown text event type '{event_type}' received from session ID {session_id}"
                    )
                    unknown_response = {
                        "type": "error",
                        "code": "UNKNOWN_EVENT_TYPE",
                        "message": f"Event type '{event_type}' is not supported.",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    await websocket.send_json(unknown_response)

            # Handle Binary Audio Frames
            elif "bytes" in message and message["bytes"] is not None:
                binary_bytes = message["bytes"]
                try:
                    # 1. Ingest and buffer audio packet
                    ack_payload = audio_stream_service.process_audio_frame(
                        session_id=session_id,
                        frame_bytes=binary_bytes,
                        session_buffer=session.audio_buffer,
                    )

                    # 2. Process audio frame through VAD Service
                    _, _, vad_meta = vad_service.process_audio_frame(
                        frame_bytes=binary_bytes,
                        vad_state=session.vad_state,
                        session_id=session_id,
                    )

                    # Attach VAD metadata to frame ACK response
                    ack_payload["vad"] = vad_meta
                    await websocket.send_json(ack_payload)

                    # 3. Check if an utterance is complete and ready for Speech-To-Text & Conversation Processing
                    if vad_service.has_utterance_completed(session.vad_state):
                        pcm_bytes = session.audio_buffer.export_raw()
                        utterance_idx = session.vad_state.utterance_counter

                        logger.info(
                            f"Utterance Completed -> Initiating STT & Conversation Processing | "
                            f"Session ID: {session_id} | Utterance #: {utterance_idx} | PCM Bytes: {len(pcm_bytes)}"
                        )

                        try:
                            # Step 3a: Invoke Speech-To-Text Orchestrator Service
                            transcription_result = await stt_service.transcribe(
                                audio_bytes=pcm_bytes,
                                language=settings.STT_LANGUAGE,
                            )

                            if transcription_result.get("success", False):
                                transcript_text = transcription_result["text"]

                                # Step 3b: Invoke Conversation Intelligence Engine
                                conv_result = await conversation_service.process_transcript(
                                    session_id=session_id,
                                    transcript_text=transcript_text,
                                    language=settings.STT_LANGUAGE,
                                )

                                # NOTE: The prompt field is included in conversation_ready payload for development/testing
                                # visibility. Production builds should omit or sanitize raw prompt strings before deployment.
                                conversation_ready_payload = {
                                    "type": "conversation_ready",
                                    "session_id": session_id,
                                    "turn": conv_result["turn_number"],
                                    "history_length": conv_result["history_length"],
                                    "latest_message": conv_result["latest_user_message"],
                                    "prompt": conv_result["prompt"],
                                    "timestamp": conv_result["timestamp"],
                                }

                                logger.info(
                                    f"Conversation Ready Emitted | Session ID: {session_id} | "
                                    f"Turn #: {conv_result['turn_number']} | History: {conv_result['history_length']} turns | "
                                    f"Latest Msg: '{conv_result['latest_user_message']}'"
                                )
                                await websocket.send_json(conversation_ready_payload)

                            else:
                                logger.warning(
                                    f"Transcription Provider Failure Payload | Session ID: {session_id} | "
                                    f"Error: {transcription_result.get('error')}"
                                )
                                failure_payload = {
                                    "type": "transcription_failed",
                                    "session_id": session_id,
                                    "utterance_index": utterance_idx,
                                    "reason": transcription_result.get("error", "Unknown transcription error"),
                                    "timestamp": datetime.now(timezone.utc).isoformat(),
                                }
                                await websocket.send_json(failure_payload)

                        except Exception as stt_err:
                            logger.exception(
                                f"Unexpected Voice Pipeline Failure | Session ID: {session_id}"
                            )
                            failure_payload = {
                                "type": "transcription_failed",
                                "session_id": session_id,
                                "utterance_index": utterance_idx,
                                "reason": str(stt_err),
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                            }
                            await websocket.send_json(failure_payload)

                        finally:
                            # Reset AudioBuffer and VAD state for the next utterance turn
                            session.audio_buffer.clear()
                            session.vad_state.mark_utterance_consumed()

                except AppValidationError as val_err:
                    logger.warning(
                        f"Audio frame validation error for session ID {session_id}: {val_err.message}"
                    )
                    err_payload = {
                        "type": "error",
                        "code": "AUDIO_BUFFER_ERROR",
                        "message": val_err.message,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    await websocket.send_json(err_payload)

                except Exception:
                    logger.exception(
                        f"Error processing binary frame for session ID {session_id}"
                    )
                    err_payload = {
                        "type": "error",
                        "code": "FRAME_PROCESSING_ERROR",
                        "message": "Internal error processing audio frame.",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                    await websocket.send_json(err_payload)

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected cleanly | Session ID: {session_id}")
    except Exception:
        logger.exception(
            f"Unexpected WebSocket error for session ID {session_id}"
        )
    finally:
        # Step 4: Clean up connection registry and delete conversation memory session
        conversation_service.memory_service.delete_session(session_id)
        await connection_manager.disconnect(session_id)
