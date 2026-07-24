# MailMind AI - Voice Engine Backend (Phase 1, Milestone 4)

Production-ready FastAPI backend architecture, WebSocket communication, Audio Streaming & Buffering, and **Voice Activity Detection (VAD) Engine** for **MailMind AI** (Voice-First AI Email Executive Assistant).

---

## 🏛️ Architectural Overview & Design Principles

### 1. Clean Architecture Layer Separation
The application is structured into decoupled layers with strict dependency control:
- **Core / Config Layer (`app/core/`)**: Configuration (`config.py`), Structured JSON Logging (`logging.py`), Exception Management (`exceptions.py`).
- **Models Layer (`app/models/`)**: Domain models including `VoiceSession` (`voice_session.py`), `AudioBuffer` (`audio_buffer.py`), and `VADSessionState` (`vad_state.py`).
- **Service Layer (`app/services/`)**: Connection management (`connection_manager.py`), Audio stream ingestion (`audio_stream_service.py`), VAD Engine (`vad_service.py`), and voice engine placeholders.
- **API Transport Layer (`app/api/`)**: HTTP endpoints and WebSocket streaming routes (`v1/endpoints/voice.py`).
- **Schemas DTO Layer (`app/schemas/`)**: Pydantic response validation models.

### 2. Voice Activity Detection (VAD) Engine (Milestone 4)
WebSocket streaming endpoints (`/ws/voice` and `/api/v1/ws/voice`) run real-time signal energy analysis on incoming PCM frames:
- **Root Mean Square (RMS) Signal Analysis**: Calculates sample amplitude energy on 16-bit PCM binary audio frames normalized against 32768.0.
- **Deterministic VAD State Machine**: Manages transitions across `IDLE`, `VOICE_STARTED`, `VOICE_ACTIVE`, `SILENCE_DETECTED`, `UTTERANCE_COMPLETE`, and `RESET`.
- **Per-Session VAD State**: Every `VoiceSession` maintains an isolated `VADSessionState` instance, guaranteeing zero cross-client state leakage during concurrent streams.
- **Utterance Boundary Notification**: When continuous silence exceeds `VAD_SILENCE_THRESHOLD_MS` (default 800ms), the backend marks the utterance as complete and emits a `type: utterance_ready` JSON event payload.
- **Buffer Persistence**: Buffered raw PCM audio frames in `AudioBuffer` are **preserved** upon utterance completion, keeping audio available for downstream Speech-To-Text (STT) consumption in Milestone 5.

---

## 🎙️ Deep Dive: Voice Activity Detection (VAD) Architecture

### Why VAD Exists
In conversational voice interfaces (like ChatGPT Voice), detecting when a user starts and finishes speaking is critical. Without VAD, the server would either have to wait for manual push-to-talk button presses or stream audio indefinitely.

### Why Whisper / STT Should Not Receive Endless Audio
Passing continuous, unbroken audio streams to heavy Speech-To-Text (STT) models like Whisper or Deepgram leads to:
1. **Excessive Latency**: Processing long silence buffers wastes compute time before generating a response.
2. **High API Costs**: Cloud STT providers charge per second of audio processed. Sending silence burns budget.
3. **Hallucination Risk**: STT models fed pure silence or static noise often hallucinate phantom text phrases (e.g. "Thank you for watching!", "Subtitles by...").

### How Utterances are Detected
1. **Signal Energy Evaluation**: `VADService` calculates normalized RMS energy per 16-bit PCM frame. Frames meeting or exceeding `VAD_ENERGY_THRESHOLD` (default 0.015) are classified as human voice.
2. **Minimum Speech Validation**: Speech must persist for `VAD_MIN_SPEECH_DURATION_MS` (default 250ms) to trigger `VOICE_STARTED`, filtering out transient clicks or pop noises.
3. **Silence Timeout**: Once voice is active, if silence persists for `VAD_SILENCE_THRESHOLD_MS` (default 800ms), `VADService` transitions to `UTTERANCE_COMPLETE` and sets `ready_for_transcription = True`.

### How VAD Reduces LLM Latency
By segmenting speech into distinct utterances at natural pause boundaries, the backend triggers Speech-To-Text and LLM generation immediately when the user finishes speaking. End-to-end user-perceived latency drops to under 1 second.

---

## 🔄 VAD Finite State Machine Transitions

