# MailMind AI - Voice Engine Backend (Phase 1, Milestone 3)

Production-ready FastAPI backend architecture, WebSocket communication, and **Audio Streaming & Memory Buffering Layer** for **MailMind AI** (Voice-First AI Email Executive Assistant).

---

## 🏛️ Architectural Overview & Design Principles

### 1. Clean Architecture Layer Separation
The application is structured into decoupled layers with strict dependency control:
- **Core / Config Layer (`app/core/`)**: Configuration (`config.py`), Structured JSON Logging (`logging.py`), Exception Management (`exceptions.py`).
- **Models Layer (`app/models/`)**: Domain models including `VoiceSession` (`voice_session.py`) and `AudioBuffer` (`audio_buffer.py`).
- **Service Layer (`app/services/`)**: Connection management (`connection_manager.py`), Audio stream ingestion (`audio_stream_service.py`), and voice engine placeholders.
- **API Transport Layer (`app/api/`)**: HTTP endpoints and WebSocket streaming routes (`v1/endpoints/voice.py`).
- **Schemas DTO Layer (`app/schemas/`)**: Pydantic response validation models.

### 2. Audio Streaming & Memory Buffering (Milestone 3)
WebSocket endpoints (`/ws/voice` and `/api/v1/ws/voice`) support multiplexed communications:
- **JSON Control Frames**: Handshake welcome messages, ping/pong heartbeats, and buffer clearing commands (`clear_buffer`).
- **Binary Audio Packets**: Raw binary audio chunks (`bytes`) received directly from client micro-streams.
- **AudioBuffer**: Per-session in-memory byte buffer storing accumulated audio frames, computing frame counts, total byte metrics, and audio duration estimates.
- **AudioStreamService**: Ingests, validates, logs, and acknowledges raw audio packets without CPU-heavy media decoding or AI inference.

---

## 🎧 Deep Dive: Audio Streaming & Buffering Architecture

### Why Streaming Audio is Necessary
Conversational AI voice assistants (such as ChatGPT Voice) require ultra-low end-to-end latency (<1 second). Sending complete pre-recorded audio files over traditional HTTP POST endpoints creates unacceptable delay because the user must stop speaking and wait for file upload completion. 

By streaming binary audio chunks continuously over persistent WebSocket connections as small frame packets, the backend receives audio in near real time as the user speaks.

### Why Memory Buffering is Required
Audio packets arrive over WebSockets as small, fragmented network frames (e.g. 50ms – 200ms audio chunks). Downstream Speech-To-Text (STT) models and Voice Activity Detection (VAD) engines cannot accurately classify speech or transcribe single fragmented audio frames in isolation; they require contiguous audio segments (utterances). 

The `AudioBuffer` serves as an in-memory staging area where incoming binary chunks accumulate safely until complete speech boundaries are detected.

### Why Each Session Owns an Independent AudioBuffer
Every active WebSocket client owns an isolated `AudioBuffer` instance attached directly to its `VoiceSession` model (`session.audio_buffer`). 
This guarantees:
1. **Strict Session Isolation**: Prevents audio chunk leakage across concurrent users.
2. **Thread Safety**: Eliminates race conditions in asynchronous event loops.
3. **Memory Lifecycle Management**: When a client disconnects, its dedicated `AudioBuffer` is instantly cleared, freeing memory.

### How Buffering Prepares for Voice Activity Detection (Milestone 4)
In Milestone 4, `VADService` will inspect the accumulating audio chunks inside `AudioBuffer` in real time. 
When VAD detects silence following human speech (speech end boundary), the pipeline will slice the accumulated raw PCM audio bytes from `AudioBuffer.export_raw()`, pass the complete utterance to `STTService` for transcription, and reset the buffer for the next conversation turn.

---

## 🎙️ End-to-End Voice Pipeline Architecture

