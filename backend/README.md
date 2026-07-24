# MailMind AI - Voice Engine Backend (Phase 1, Milestone 5 - Provider Architecture)

Production-ready FastAPI backend architecture, WebSocket communication, Audio Streaming & Buffering, Voice Activity Detection (VAD), and **Provider-Based Speech-To-Text (STT) Engine Strategy Architecture** for **MailMind AI** (Voice-First AI Email Executive Assistant).

---

## 🏛️ Architectural Overview & Design Principles

### 1. Clean Architecture & Design Patterns
- **Strategy Pattern (`BaseSTTProvider`)**: Abstract provider interface establishing a standard strategy contract across all STT provider adapters (`GroqSTTProvider`, future `OpenAISTTProvider`, `DeepgramSTTProvider`, `FasterWhisperProvider`, `AzureSTTProvider`).
- **Factory Pattern (`STTProviderFactory`)**: Dynamic provider strategy registry that instantiates concrete providers based on environment configuration (`STT_PROVIDER`).
- **Dependency Injection (`STTService`)**: High-level orchestrator service injected with a concrete `BaseSTTProvider` strategy during application startup in `app/main.py`.
- **Open/Closed Principle (OCP)**: Adding new providers requires creating only one new file under `app/services/providers/` and registering it in `STTProviderFactory`. Zero code changes are required in `STTService`, WebSocket controllers (`/ws/voice`), or conversation orchestrators.

---

## 🎙️ Deep Dive: Speech-To-Text (STT) Provider Architecture

### System Flow
```
WebSocket Router (/ws/voice)
       │
       ▼ (Calls stt_service.transcribe(pcm_bytes))
STTService Orchestrator (Request Validation, Timing, Telemetry Logging, Standardized Output Schema)
       │
       ▼ (Delegates via BaseSTTProvider Interface - Strategy Pattern)
STTProviderFactory (Instantiates provider based on STT_PROVIDER config - Factory Pattern)
       │
       ▼
GroqSTTProvider (Concrete Provider: In-Memory PCM->WAV, AsyncGroq Client, API & Timeout Error Handling)
```

### 1. In-Memory PCM-to-WAV Conversion (`pcm_to_wav`)
Converts raw 16-bit 16000Hz mono PCM audio bytes to WAV containers completely in RAM using standard library `wave` and `io.BytesIO`. No temporary files or disk writes occur.

### 2. Standardized Response & Error Contracts
All transcription attempts return a predictable dictionary schema:
- **Success Schema**:
  ```json
  {
      "success": true,
      "text": "Schedule an executive sync for tomorrow morning.",
      "language": "en",
      "processing_ms": 342,
      "provider": "groq",
      "model": "whisper-large-v3-turbo",
      "word_count": 7
  }
  ```
- **Error Schema**:
  ```json
  {
      "success": false,
      "provider": "groq",
      "error": "Groq STT provider timed out after 30.0s.",
      "processing_ms": 30001
  }
  ```

---

## 🚀 How to Add a New STT Provider (Extensibility Guide)

To add a new provider (e.g. `openai` using `whisper-1`):

1. **Create Provider File**: Create `app/services/providers/openai_stt.py` inheriting from `BaseSTTProvider`:
   ```python
   from app.services.providers.base_provider import BaseSTTProvider

   class OpenAISTTProvider(BaseSTTProvider):
       @property
       def provider_name(self) -> str:
           return "openai"

       async def initialize(self) -> None: ...
       async def is_ready(self) -> bool: ...
       async def health_check(self) -> bool: ...
       async def shutdown(self) -> None: ...
       async def transcribe(self, audio_bytes: bytes, language: str = "en") -> dict[str, Any]: ...
   ```

2. **Register in Factory**: In `app/services/providers/factory.py` or during package import:
   ```python
   STTProviderFactory.register_provider("openai", OpenAISTTProvider)
   ```

3. **Configure `.env`**:
   ```env
   STT_PROVIDER=openai
   ```

**Zero code changes required in `voice.py`, `STTService`, or `main.py`!**

---

## 📂 Directory Responsibilities Breakdown

```
backend/
├── app/
│   ├── main.py                     # FastAPI factory, lifespan DI setup
│   ├── core/                       # Core configuration & logging
│   │   └── config.py               # STT_PROVIDER, GROQ_API_KEY, STT_MODEL settings
│   ├── api/                        # HTTP & WebSocket endpoints
│   │   └── v1/endpoints/voice.py   # /ws/voice multiplexed binary/VAD/STT streaming endpoint
│   ├── services/                   # Service & Provider Strategy Layer
│   │   ├── base.py                 # BaseService & BaseSTTService interfaces
│   │   ├── stt_service.py          # STTService orchestrator (Strategy DI & Telemetry)
│   │   └── providers/              # STT Provider Strategy Package
│   │       ├── __init__.py         # Package exports
│   │       ├── base_provider.py    # BaseSTTProvider abstract base strategy
│   │       ├── groq_stt.py         # GroqSTTProvider & pcm_to_wav converter
│   │       └── factory.py          # STTProviderFactory registry
├── tests/                          # Automated testing suite
│   ├── test_stt_provider_factory.py# Provider Factory & registration tests
│   ├── test_groq_provider.py       # GroqSTTProvider & PCM-to-WAV unit tests
│   ├── test_stt_service.py         # STTService orchestrator & DI tests
│   ├── test_websocket_transcription.py# End-to-end WebSocket STT integration tests
│   └── ...
└── README.md                       # Architecture documentation (this file)
```

---

## 🧪 Running Automated Tests

Run the full automated test suite:
```bash
cd backend
python -m pytest
```
