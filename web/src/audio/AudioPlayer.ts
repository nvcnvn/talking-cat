/** Plays the cat's voice and reports a 0..1 level so the mouth can move. */
export interface AudioPlayer {
  play(clip: Blob, onLevel?: (level: number) => void): Promise<void>;
  stop(): void;
  /** Call from a user gesture so browsers allow playback. */
  unlock(): void;
}

export class HtmlAudioPlayer implements AudioPlayer {
  private el: HTMLAudioElement | null = null;
  private ctx: AudioContext | null = null;
  private analyser: AnalyserNode | null = null;
  private raf = 0;

  unlock() {
    if (typeof AudioContext === "undefined") return;
    this.ctx ??= new AudioContext();
    if (this.ctx.state === "suspended") this.ctx.resume().catch(() => {});
  }

  play(clip: Blob, onLevel?: (level: number) => void): Promise<void> {
    this.stop();
    if (clip.type.startsWith("text/")) return new SilentPlayer().play(clip, onLevel);
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(clip);
      const el = new Audio(url);
      this.el = el;
      const done = () => {
        cancelAnimationFrame(this.raf);
        onLevel?.(0);
        URL.revokeObjectURL(url);
        this.el = null;
        resolve();
      };
      el.onended = done;
      el.onerror = () => {
        done();
        reject(new Error("audio playback error"));
      };
      if (onLevel && this.ctx) this.meter(el, onLevel);
      el.play().catch((e) => {
        done();
        reject(e);
      });
    });
  }

  stop() {
    cancelAnimationFrame(this.raf);
    if (this.el) {
      this.el.pause();
      this.el.src = "";
      this.el = null;
    }
  }

  private meter(el: HTMLAudioElement, onLevel: (l: number) => void) {
    try {
      const ctx = this.ctx!;
      const src = ctx.createMediaElementSource(el);
      this.analyser = ctx.createAnalyser();
      this.analyser.fftSize = 256;
      src.connect(this.analyser);
      this.analyser.connect(ctx.destination);
      const buf = new Uint8Array(this.analyser.frequencyBinCount);
      const tick = () => {
        this.analyser!.getByteTimeDomainData(buf);
        let sum = 0;
        for (const b of buf) sum += (b - 128) ** 2;
        onLevel(Math.min(1, Math.sqrt(sum / buf.length) / 30));
        this.raf = requestAnimationFrame(tick);
      };
      tick();
    } catch {
      // Analyser unavailable (e.g. jsdom): fall back to a synthetic wobble.
      const tick = () => {
        onLevel(0.4 + 0.4 * Math.abs(Math.sin(performance.now() / 120)));
        this.raf = requestAnimationFrame(tick);
      };
      tick();
    }
  }
}

/** For tests / audio=off: resolves after a short, length-based delay with a synthetic mouth wobble. */
export class SilentPlayer implements AudioPlayer {
  private timer = 0;
  private raf = 0;
  constructor(private msPerKb = 200, private msPerChar = 45) {}
  unlock() {}
  play(clip: Blob, onLevel?: (l: number) => void): Promise<void> {
    this.stop();
    const ms = clip.type.startsWith("text/")
      ? Math.min(4000, Math.max(400, clip.size * this.msPerChar))
      : Math.min(2500, Math.max(300, (clip.size / 1024) * this.msPerKb));
    return new Promise((resolve) => {
      const tick = () => {
        onLevel?.(0.5 + 0.5 * Math.abs(Math.sin(performance.now() / 100)));
        this.raf = requestAnimationFrame(tick);
      };
      if (onLevel) tick();
      this.timer = window.setTimeout(() => {
        cancelAnimationFrame(this.raf);
        onLevel?.(0);
        resolve();
      }, ms);
    });
  }
  stop() {
    clearTimeout(this.timer);
    cancelAnimationFrame(this.raf);
  }
}
