import { createEndpointer, DEFAULT_ENDPOINTER } from "../../src/audio/endpointer";

const opts = { ...DEFAULT_ENDPOINTER, threshold: 0.1, silenceMs: 1000, minSpeechMs: 300, noSpeechMs: 5000 };

/** Feeds levels at 100ms steps and returns the time (ms from start) of the first non-listening verdict. */
function run(levels: number[]): { verdict: string; atMs: number } {
  const feed = createEndpointer(opts, 0);
  for (let i = 0; i < levels.length; i++) {
    const v = feed(levels[i], (i + 1) * 100);
    if (v !== "listening") return { verdict: v, atMs: (i + 1) * 100 };
  }
  return { verdict: "listening", atMs: levels.length * 100 };
}

const quiet = (n: number) => Array(n).fill(0.02);
const speech = (n: number) => Array(n).fill(0.4);

test("submits one second after the child stops talking", () => {
  const r = run([...quiet(3), ...speech(10), ...quiet(30)]);
  expect(r.verdict).toBe("done");
  expect(r.atMs).toBe(2300); // 300ms quiet + 1000ms speech + 1000ms silence
});

test("keeps listening through a short pause mid-sentence", () => {
  expect(run([...speech(5), ...quiet(8), ...speech(5)]).verdict).toBe("listening");
});

test("a cough is not speech: it ends as no-speech, not a turn", () => {
  const r = run([...quiet(5), 0.5, 0.5, ...quiet(60)]);
  expect(r.verdict).toBe("no-speech");
  expect(r.atMs).toBe(5000);
});

test("silence from the start gives up after noSpeechMs", () => {
  expect(run(quiet(60))).toEqual({ verdict: "no-speech", atMs: 5000 });
});

test("a noisy room only ends the turn when its threshold is raised", () => {
  const noise = Array(40).fill(0.15);
  expect(run([...speech(5), ...noise]).verdict).toBe("listening");
  const feed = createEndpointer({ ...opts, threshold: 0.25 }, 0);
  let last = "listening";
  [...speech(5), ...noise].forEach((l, i) => (last = feed(l, (i + 1) * 100)));
  expect(last).toBe("done");
});
