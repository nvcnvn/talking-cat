import { canListen, initialState, reduce, type ConversationState } from "../../src/state/conversation";

const s0 = (): ConversationState => initialState("sid");

test("happy path: idle → listening → thinking → speaking → idle", () => {
  let s = reduce(s0(), { type: "LISTEN_START" });
  expect(s.phase).toBe("listening");
  s = reduce(s, { type: "LISTEN_STOP" });
  expect(s.phase).toBe("thinking");
  s = reduce(s, { type: "RESULT", heard: "chào", reply: "meo", blocked: false });
  expect(s).toMatchObject({ heard: "chào", reply: "meo", turns: 1 });
  s = reduce(s, { type: "SPEAK_START" });
  expect(s.phase).toBe("speaking");
  s = reduce(s, { type: "SPEAK_END" });
  expect(s.phase).toBe("idle");
  expect(canListen(s)).toBe(true);
});

test("cannot start listening while thinking", () => {
  const s = reduce(reduce(s0(), { type: "LISTEN_START" }), { type: "LISTEN_STOP" });
  expect(reduce(s, { type: "LISTEN_START" }).phase).toBe("thinking");
  expect(canListen(s)).toBe(false);
});

test("failure moves to error and can be retried", () => {
  const s = reduce(reduce(s0(), { type: "LISTEN_START" }), { type: "FAIL", message: "x" });
  expect(s.phase).toBe("error");
  expect(s.error).toBe("x");
  const again = reduce(s, { type: "LISTEN_START" });
  expect(again.phase).toBe("listening");
  expect(again.error).toBeNull();
});

test("interrupt stops speaking", () => {
  let s = reduce(reduce(s0(), { type: "TEXT_SUBMIT", text: "hi" }), { type: "SPEAK_START" });
  expect(s.phase).toBe("speaking");
  s = reduce(s, { type: "INTERRUPT" });
  expect(s.phase).toBe("idle");
});

test("reset gives a fresh session", () => {
  let s = reduce(s0(), { type: "TEXT_SUBMIT", text: "hi" });
  s = reduce(s, { type: "RESULT", heard: "hi", reply: "r", blocked: false });
  s = reduce(s, { type: "RESET", sessionId: "new" });
  expect(s).toEqual(initialState("new"));
});

test("RESULT outside thinking is ignored", () => {
  expect(reduce(s0(), { type: "RESULT", heard: "a", reply: "b", blocked: false }).reply).toBe("");
});
