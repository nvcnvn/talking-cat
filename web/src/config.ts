import type { EndpointerOptions } from "./audio/endpointer";

/** Runtime flags from the URL. Nothing here is compiled in, so tests can flip them. */
export type InputMode = "mic" | "file";
export type ApiMode = "http" | "mock";

export interface RuntimeConfig {
  api: ApiMode;
  input: InputMode;
  playAudio: boolean;
  apiBase: string;
  testMode: boolean;
  /** Silence-detection overrides: ?vadThreshold=0.2&vadNoise=3 for a noisy room,
   * ?vadMax=60000 for a child who describes things at length. */
  endpointer: Partial<EndpointerOptions>;
  /** Re-open the mic after each reply; ?hands=off for tap-per-turn. */
  handsFree: boolean;
}

function num(raw: string | null, key: keyof EndpointerOptions, into: Partial<EndpointerOptions>): Partial<EndpointerOptions> {
  const v = raw === null ? NaN : Number(raw);
  return Number.isFinite(v) ? { ...into, [key]: v } : into;
}

export function readConfig(search: string = window.location.search): RuntimeConfig {
  const q = new URLSearchParams(search);
  const testMode = q.get("test") === "1";
  return {
    api: q.get("api") === "mock" ? "mock" : "http",
    input: q.get("input") === "file" || testMode ? "file" : "mic",
    playAudio: q.get("audio") !== "off",
    apiBase: q.get("apiBase") || "",
    testMode,
    endpointer: num(
      q.get("vadThreshold"),
      "threshold",
      num(q.get("vadSilence"), "silenceMs", num(q.get("vadNoise"), "noiseRatio", num(q.get("vadMax"), "maxMs", {}))),
    ),
    handsFree: q.get("hands") !== "off",
  };
}
