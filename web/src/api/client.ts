export type AgeGroup = "3-6" | "7-12";

export interface TalkResult {
  session_id: string;
  transcript: { text: string; language: string; confidence: number | null };
  reply: { text: string; blocked: boolean; category: string; llm_used: boolean };
  audio: { mime: string; base64: string } | null;
  timings_ms: Record<string, number>;
}

export interface ChatResult {
  session_id: string;
  reply: TalkResult["reply"];
}

export interface TalkOptions {
  sessionId: string;
  ageGroup: AgeGroup;
  wantAudio: boolean;
}

/** One line of POST /api/talk/stream: the cat speaks each "chunk" while the next is still being written. */
export type TurnEvent =
  | { type: "transcript"; transcript: TalkResult["transcript"] }
  | { type: "chunk"; text: string; audio?: { mime: string; base64: string } | null }
  | { type: "done"; reply: { text: string; blocked: boolean }; timings_ms: Record<string, number> };

/** Everything the UI needs from the backend. Implemented by HttpApiClient and MockApiClient. */
export interface ApiClient {
  /** Runs a turn, calling `onEvent` as each piece arrives. Must not be awaited per chunk by the caller. */
  talkStream(audio: Blob, opts: TalkOptions, onEvent: (e: TurnEvent) => void): Promise<void>;
  chat(text: string, opts: TalkOptions): Promise<ChatResult>;
  tts(text: string): Promise<Blob>;
  /** Filler audio for the wait, in the same voice as the reply. */
  thinking(index: number): Promise<Blob>;
  clearSession(sessionId: string): Promise<void>;
}

export function base64ToBlob(b64: string, mime: string): Blob {
  const bin = atob(b64);
  const bytes = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i);
  return new Blob([bytes], { type: mime });
}

/** Blob.text() with a FileReader fallback (jsdom, older Safari). */
export function blobToText(b: Blob): Promise<string> {
  if (typeof (b as Blob).text === "function") return b.text();
  return new Promise((resolve, reject) => {
    const r = new FileReader();
    r.onload = () => resolve(String(r.result));
    r.onerror = () => reject(r.error);
    r.readAsText(b);
  });
}
