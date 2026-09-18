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

Two supported environments. Both use the same code; only the provider config differs.

### Linux CPU (Docker, the testing environment)

```bash
cp .env.example .env      # put your GLM key in LLM_API_KEY
make up                   # http://localhost:8080
```

First start downloads the Whisper model (~500 MB for `small`) into a Docker volume. Whisper runs on
faster-whisper (CTranslate2, int8), Piper on ONNX Runtime CPU.

Fake stack (no key, no models, instant):

```bash
make up-fake
```

### Mac with Apple Silicon (MLX)

MLX needs Metal, which Docker's Linux VM cannot reach, so the backend runs natively and only the
web container runs in Docker (it proxies `/api` to `host.docker.internal:8000`).

```bash
brew install uv          # audio decoding uses PyAV's bundled ffmpeg, no system ffmpeg needed
cp .env.example .env      # LLM key; STT_PROVIDER is overridden to mlx_whisper by the make target
make mac-setup            # venv with mlx-whisper instead of faster-whisper
make mac-backend          # native backend on :8000 (first run downloads MLX_WHISPER_MODEL from Hugging Face)
make mac-up               # web on http://localhost:8080
```

`MLX_WHISPER_MODEL=mlx-community/whisper-large-v3-turbo` is the recommended setting on an M-series
chip: noticeably better Vietnamese than `small`, and still well under a second per clip. Piper stays on
CPU (it is already ~0.3 s), and edge-tts is network-bound, so STT is the only stage MLX accelerates.

| Stage | Linux CPU | Mac MLX |
|---|---|---|
| STT | `WhisperSTT` (faster-whisper) | `MlxWhisperSTT` (mlx-whisper) |

