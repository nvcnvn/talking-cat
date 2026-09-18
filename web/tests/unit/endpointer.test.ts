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

test("room noise after speech is not mistaken for more speech", () => {
  // Steady 0.15 noise sits above the fixed threshold, but not above the learned floor.
  expect(run([...speech(5), ...Array(40).fill(0.15)])).toEqual({ verdict: "done", atMs: 1500 });
});

test("steady background noise alone never becomes a turn", () => {
  // The whole point: a fan or a TV must not upload 15s of nothing to the backend.
  expect(run(Array(80).fill(0.2)).verdict).toBe("no-speech");
});

test("a child who keeps talking is not cut off at the old 15s limit", () => {
  expect(run(speech(250)).verdict).toBe("listening"); // 25s, still going
  expect(run(speech(500))).toEqual({ verdict: "done", atMs: 45000 }); // hard ceiling only
});

test("the floor recovers if the child is already talking when the mic opens", () => {
  // Seeded high by their own voice, it drops on the first gap between syllables.
  expect(run([...speech(6), ...quiet(2), ...speech(6), ...quiet(20)]).verdict).toBe("done");
});

describe("mic opening mid-sentence", () => {
  it("hears a child already talking when the mic opens, at ordinary voice level", () => {
    // With no quiet frames to learn the room from, the floor was seeded from the child's own
    // voice; times noiseRatio that gated above them and the turn died as "no-speech".
    const feed = createEndpointer(DEFAULT_ENDPOINTER, 0);
    let verdict: ReturnType<typeof feed> = "listening";
    for (let t = 50; t <= 1000; t += 50) verdict = feed(0.28, t); // talking from the first frame
    expect(verdict).toBe("listening"); // speech, not room noise
    for (let t = 1050; t <= 2400; t += 50) verdict = feed(0.01, t); // then they stop
    expect(verdict).toBe("done");
  });
});
