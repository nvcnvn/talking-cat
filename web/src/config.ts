/** Runtime flags from the URL. Nothing here is compiled in, so tests can flip them. */
export type InputMode = "mic" | "file";
export type ApiMode = "http" | "mock";

export interface RuntimeConfig {
  api: ApiMode;
  input: InputMode;
  playAudio: boolean;
  apiBase: string;
  testMode: boolean;
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
  };
}