The MLX provider can be smoke-tested on Linux with `uv pip install "mlx[cpu]" mlx-whisper` (same code, same
transcripts, but ~90 s per clip because MLX's Linux CPU backend is unoptimized). The stubbed unit tests in
`backend/tests/test_stt_mlx.py` cover it in CI without MLX installed.
| TTS | `EdgeTTS` → `PiperTTS` | same |
| LLM | GLM over HTTP | same |

## Test

```bash
make test-backend   # pytest, all fakes, ~0.2s
make test-web       # tsc + vite build + vitest (state machine, mock client)
make up-fake && make e2e   # Playwright: file-driven turns through the real HTTP path
```

### Driving the app with prerecorded voice

* **Browser:** open `http://localhost:8080/?test=1` — a test panel replaces the mic. Upload a `.wav`/`.webm`/`.mp3`, or a `.txt` whose first line is `#transcript: <words>` (fake STT only). Add `&audio=off` to skip playback, `&api=mock` to run with no backend at all.
* **CLI:** `make talk FILE=path/to/clip.wav` posts the file to `/api/talk` and saves the cat's reply audio.
  `backend/scripts/stt_file.py clip.mp3 ...` runs only the STT provider selected by `STT_PROVIDER` on local files, to compare Whisper engines/models across the two environments on identical clips.
* **Playwright:** `web/tests/e2e/talk.spec.ts` uses `setInputFiles` on the same panel. The config also launches Chromium with a fake media device, so the real `MicrophoneSource` can be fed a WAV via `--use-file-for-fake-audio-capture=<file.wav>` when you want to test the mic path itself. `mic-autosubmit.spec.ts` does exactly that for the
  silence detector: speech-then-silence must submit with one tap, and pure silence must never reach the backend.

## Latency notes (measured)

| Stage | Typical | Notes |
|---|---|---|
| Whisper `small`, CPU int8 | 1.5–2.5 s | `WHISPER_INITIAL_PROMPT` biases it toward "Miu" |
| GLM 5.2 | 5–6 s | `thinking: disabled` is sent; input safety classifier runs concurrently, not serially |
| edge-tts | ~0.5 s repeated, 1.5–5.6 s novel | see the caching note below: novel text is slow and fails ~1 in 3 with "No audio was received" |
| Piper (`vi_VN-vais1000-medium`) | 0.2–0.7 s | self-hosted fallback when edge-tts misses `TTS_DEADLINE_S` (default 8 s); plainer voice |
| Apple `say` (`Linh`, macOS) | ~0.5 s | `TTS_PROVIDER=apple`; on-device, no network, no model download; needs the vi_VN voice installed (`say -v '?'`) |

Set `TTS_PROVIDER=piper` to go fully self-hosted, or `TTS_FALLBACK=none` to insist on the Edge voice.
On a Mac, `TTS_PROVIDER=apple TTS_FALLBACK=none` is the only setting that guarantees a single voice for
every utterance in a turn, at ~0.5 s each and with no network in the path.

### Would a locally hosted LLM be faster?

Measured with `mlx-lm` on an M4 Pro / 64 GB, same persona prompt, three child-style questions:

| model | reply time (warm) | notes |
|---|---|---|
| GLM 5.2 over greennode | 5.0–7.7 s | 3.3–4.7 s of it is time-to-first-token; generation itself ~1 s |
| `Qwen3-4B-Instruct-2507-4bit` | 1.2–2.7 s | ~2.3 GB; followed the persona worst — refused a clear sentence |
| `Qwen3-30B-A3B-Instruct-2507-4bit` | 1.2–4.8 s | ~17 GB, MoE so only 3B active; better Vietnamese, leaked a "Miu:" prefix |

So yes — roughly 4x faster, and the latency is predictable instead of queue-dependent. The cost is
instruction-following: the small models are looser with the safety and persona rules, which is where
this app cannot be loose. A hybrid (local model for chat, hosted model for the safety classifier) is
the obvious next experiment; nothing in the codebase assumes one provider, `LLM_BASE_URL` points
anywhere OpenAI-compatible (including `mlx_lm.server`).

### Streaming a turn

`POST /api/talk/stream` returns NDJSON, one line per event: `transcript`, then one `chunk` per
sentence (text + its audio), then `done` with the timings. The cat speaks sentence 1 while the LLM
is still writing sentence 2: generation, TTS and playback overlap. The browser uses this endpoint;
`POST /api/talk` stays for the CLI and for anything that wants one blocking JSON answer.

Measured on the same clip (MLX Whisper + GLM 5.2), time until the child *hears* the cat:

| setup | first audio | whole turn |
|---|---|---|
| blocking `/api/talk`, edge-tts | 8.3 s (nothing before that) | 8.3 s |
| streamed, edge-tts, 2.5 s deadline | 9.2–9.8 s | 10.4–12.0 s |
| streamed, edge-tts, `TTS_DEADLINE_S=1.2` | 6.8–7.5 s | 8.1–8.5 s |
| **streamed, `TTS_PROVIDER=piper`** | **3.6–6.9 s** | **3.9–7.0 s** |

While the child waits for that first sentence, the cat mutters a short "ừmmm, để Miu nghĩ..."
(`GET /api/thinking/{i}`, up to three in a row, stopped the moment the real answer starts). There are a
dozen of these lines in `THINKING_LINES` and the client picks at random; the backend wraps any index it
is given, so adding lines needs no frontend change. The
backend synthesises those lines with the *same* TTS provider as the reply and caches them, because a
filler in a different voice sounds like a different cat.

**The fillers sounded right and the replies did not, and the reason is not the deadline.** Microsoft's
endpoint behaves as if it caches per text. Measured directly, same voice, same session:

| text | first render | repeat render | failures |
|---|---|---|---|
| the 12 fixed `THINKING_LINES` | 1.5–2.3 s | ~0.5 s | none observed |
| a freshly generated reply sentence | 1.5–5.6 s | ~0.5 s | ~1 in 3, `NoAudioReceived` |

So the fillers — a dozen fixed strings synthesised over and over — are permanently warm and always
arrive in Edge's voice, while every reply sentence is novel text that fails often enough to be handed
to Piper mid-reply. Raising `TTS_DEADLINE_S` cannot fix this: `NoAudioReceived` is a hard error that
comes back in ~2.5 s, not a stall. The deadline only governs genuine stalls, and 2.5 s was cutting off
novel renders that would have succeeded, so it is now 6 s.

The fix is to stop mixing engines. `TTS_PROVIDER=apple` with `TTS_FALLBACK=none` renders every
utterance — filler and reply alike — with macOS `say` in ~0.45 s, on-device, with nothing to fail and
no second voice to fall back to. That is the default in this repo's `.env` for the Mac setup. Since
there is then no fallback to catch an error, `talk_stream()` guards each synthesis: a failed sentence
arrives silent with its text on screen instead of killing the turn (`tests/test_tts_guard.py`).

Streaming only pays off if a sentence can be synthesised quickly: with edge-tts as primary, a stalled
sentence waits out `TTS_DEADLINE_S` before Piper takes over, and splitting the reply multiplies that
wait. That is the price of the long deadline above — paid in latency, which the fillers hide, rather
than in a change of voice, which they do not. `TTS_PROVIDER=piper` trades the nicer voice for speed.

Every turn logs its own breakdown, so a slow turn can be attributed without guessing:

```
INFO app.core.pipeline: turn session=... timings_ms={'stt': 437, 'llm': 5004, 'tts': 1751, 'total': 7192} chars=79
```

The LLM is ~70% of a turn and almost all of that is the provider's time-to-first-token: measured against
GLM 5.2 on greennode, streaming gives the first token after 3.3–4.7 s and then finishes in ~1 s. Prompt
size barely matters (a 2135-char system prompt costs ~0.4 s over a one-line one), so shortening the
persona is not the lever — overlapping TTS with generation, or a faster endpoint, is.

## Taking turns (no second tap)

The child taps once. `web/src/audio/endpointer.ts` watches the mic level and ends the turn by itself
after `silenceMs` of quiet (default 1.2 s), once at least `minSpeechMs` of speech has been heard;
if nothing is ever said it gives up after `noSpeechMs` and the cat answers without any backend call.
A child describing something at length is never cut off mid-sentence: only a pause ends the turn, and
`maxMs` (45 s) is a ceiling for a child who never pauses at all.

Speech also has to beat the room, not just a fixed number. The endpointer learns the ambient level over
the first 300 ms (the mic has just opened; the child is still drawing breath), then tracks it downward
instantly and upward over ~3 s, and counts a level as speech only above `max(threshold, floor × noiseRatio)`.
Without this a fan or a TV sat permanently above the fixed threshold, so the quiet never arrived, the
hard cap fired, and 15 s of room noise went to Whisper — which duly invented a sentence out of it.
The floor is capped internally so it can never climb high enough to gate out a real speaking voice.

Tune per room without rebuilding: `?vadThreshold=0.2&vadSilence=1800&vadNoise=3&vadMax=60000`
(level is 0..1, clamped at 1).

After the cat finishes, the mic reopens by itself, so a three-year-old taps once per conversation
rather than once per turn. Two turns in a row with nothing said end the loop (the child has walked
away), as does tapping the cat while it speaks. `?hands=off` restores tap-per-turn.

Several children talking at once is handled at the prompt, not by a threshold. Measured on mixed clips
with `mlx-community/whisper-large-v3-turbo`:

| clip | transcript | Whisper confidence |
|---|---|---|
| one voice | correct | 0.88 |
| two voices overlapping | mash-up of both questions | 0.85 |
| three voices | mash-up | 0.78 |
| babble + noise | nonsense | 0.53 |

Overlapping voices are each clean, so confidence does *not* separate them, and GLM will happily answer
the mash-up. The persona prompt therefore has a "KHI NGHE KHÔNG RÕ" rule: when a sentence splices two
different topics, the cat answers the part it heard most clearly, briefly, and then asks the friends to
speak one at a time. Measured on 3 spliced and 5 ordinary sentences: every input got an answer (no
refusals), and the take-turns reminder appeared on 1 of 3 spliced ones - the ceiling is the model
noticing the splice at all, not the wording of the rule. `STT_MIN_CONFIDENCE` (default 0.55) is only a noise gate for audio
Whisper itself is unsure of; it skips the LLM round-trip on genuinely degraded clips.

The wording matters less than the examples: an earlier version without them refused
"Miu ơi, còn voi keo như thế nào?" — a single child whose "con voi kêu" Whisper mis-heard. A separate
LLM classifier asked the same question in its own call was also tried and measured worse (1/3 spliced
sentences caught versus 2/3, plus a false positive), so it was removed rather than kept as an option.

## Safety

1. **Persona prompt** (`backend/app/core/prompts.py`): short Vietnamese sentences, social skills, no personal info, comforts and redirects to parents.
2. **Rule filter**, in two tiers, because a keyword cannot tell a request from a memory. Words a
   child essentially cannot use innocently (giết, ma túy, tự tử, sexual terms, phone numbers) are
   blocked before the LLM sees them. Context-dependent ones (đánh nhau, súng, bom, đấm, máu me, ma
   quỷ, kinh dị, hút thuốc, đồ ngu) are **not** blocked: they are marked as a *soft topic*, which
   appends a "handle this gently" hint to the system prompt for that turn. Blocking them meant
   answering "hôm nay bạn Bo đánh em, em buồn lắm" with "Miu doesn't talk about that" - the moment
   the persona was written for. 9 of 14 ordinary kid sentences were gated that way before this split.
3. **LLM classifier** on input (default on), which does see the whole sentence and catches the
   requests the narrowed rules let through ("cây súng bắn thế nào" → violence). It fails open on
   transport errors because rules already ran. Its prompt classifies *intent*, not vocabulary.
   Known gap: "quả bom nổ" is classified ok, and is left to the persona to deflect.
   The output rules are the strict tier, minus any sensitive word the child themselves just used -
   the cat may answer "chơi súng nước vui lắm" but may not be the one to bring a gun up.
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
