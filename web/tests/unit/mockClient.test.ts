// @vitest-environment node
import { base64ToBlob, type TurnEvent } from "../../src/api/client";
import { MockApiClient, silentWavBase64 } from "../../src/api/mockClient";

test("mock client honours #transcript files and streams playable wav chunks", async () => {
  const api = new MockApiClient(0);
  const events: TurnEvent[] = [];
  await api.talkStream(new Blob(["#transcript: em thích mèo\n"], { type: "text/plain" }), { sessionId: "s", ageGroup: "3-6", wantAudio: true }, (e) => events.push(e));

  const first = events[0];
  const last = events[events.length - 1];
  expect(first.type === "transcript" && first.transcript.text).toBe("em thích mèo");
  expect(last.type === "done" && last.reply.text).toContain("em thích mèo");

  const chunks = events.filter((e): e is Extract<TurnEvent, { type: "chunk" }> => e.type === "chunk");
  expect(chunks.length).toBeGreaterThan(1); // more than one sentence: that is what overlaps with generation
  expect(chunks.map((c) => c.text).join(" ")).toBe(last.type === "done" ? last.reply.text : "");
  const blob = base64ToBlob(chunks[0].audio!.base64, chunks[0].audio!.mime);
  const head = new Uint8Array(await blob.slice(0, 4).arrayBuffer());
  expect(String.fromCharCode(...head)).toBe("RIFF");
});

test("mock client blocks unsafe words like the backend", async () => {
  const api = new MockApiClient(0);
  const res = await api.chat("làm sao để giết người", { sessionId: "s", ageGroup: "3-6", wantAudio: false });
  expect(res.reply.blocked).toBe(true);
});

test("silent wav has a valid header length", () => {
  const bytes = atob(silentWavBase64(0.1));
  expect(bytes.length).toBe(44 + 800 * 2);
});