```
                    ┌─────────────────────────┐
                    │          IDLE           │
                    └────────────┬────────────┘
                                 │ (Voice detected >= 250ms)
                                 ▼
                    ┌─────────────────────────┐
                    │      VOICE_STARTED      │
                    └────────────┬────────────┘
                                 │ (Voice continues)
                                 ▼
                    ┌─────────────────────────┐
                    │      VOICE_ACTIVE       │<──────┐
                    └────────────┬────────────┘       │ (Voice resumes)
                                 │ (Voice stops)      │
                                 ▼                    │
                    ┌─────────────────────────┐       │
                    │    SILENCE_DETECTED     ├───────┘
                    └────────────┬────────────┘
                                 │ (Silence >= 800ms)
                                 ▼
                    ┌─────────────────────────┐
                    │   UTTERANCE_COMPLETE    │
                    └────────────┬────────────┘
                                 │ (Consumer resets or consumes)
                                 ▼
                    ┌─────────────────────────┐
                    │          RESET          │ ───> Back to IDLE
                    └─────────────────────────┘
```

---

## 🎙️ End-to-End Voice Pipeline Architecture

```
Client (Microphone Stream over WebSocket /ws/voice)
    │
    ├──> 1. Ingest Binary Packet ─────────────> [ AudioStreamService ] ──> [ AudioBuffer ]
    │                                                                  (Stores raw PCM bytes)
    │
    ├──> 2. Signal Energy & State Analysis ───> [ VADService ]
    │        │                                  (Evaluates RMS & transitions state)
    │        ▼
    │    Is Utterance Complete? (Silence >= 800ms)
    │        │
    │        ├──> YES: Send JSON {"type": "utterance_ready", "duration": 2.84, "bytes": 90564}
    │        │         (AudioBuffer preserved for STT)
    │        │
    │        └──> NO: Continue streaming binary frame ACK
    │
    └──> 3. (Milestone 5 Extension Point) ────> [ STTService ]
             Reads AudioBuffer.export_raw() -> Transcribes -> Calls LLM -> TTS -> Audio Out
```

---

## 📂 Directory Responsibilities Breakdown

```
backend/
├── app/
│   ├── __init__.py                 # Application package metadata
│   ├── main.py                     # FastAPI application factory, lifespan, CORS, & exception handler setup
│   ├── core/                       # Cross-cutting infrastructure concerns
│   │   ├── config.py               # Settings management via Pydantic BaseSettings (incl. VAD parameters)
│   │   ├── logging.py              # Structured JSON / Text loggers configuration
│   │   └── exceptions.py           # Domain exception classes & global error handlers
│   ├── models/                     # Data & Domain Models Layer
│   │   ├── voice_session.py        # VoiceSession model tracking connection status, buffer, & VAD state
│   │   ├── audio_buffer.py         # AudioBuffer model storing raw session audio bytes & metrics
│   │   └── vad_state.py            # VADState enum, VADEvent enum, & VADSessionState model
│   ├── api/                        # HTTP Routing & WebSocket Controller Layer
│   │   ├── router.py               # Root API router combining health & WebSocket endpoints
│   │   └── v1/
│   │       ├── router.py           # V1 route aggregator
│   │       └── endpoints/
│   │           ├── health.py       # GET /health endpoints
│   │           └── voice.py        # WebSocket /ws/voice multiplexed binary/VAD/JSON streaming endpoint
│   ├── services/                   # Business logic & Voice AI engine services
│   │   ├── base.py                 # Abstract Base Class defining service lifecycle interface (BaseService)
│   │   ├── connection_manager.py   # Asynchronous WebSocket connection lifecycle manager
│   │   ├── audio_stream_service.py # Audio stream packet ingestion, validation, and frame logging service
│   │   ├── vad_service.py          # Voice Activity Detection (VAD) signal engine & state machine
│   │   ├── audio_service.py        # Audio processing & format conversion placeholder
│   │   ├── stt_service.py          # Speech-to-Text transcription placeholder (Milestone 5 integration)
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
│   ├── test_audio_stream.py        # AudioBuffer & binary streaming unit tests
│   ├── test_vad_state_machine.py   # VAD state machine transition unit tests
│   ├── test_vad_service.py         # VADService RMS calculation & frame processing tests
│   ├── test_utterance_detection.py # Utterance completion & utterance_ready event integration tests
│   └── test_multiple_clients_vad.py# Per-session VAD state isolation tests
├── .env.example                    # Template environment variables
├── .env                            # Local development configuration file
├── pytest.ini                      # Pytest runner configuration
├── requirements.txt                # Production & development dependencies
└── README.md                       # Architecture documentation (this file)
```

---

## 🧪 Running Automated Tests

Run the full automated test suite (health, websockets, audio buffers, VAD engine):
```bash
cd backend
python -m pytest
```
