import type { AudioSource } from "./AudioSource";

const PREFERRED = ["audio/webm;codecs=opus", "audio/webm", "audio/mp4", "audio/ogg;codecs=opus"];

export function pickMimeType(): string {
  if (typeof MediaRecorder === "undefined") return "";
  return PREFERRED.find((m) => MediaRecorder.isTypeSupported(m)) ?? "";
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
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
    });
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
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    this.recorder = null;
    this.levelCb?.(0);
  }
}
