"""
MailMind AI - Voice WebSocket Endpoint.

Architectural Decision Rationale & Future Audio Pipeline Integration:
----------------------------------------------------------------------
1. Multiplexed Control & Streaming Data Channels: Over a single persistent WebSocket connection (`/ws/voice`),
   the endpoint automatically differentiates between:
   - Text JSON Control Frames (ping/pong, state events, buffer/VAD clearing)
   - Binary Audio Bytes Streams (raw PCM / WebM audio frame chunks)
2. Integrated Voice Activity Detection (VAD) Flow:
   Binary Bytes -> AudioStreamService -> Session AudioBuffer
                                      -> VADService (Updates VADState)
   When VAD detects an Utterance Complete boundary:
   Emits JSON Event: {"type": "utterance_ready", "duration": ..., "bytes": ..., "session_id": ...}
   Note: The AudioBuffer is NOT cleared, preserving raw bytes for downstream STT in Milestone 5.
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.exceptions import AppValidationError
from app.core.logging import get_logger
from app.services.audio_stream_service import audio_stream_service
from app.services.connection_manager import connection_manager
from app.services.vad_service import vad_service

logger = get_logger("api.endpoints.voice")

router = APIRouter()


@router.websocket("/ws/voice")
async def voice_websocket_endpoint(websocket: WebSocket) -> None:
    """
    WebSocket endpoint supporting real-time binary audio streaming, VAD utterance boundary detection,
    and JSON control frames.

    Lifecycle:
    1. Connection Handshake: Accepts socket connection and assigns a unique `session_id`.
    2. Connection Established Event: Emits welcome JSON payload containing `session_id`.
    3. Stream Receive Loop: Receives text JSON messages or raw binary audio frames.
    4. Disconnection Cleanup: Closes session cleanly and clears session memory buffer & VAD state.
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

                    # 3. Check if an utterance is complete and ready for transcription
                    if vad_service.has_utterance_completed(session.vad_state):
                        utterance_ready_payload = {
                            "type": "utterance_ready",
                            "session_id": session_id,
                            "utterance_index": session.vad_state.utterance_counter,
                            "duration": round(session.audio_buffer.duration_estimate(), 2),
                            "bytes": session.audio_buffer.total_bytes,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        logger.info(
                            f"Utterance Ready Notification | Session ID: {session_id} | "
                            f"Utterance #: {session.vad_state.utterance_counter} | "
                            f"Duration: {utterance_ready_payload['duration']}s | "
                            f"Bytes: {session.audio_buffer.total_bytes}"
                        )
                        await websocket.send_json(utterance_ready_payload)

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
        # Step 3: Ensure session cleanup, clearing audio buffer and logging active duration
        await connection_manager.disconnect(session_id)