```
Client (Web / Mobile / Desktop Microphone)
    │
    │ (Binary Audio Chunks over WebSocket /ws/voice)
    ▼
[ /ws/voice Endpoint Handler ]
    │
    ├──> 1. Ingest & Log Binary Packet ───────> [ AudioStreamService ]
    │                                                    │
    │                                                    ▼
    │                                       [ Session AudioBuffer ]
    │                                        (Stores raw byte chunks)
    │
    ├──> 2. Real-time Silence / Speech Check ─> [ VADService ] (Milestone 4)
    │        └── If speech boundary ends:
    │
    ├──> 3. Transcribe Speech to Text ────────> [ STTService ]
    │        └── Yields user transcript string
    │
    ├──> 4. Send Transcript & History ────────> [ LLMService ]
    │        └── Streams text tokens asynchronously
    │
    ├──> 5. Synthesize Tokens to Speech ─────> [ TTSService ]
    │        └── Streams audio bytes back to client
    │
    ▼ (Binary Audio Response Chunks via WebSocket)
Client Plays Response Audio
```

---

## 📂 Directory Responsibilities Breakdown

```
backend/
├── app/
│   ├── __init__.py                 # Application package metadata
│   ├── main.py                     # FastAPI application factory, lifespan, CORS, and exception handler setup
│   ├── core/                       # Cross-cutting infrastructure concerns
│   │   ├── config.py               # Settings management via Pydantic BaseSettings
│   │   ├── logging.py              # Structured JSON / Text loggers configuration
│   │   └── exceptions.py           # Domain exception classes & global error handlers
│   ├── models/                     # Data & Domain Models Layer
│   │   ├── voice_session.py        # VoiceSession model tracking connection status & duration
│   │   └── audio_buffer.py         # AudioBuffer model storing raw session audio bytes & metrics
│   ├── api/                        # HTTP Routing & WebSocket Controller Layer
│   │   ├── router.py               # Root API router combining health & WebSocket endpoints
│   │   └── v1/
│   │       ├── router.py           # V1 route aggregator
│   │       └── endpoints/
│   │           ├── health.py       # GET /health endpoints
│   │           └── voice.py        # WebSocket /ws/voice multiplexed binary/JSON streaming endpoint
│   ├── services/                   # Business logic & Voice AI engine services
│   │   ├── base.py                 # Abstract Base Class defining service lifecycle interface (BaseService)
│   │   ├── connection_manager.py   # Asynchronous WebSocket connection lifecycle manager
│   │   ├── audio_stream_service.py # Audio stream packet ingestion, validation, and frame logging service
│   │   ├── audio_service.py        # Audio processing & format conversion placeholder
│   │   ├── vad_service.py          # Voice Activity Detection (silence detection) placeholder
│   │   ├── stt_service.py          # Speech-to-Text transcription placeholder
│   │   ├── llm_service.py          # Large Language Model orchestration & token streaming placeholder
│   │   ├── tts_service.py          # Text-to-Speech audio synthesis placeholder
│   │   └── conversation_service.py # Pipeline coordinator orchestrating voice interaction loop
│   └── schemas/                    # Pydantic DTO validation models
│       └── health.py               # Health check request/response schemas
├── tests/                          # Automated testing suite
│   ├── conftest.py                 # Pytest fixtures and FastAPI TestClient setup
│   ├── test_health.py              # Health check endpoint unit tests
│   ├── test_websocket.py           # WebSocket endpoint & ConnectionManager unit tests
│   ├── test_multiple_connections.py# Multiple concurrent WebSocket connection unit tests
│   └── test_audio_stream.py        # AudioBuffer & binary streaming unit tests
├── .env.example                    # Template environment variables
├── .env                            # Local development configuration file
├── pytest.ini                      # Pytest runner configuration
├── requirements.txt                # Production & development dependencies
└── README.md                       # Architecture documentation (this file)
```

---

## 🧪 Running Automated Tests

Run the full automated test suite (health, websockets, connection manager, audio buffers):
```bash
cd backend
python -m pytest
```
