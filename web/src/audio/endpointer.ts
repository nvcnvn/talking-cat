/** Decides when the child has finished talking, from the mic level alone.
 *
 * Pure: it is fed (level, timestamp) and answers with a verdict, so it unit-tests
 * without audio or timers. Thresholds are knobs because rooms differ — a noisy
 * living room needs a higher `threshold` than a bedroom (see RuntimeConfig).
 */
export interface EndpointerOptions {
  /** 0..1 mic level at or above which we call it speech, in a silent room. */
  threshold: number;
  /** Quiet time after real speech that ends the turn. */
  silenceMs: number;
  /** Total voiced time required before silence can end the turn (ignores coughs, taps). */
  minSpeechMs: number;
  /** Give up if the child never says anything. */
  noSpeechMs: number;
  /** Speech must also beat the room's own noise by this much. Gates a fan, a TV, a sibling
   * in the next room — without it steady noise reads as endless speech and gets uploaded. */
  noiseRatio: number;
  /** Hard ceiling on one turn. Only reached by a child who never pauses: an ordinary
   * pause ends the turn on `silenceMs` long before this. */
  maxMs: number;
}

export const DEFAULT_ENDPOINTER: EndpointerOptions = {
  threshold: 0.12,
  silenceMs: 1200,
  minSpeechMs: 350,
  noSpeechMs: 6000,
  noiseRatio: 2.5,
  maxMs: 45000,
};

/** The mic has just opened and the child has not started yet: learn the room fast. */
const FLOOR_SEED_MS = 300;
/** After that the floor drops instantly but climbs over ~3s, so a shout never becomes "ambient". */
const FLOOR_RISE_MS = 3000;
/** And it can never climb far enough to gate out a normal speaking voice. */
const FLOOR_MAX = 0.15;

export type Endpoint = "listening" | "done" | "no-speech";

/** Returns a `feed(level, now)` function; call it as often as levels arrive. */
export function createEndpointer(o: EndpointerOptions, startedAt: number) {
  let voicedMs = 0;
  let lastLoudAt = startedAt;
  let lastAt = startedAt;
  let floor = 0; // running estimate of the room's own noise

  return function feed(level: number, now: number): Endpoint {
    const dt = Math.max(0, now - lastAt);
    lastAt = now;
    floor = Math.min(
      FLOOR_MAX,
      now - startedAt < FLOOR_SEED_MS
        ? Math.max(floor, level)
        : level < floor
          ? level
          : floor + (level - floor) * Math.min(1, dt / FLOOR_RISE_MS),
    );
    if (level >= Math.max(o.threshold, floor * o.noiseRatio)) {
      voicedMs += dt;
      lastLoudAt = now;
    }
    if (voicedMs < o.minSpeechMs) return now - startedAt >= o.noSpeechMs ? "no-speech" : "listening";
    if (now - startedAt >= o.maxMs) return "done";
    return now - lastLoudAt >= o.silenceMs ? "done" : "listening";
  };
}
