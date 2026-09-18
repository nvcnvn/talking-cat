/** Pure state machine for one conversation. No DOM, no audio, no fetch: trivially unit-testable. */
export type Phase = "idle" | "listening" | "thinking" | "speaking" | "error";

export interface ConversationState {
  phase: Phase;
  sessionId: string;
  heard: string;
  reply: string;
  blocked: boolean;
  error: string | null;
  turns: number;
}

export type ConversationEvent =
  | { type: "LISTEN_START" }
  | { type: "LISTEN_STOP" }
  | { type: "TEXT_SUBMIT"; text: string }
  | { type: "HEARD"; text: string }
  | { type: "REPLY_CHUNK"; text: string }
  | { type: "RESULT"; heard: string; reply: string; blocked: boolean }
  | { type: "SPEAK_START" }
  | { type: "SPEAK_END" }
  | { type: "FAIL"; message: string }
  | { type: "INTERRUPT" }
  | { type: "RESET"; sessionId: string };

export function newSessionId(): string {
  return Math.random().toString(36).slice(2) + Date.now().toString(36);
}

export function initialState(sessionId = newSessionId()): ConversationState {
  return { phase: "idle", sessionId, heard: "", reply: "", blocked: false, error: null, turns: 0 };
}

export function reduce(s: ConversationState, e: ConversationEvent): ConversationState {
  switch (e.type) {
    case "LISTEN_START":
      return s.phase === "idle" || s.phase === "error" ? { ...s, phase: "listening", error: null } : s;
    case "LISTEN_STOP":
      return s.phase === "listening" ? { ...s, phase: "thinking" } : s;
    case "TEXT_SUBMIT":
      return s.phase === "idle" || s.phase === "error" ? { ...s, phase: "thinking", heard: e.text, error: null } : s;
    case "HEARD":
      return s.phase === "thinking" ? { ...s, heard: e.text, reply: "" } : s;
    case "REPLY_CHUNK":
      // The cat starts talking on the first sentence, while the rest is still being written.
      return s.phase === "thinking" || s.phase === "speaking"
        ? { ...s, phase: "speaking", reply: s.reply ? `${s.reply} ${e.text}` : e.text }
        : s;
    case "RESULT":
      return s.phase === "thinking" || s.phase === "speaking"
        ? { ...s, heard: e.heard, reply: e.reply, blocked: e.blocked, turns: s.turns + 1 }
        : s;
    case "SPEAK_START":
      return s.phase === "thinking" ? { ...s, phase: "speaking" } : s;
    case "SPEAK_END":
      return s.phase === "speaking" || s.phase === "thinking" ? { ...s, phase: "idle" } : s;
    case "FAIL":
      return { ...s, phase: "error", error: e.message };
    case "INTERRUPT":
      return s.phase === "speaking" || s.phase === "listening" ? { ...s, phase: "idle" } : s;
    case "RESET":
      return initialState(e.sessionId);
  }
}

/** True when the talk button should start a new turn. */
export function canListen(s: ConversationState): boolean {
  return s.phase === "idle" || s.phase === "error";
}
