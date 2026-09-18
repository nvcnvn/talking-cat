import type { ApiClient, ChatResult, TalkOptions, TurnEvent } from "./client";

export class HttpApiClient implements ApiClient {
  constructor(private base: string = "") {}

  private url(path: string) {
    return `${this.base}/api${path}`;
  }

  async talkStream(audio: Blob, opts: TalkOptions, onEvent: (e: TurnEvent) => void): Promise<void> {
    const form = new FormData();
    const ext = audio.type.includes("wav") ? "wav" : audio.type.includes("mp4") ? "mp4" : audio.type.startsWith("text") ? "txt" : "webm";
    form.append("audio", audio, `clip.${ext}`);
    form.append("session_id", opts.sessionId);
    form.append("age_group", opts.ageGroup);
    form.append("want_audio", String(opts.wantAudio));
    const r = await fetch(this.url("/talk/stream"), { method: "POST", body: form });
    if (!r.ok || !r.body) throw new Error(`talk failed: ${r.status}`);

    // NDJSON: one event per line, handed on the moment its line is complete.
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buf = "";
    for (;;) {
      const { done, value } = await reader.read();
      buf += decoder.decode(value ?? new Uint8Array(), { stream: !done });
      let nl: number;
      while ((nl = buf.indexOf("\n")) >= 0) {
        const line = buf.slice(0, nl).trim();
        buf = buf.slice(nl + 1);
        if (line) onEvent(JSON.parse(line) as TurnEvent);
      }
      if (done) break;
    }
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

  async thinking(index: number): Promise<Blob> {
    const r = await fetch(this.url(`/thinking/${index}`));
    if (!r.ok) throw new Error(`thinking failed: ${r.status}`);
    return r.blob();
  }

  async clearSession(sessionId: string): Promise<void> {
    await fetch(this.url(`/session/${encodeURIComponent(sessionId)}`), { method: "DELETE" });
  }
}
