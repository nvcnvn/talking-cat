import { blobToText, type ApiClient, type ChatResult, type TalkOptions, type TalkResult } from "./client";

/** In-browser fake backend. Enables UI work and e2e tests with no server at all. */
export class MockApiClient implements ApiClient {
  constructor(private delayMs = 400) {}

  private wait() {
    return new Promise((r) => setTimeout(r, this.delayMs));
  }

  private replyFor(text: string) {
    const t = text.toLowerCase();
    if (/(giết|đánh nhau|ma quỷ)/.test(t)) {
      return { text: "Meo, chuyện đó Miu không nói đâu. Mình chơi đố vui về con vật nhé?", blocked: true, category: "violence", llm_used: false };
    }
    return { text: `Meo meo! Bạn vừa nói: ${text}. Bạn có muốn chơi đố vui không?`, blocked: false, category: "ok", llm_used: true };
  }

  async talk(audio: Blob, opts: TalkOptions): Promise<TalkResult> {
    await this.wait();
    let heard = "xin chào Miu";
    if (audio.type.startsWith("text/")) {
      const raw = await blobToText(audio);
      const m = raw.match(/^#transcript:\s*(.*)$/m);
      if (m) heard = m[1].trim();
    }
    const reply = this.replyFor(heard);
    return {
      session_id: opts.sessionId,
      transcript: { text: heard, language: "vi", confidence: 1 },
      reply,
      audio: opts.wantAudio ? { mime: "audio/wav", base64: silentWavBase64(Math.min(4, 0.04 * reply.text.length)) } : null,
      timings_ms: { stt: 1, llm: 1, tts: 1, total: 3 },
    };
  }

  async chat(text: string, opts: TalkOptions): Promise<ChatResult> {
    await this.wait();
    return { session_id: opts.sessionId, reply: this.replyFor(text) };
  }

  async tts(): Promise<Blob> {
    await this.wait();
    return new Blob([Uint8Array.from(atob(silentWavBase64(1)), (c) => c.charCodeAt(0))], { type: "audio/wav" });
  }

  async clearSession(): Promise<void> {}
}

/** A quiet 8 kHz mono WAV of `seconds` length (small, but real, so <audio> plays it). */
export function silentWavBase64(seconds: number): string {
  const rate = 8000;
  const n = Math.max(1, Math.floor(rate * seconds));
  const buf = new ArrayBuffer(44 + n * 2);
  const v = new DataView(buf);
  const str = (o: number, s: string) => [...s].forEach((c, i) => v.setUint8(o + i, c.charCodeAt(0)));
  str(0, "RIFF"); v.setUint32(4, 36 + n * 2, true); str(8, "WAVE"); str(12, "fmt ");
  v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
  v.setUint32(24, rate, true); v.setUint32(28, rate * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
  str(36, "data"); v.setUint32(40, n * 2, true);
  for (let i = 0; i < n; i++) v.setInt16(44 + i * 2, Math.round(3000 * Math.sin((2 * Math.PI * 440 * i) / rate)), true);
  let bin = "";
  new Uint8Array(buf).forEach((b) => (bin += String.fromCharCode(b)));
  return btoa(bin);
}
