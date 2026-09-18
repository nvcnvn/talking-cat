/** Decides when the child has finished talking, from the mic level alone.
 *
 * Pure: it is fed (level, timestamp) and answers with a verdict, so it unit-tests
 * without audio or timers. Thresholds are knobs because rooms differ — a noisy
 * living room needs a higher `threshold` than a bedroom (see RuntimeConfig).
 */
export interface EndpointerOptions {
  /** 0..1 mic level at or above which we call it speech. */
  threshold: number;
  /** Quiet time after real speech that ends the turn. */
  silenceMs: number;
  /** Total voiced time required before silence can end the turn (ignores coughs, taps). */
  minSpeechMs: number;
  /** Give up if the child never says anything. */
  noSpeechMs: number;
}

export const DEFAULT_ENDPOINTER: EndpointerOptions = {
  threshold: 0.12,
  silenceMs: 1200,
  minSpeechMs: 350,
  noSpeechMs: 6000,
};

export type Endpoint = "listening" | "done" | "no-speech";

/** Returns a `feed(level, now)` function; call it as often as levels arrive. */
export function createEndpointer(o: EndpointerOptions, startedAt: number) {
  let voicedMs = 0;
  let lastLoudAt = startedAt;
  let lastAt = startedAt;

  return function feed(level: number, now: number): Endpoint {
    const dt = Math.max(0, now - lastAt);
    lastAt = now;
    if (level >= o.threshold) {
      voicedMs += dt;
      lastLoudAt = now;
    }
    if (voicedMs < o.minSpeechMs) return now - startedAt >= o.noSpeechMs ? "no-speech" : "listening";
    return now - lastLoudAt >= o.silenceMs ? "done" : "listening";
  };
}
