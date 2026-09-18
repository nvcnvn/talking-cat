# Mèo Miu — talking cat for Vietnamese kids (3–12)

A voice-first web app: the child taps the mic, talks, and an animated cat answers out loud.
Speech → text (Whisper) → LLM (GLM 5.2) → text → speech (Edge neural voice), with family-safe guardrails.

## Architecture

```
web (React SPA, nginx)                      backend (FastAPI)
┌───────────────────────────┐    /api/*     ┌─────────────────────────────────────────┐
│ AudioSource ──┐           │ ───────────►  │ ConversationService                     │
│  • Microphone │           │               │   STTProvider   • WhisperSTT  • FakeSTT │
│  • File       ├─► useConversation ─► ApiClient   LLMProvider   • OpenAICompat • FakeLLM │
│ AudioPlayer ──┘  (state machine)   • Http │   TTSProvider   • EdgeTTS     • FakeTTS │
│  • HtmlAudio               • Mock  │   SafetyFilter  • Rules + LLM classifier │
│  • Silent                          │   SessionStore  • InMemory              │
└───────────────────────────┘               └─────────────────────────────────────────┘
```

Every I/O edge is an interface with a real and a fake implementation, chosen by config, never by code edits:

| Stage          | Interface (backend `app/core/interfaces.py`, web `src/audio`, `src/api`) | Real                | Fake / file-driven                                   |
|----------------|--------------------------------------------------------------------------|---------------------|------------------------------------------------------|
| Voice input    | `AudioSource`                                                            | `MicrophoneSource`  | `FileSource` (any audio file, or `#transcript:` txt) |
| Voice output   | `AudioPlayer`                                                            | `HtmlAudioPlayer`   | `SilentPlayer`                                       |
| Backend calls  | `ApiClient`                                                              | `HttpApiClient`     | `MockApiClient` (in-browser, no server)              |
| Speech to text | `STTProvider`                                                            | `WhisperSTT`        | `FakeSTT`                                            |
| LLM            | `LLMProvider`                                                            | `OpenAICompatLLM`   | `FakeLLM` (scripted / echo)                          |
| Text to speech | `TTSProvider`                                                            | `EdgeTTS` → `PiperTTS` fallback | `FakeTTS` (real WAV beep)                |
| Safety         | `SafetyFilter`                                                           | Rules + LLM         | Rules only (`SAFETY_LLM_CHECK=false`)                |

Endpoints: `POST /api/talk` (audio → full turn), and one per stage: `/api/stt`, `/api/chat`, `/api/tts`. `GET /api/health`.

## Run

```bash
cp .env.example .env      # put your GLM key in LLM_API_KEY
make up                   # http://localhost:8080
```

First start downloads the Whisper model (~500 MB for `small`) into a Docker volume.

Fake stack (no key, no models, instant):

```bash
make up-fake
```

## Test

```bash
make test-backend   # pytest, all fakes, ~0.2s
make test-web       # tsc + vite build + vitest (state machine, mock client)
make up-fake && make e2e   # Playwright: file-driven turns through the real HTTP path
```

### Driving the app with prerecorded voice

* **Browser:** open `http://localhost:8080/?test=1` — a test panel replaces the mic. Upload a `.wav`/`.webm`/`.mp3`, or a `.txt` whose first line is `#transcript: <words>` (fake STT only). Add `&audio=off` to skip playback, `&api=mock` to run with no backend at all.
* **CLI:** `make talk FILE=path/to/clip.wav` posts the file to `/api/talk` and saves the cat's reply audio.
* **Playwright:** `web/tests/e2e/talk.spec.ts` uses `setInputFiles` on the same panel. The config also launches Chromium with a fake media device, so the real `MicrophoneSource` can be fed a WAV via `--use-file-for-fake-audio-capture=<file.wav>` when you want to test the mic path itself.

## Latency notes (measured)

| Stage | Typical | Notes |
|---|---|---|
| Whisper `small`, CPU int8 | 1.5–2.5 s | `WHISPER_INITIAL_PROMPT` biases it toward "Miu" |
| GLM 5.2 | 5–6 s | `thinking: disabled` is sent; input safety classifier runs concurrently, not serially |
| edge-tts | ~1 s when healthy | upstream randomly fails or stalls 10 s+; serial retries, late hedge, then Piper takes over at the deadline |
| Piper (`vi_VN-vais1000-medium`) | 0.2–0.7 s | self-hosted fallback when edge-tts misses `TTS_DEADLINE_S` (default 2.5 s); plainer voice |

Set `TTS_PROVIDER=piper` to go fully self-hosted, or `TTS_FALLBACK=none` to insist on the Edge voice.

## Safety

1. **Persona prompt** (`backend/app/core/prompts.py`): short Vietnamese sentences, social skills, no personal info, comforts and redirects to parents.
2. **Rule filter** on input and output: diacritics-insensitive keyword and pattern matching (violence, sexual, drugs, self-harm, hate, scary, phone numbers / addresses). Blocked input never reaches the LLM.
3. **LLM classifier** (optional second stage) on input and output; fails open on transport errors because rules already ran.
4. **Output sanitiser**: strips URLs, emoji, markdown; caps length on a sentence boundary.
5. **Parent gate** (arithmetic) in front of settings; no accounts, no persistence beyond an in-memory session with TTL.

## Layout

```
backend/app/core        pipeline, interfaces, models, prompts, safety, session   (no framework imports)
backend/app/providers   whisper, openai-compat, edge-tts, fakes
backend/app/api         FastAPI routes + schemas (thin)
backend/app/deps.py     composition root (Settings → providers → service)
backend/scripts         talk_file.py
web/src/audio           AudioSource / AudioPlayer + implementations
web/src/api             ApiClient + http / mock
web/src/state           pure reducer + useConversation hook
web/src/components      Cat, TalkButton, Bubble, ParentGate, TestPanel
web/src/runtime.ts      browser composition root (URL flags)
```
