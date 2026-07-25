# MailMind AI - Voice Engine Backend & Developer Tools

Production-ready FastAPI backend architecture, WebSocket communication, Audio Streaming & Memory Buffering, Voice Activity Detection (VAD), Provider-Based Speech-To-Text (STT) Engine Strategy Architecture, Conversation Intelligence Engine, and **Official Developer CLI Voice Client** for **MailMind AI** (Voice-First AI Email Executive Assistant).

---

## 🏛️ Architectural Overview & Design Principles

### Clean Architecture Layer Separation
- **Core / Config Layer (`app/core/`)**: Settings (`config.py`), Structured JSON Logging (`logging.py`), Exception Management (`exceptions.py`).
- **Models Layer (`app/models/`)**: `VoiceSession` (`voice_session.py`), `AudioBuffer` (`audio_buffer.py`), `VADSessionState` (`vad_state.py`), and `ConversationSession` / `ConversationTurn` / `ConversationMetadata` (`conversation_models.py`).
- **Service Layer (`app/services/`)**: Connection management (`connection_manager.py`), Audio stream ingestion (`audio_stream_service.py`), VAD Engine (`vad_service.py`), STT Provider Strategy & Factory (`stt_service.py`, `providers/`), Conversation Memory (`conversation_memory.py`), Prompt Builder (`prompt_builder.py`), Conversation Manager (`conversation_manager_service.py`), and Conversation Orchestrator (`conversation_service.py`).
- **API Transport Layer (`app/api/`)**: HTTP endpoints and WebSocket streaming controllers (`v1/endpoints/voice.py`).
- **Developer Tools Layer (`tools/`)**: Modular CLI Voice Client (`tools/test_voice_client.py`) supporting live microphone recording, binary PCM streaming, ANSI color UI cards, and message handling strategies.

---

## 🎙️ Developer CLI Voice Client (`tools/test_voice_client.py`)

The official internal developer testing tool allowing real-time testing of all backend milestones.

### Why Built:
- **No Heavy Frontend Needed**: Allows testing VAD, STT, and Conversation Engine without needing React, HTML, or WebSockets GUI code.
- **Hardware Integration**: Captures microphone audio using `sounddevice` and converts float32/int16 NumPy frames directly into 16-bit 16000Hz mono raw PCM bytes in RAM (50ms chunks = 1600 bytes).
- **Zero Disk Writes**: Performs 100% in-memory streaming over WebSocket (`ws://localhost:8000/ws/voice`).
- **Auto-Reconnection**: Reconnects automatically if the server restarts or connection drops.
- **Colored CLI Terminal UI**: Renders connection status badges, VAD transitions, STT transcript cards, and Conversation Ready prompt preview cards using `colorama`.

---

## 🔄 Voice Client Sequence Diagram

```
Hardware Mic ──> sounddevice InputStream Callback ──> float32 to int16 PCM Bytes ──> asyncio.Queue
                                                                                         │
                                                                                         ▼
WebSocket Server ◄────── ws.send(pcm_bytes) ◄────── WebSocketManager Sender Task ◄───────┘
       │
       ▼ (Server VAD + STT + Conversation Engine)
WebSocket Server ──────> ws.recv(json_string) ──────> MessageHandler ──────> TerminalUI Cards
```

---

## 💻 Expected CLI Terminal Output

```
============================================================
       MailMind AI Developer Voice Client
============================================================
 Server URL : ws://localhost:8000/ws/voice
 Audio Spec : 16000Hz 16-bit PCM Mono (50ms chunks)
------------------------------------------------------------

[CONNECTED] | Session ID: 8f3b2a7e-1234-4567-89ab-cdef01234567 Connection acknowledged
[LISTENING...] Speak into your microphone. VAD & STT active.

 [VAD] voice_started (Speech: 250ms, Silence: 0ms)
 [VAD] voice_active (Speech: 500ms, Silence: 0ms)
 [VAD] silence_detected (Speech: 500ms, Silence: 100ms)
 [VAD] utterance_complete (Speech: 500ms, Silence: 800ms)

--------------------------------------------------
[STT TRANSCRIPT]
 Text       : Schedule an executive sync for tomorrow morning.
 Provider   : groq
 Latency    : 145.0 ms
--------------------------------------------------

==================================================
[CONVERSATION READY - ENGINE PREPARED]
 Turn Number   : 1
 History Size  : 1 turns
 User Message  : Schedule an executive sync for tomorrow morning.
 Prompt Preview:
=== SYSTEM MESSAGE ===
You are MailMind AI, a professional AI email assistant. Be concise. Never hallucinate. Always ask for clarification if required.

=== CURRENT USER MESSAGE ===
User: Schedule an executive sync for tomorrow morning.
==================================================
```

---

## 🛠️ How to Run Developer Tools

### 1. Install Dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Start MailMind AI Backend Server
In Terminal 1:
```bash
cd backend
uvicorn app.main:app --reload --port 8000
```

### 3. Run Developer Voice Client
In Terminal 2:
```bash
cd backend
python tools/test_voice_client.py
```

Optional CLI flags:
```bash
python tools/test_voice_client.py --url ws://localhost:8000/ws/voice --rate 16000 --device 0
```

---

## 🔮 Future Milestone Extensibility (Milestones 7-12)

The `MessageHandler` and `TerminalUI` use an Open/Closed strategy table. Adding support for future milestone server events requires registering a single handler method:

```python
# Milestone 7: LLM Response
message_handler.register_handler("assistant_response", lambda payload: ui.print_future_event("assistant_response", payload))

# Milestone 8: Tool Execution
message_handler.register_handler("tool_execution", lambda payload: ui.print_future_event("tool_execution", payload))
```

---

## 📂 Complete Backend Directory Breakdown

```
backend/
├── app/
│   ├── main.py                     # FastAPI factory, lifespan DI setup
│   ├── core/                       # Core configuration & logging
│   ├── models/                     # VoiceSession, AudioBuffer, VADState, ConversationSession
│   ├── api/                        # HTTP & WebSocket endpoints (/ws/voice)
│   ├── services/                   # Connection, VAD, STT Provider, Conversation Engine services
│   └── providers/                  # STT Provider Strategy Package (Groq, Base, Factory)
├── tools/                          # Developer CLI Testing Client Subpackage
│   ├── __init__.py                 # Subpackage exports
│   ├── config.py                   # VoiceClientConfig (16-bit PCM chunk calculations)
│   ├── terminal_ui.py              # TerminalUI renderer (Colorama cards & fallback)
│   ├── audio_recorder.py           # AudioRecorder (sounddevice live microphone capture)
│   ├── message_handler.py          # MessageHandler (Server JSON event strategy parser)
│   ├── websocket_manager.py        # WebSocketManager (Async connection & reconnect loop)
│   └── test_voice_client.py        # VoiceClient CLI entrypoint orchestrator
├── tests/                          # Automated testing suite (60 test cases)
├── requirements.txt                # Production & development dependencies
└── README.md                       # Architecture documentation (this file)
```

---

## 🧪 Running Automated Tests

Run the full automated test suite (60 test cases):
```bash
cd backend
python -m pytest
```
