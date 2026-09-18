import type { ApiClient, ChatResult, TalkOptions, TalkResult } from "./client";

export class HttpApiClient implements ApiClient {
  constructor(private base: string = "") {}

  private url(path: string) {
    return `${this.base}/api${path}`;
  }

  async talk(audio: Blob, opts: TalkOptions): Promise<TalkResult> {
    const form = new FormData();
    const ext = audio.type.includes("wav") ? "wav" : audio.type.includes("mp4") ? "mp4" : audio.type.startsWith("text") ? "txt" : "webm";
    form.append("audio", audio, `clip.${ext}`);
    form.append("session_id", opts.sessionId);
    form.append("age_group", opts.ageGroup);
    form.append("want_audio", String(opts.wantAudio));
    const r = await fetch(this.url("/talk"), { method: "POST", body: form });
    if (!r.ok) throw new Error(`talk failed: ${r.status}`);
    return r.json();
  }

  async chat(text: string, opts: TalkOptions): Promise<ChatResult> {
    const r = await fetch(this.url("/chat"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: opts.sessionId, text, age_group: opts.ageGroup }),
    });
    if (!r.ok) throw new Error(`chat failed: ${r.status}`);
    return r.json();
  }

  async tts(text: string): Promise<Blob> {
    const r = await fetch(this.url("/tts"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text }),
    });
    if (!r.ok) throw new Error(`tts failed: ${r.status}`);
    return r.blob();
  }

  async clearSession(sessionId: string): Promise<void> {
    await fetch(this.url(`/session/${encodeURIComponent(sessionId)}`), { method: "DELETE" });
  }
}
