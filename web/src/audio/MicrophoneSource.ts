import type { AudioSource } from "./AudioSource";

const PREFERRED = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];

export function pickMimeType(): string {
  if (typeof MediaRecorder === "undefined") return "";
  return PREFERRED.find((m) => MediaRecorder.isTypeSupported(m)) ?? "";
}

/** Opening the mic costs 150-600ms of device acquisition, and that was dead time between
 * every turn: the child starts talking into a mic that is not recording yet. So the stream
 * is held across turns and only dropped once the conversation has clearly stopped. */
let shared: MediaStream | null = null;
let release = 0;
const IDLE_RELEASE_MS = 10000;

async function acquire(): Promise<MediaStream> {
  clearTimeout(release);
  if (shared?.getAudioTracks().some((t) => t.readyState === "live")) return shared;
  shared = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
  });
  return shared;
}

/** Give the mic back if no new turn starts: the child has walked away. */
function scheduleRelease() {
  clearTimeout(release);
  release = window.setTimeout(releaseMic, IDLE_RELEASE_MS);
}

export function releaseMic() {
  clearTimeout(release);
  shared?.getTracks().forEach((t) => t.stop());
  shared = null;
}

export class MicrophoneSource implements AudioSource {
  readonly kind = "microphone" as const;
  private stream: MediaStream | null = null;
  private recorder: MediaRecorder | null = null;
  private chunks: BlobPart[] = [];
  private levelCb: ((l: number) => void) | null = null;
  private ctx: AudioContext | null = null;
  private raf = 0;

  onLevel(cb: (level: number) => void) {
    this.levelCb = cb;
  }

  async start(): Promise<void> {
    this.stream = await acquire();
    const mimeType = pickMimeType();
    this.recorder = new MediaRecorder(this.stream, mimeType ? { mimeType } : undefined);
    this.chunks = [];
    this.recorder.ondataavailable = (e) => e.data.size && this.chunks.push(e.data);
    this.recorder.start(250);
    this.startMeter();
  }

  stop(): Promise<Blob> {
    return new Promise((resolve, reject) => {
      const rec = this.recorder;
      if (!rec) return reject(new Error("not recording"));
      rec.onstop = () => {
        const blob = new Blob(this.chunks, { type: rec.mimeType || "audio/webm" });
        this.cleanup();
        resolve(blob);
      };
      rec.onerror = () => {
        this.cleanup();
        reject(new Error("recorder error"));
      };
      rec.state === "inactive" ? rec.onstop(new Event("stop")) : rec.stop();
    });
  }

  cancel() {
    try {
      this.recorder?.state !== "inactive" && this.recorder?.stop();
    } catch {
      /* ignore */
    }
    this.cleanup();
  }

  private startMeter() {
    if (!this.levelCb || !this.stream || typeof AudioContext === "undefined") return;
    this.ctx = new AudioContext();
    const src = this.ctx.createMediaStreamSource(this.stream);
    const analyser = this.ctx.createAnalyser();
    analyser.fftSize = 512;
    src.connect(analyser);
    const buf = new Uint8Array(analyser.frequencyBinCount);
    const tick = () => {
      analyser.getByteTimeDomainData(buf);
      let sum = 0;
      for (const b of buf) sum += (b - 128) ** 2;
      this.levelCb?.(Math.min(1, Math.sqrt(sum / buf.length) / 40));
      this.raf = requestAnimationFrame(tick);
    };
    tick();
  }

  private cleanup() {
    cancelAnimationFrame(this.raf);
    this.ctx?.close().catch(() => {});
    this.ctx = null;
    this.stream = null; // the tracks stay live for the next turn; see scheduleRelease
    scheduleRelease();
    this.recorder = null;
    this.levelCb?.(0);
  }
}
