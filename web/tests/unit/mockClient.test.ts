// @vitest-environment node
import { base64ToBlob } from "../../src/api/client";
import { MockApiClient, silentWavBase64 } from "../../src/api/mockClient";

test("mock client honours #transcript files and produces playable wav", async () => {
  const api = new MockApiClient(0);
  const res = await api.talk(new Blob(["#transcript: em thích mèo\n"], { type: "text/plain" }), { sessionId: "s", ageGroup: "3-6", wantAudio: true });
  expect(res.transcript.text).toBe("em thích mèo");
  expect(res.reply.text).toContain("em thích mèo");
  const blob = base64ToBlob(res.audio!.base64, res.audio!.mime);
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
