import type { ApiClient } from "./api/client";
import { HttpApiClient } from "./api/httpClient";
import { MockApiClient } from "./api/mockClient";
import { HtmlAudioPlayer, SilentPlayer, type AudioPlayer } from "./audio/AudioPlayer";
import type { AudioSourceFactory } from "./audio/AudioSource";
import { MicrophoneSource } from "./audio/MicrophoneSource";
import { readConfig, type RuntimeConfig } from "./config";

export interface Runtime {
  config: RuntimeConfig;
  api: ApiClient;
  player: AudioPlayer;
  makeSource: AudioSourceFactory;
}

/** Composition root for the browser: picks real or fake pieces from URL flags. */
export function createRuntime(config: RuntimeConfig = readConfig()): Runtime {
  const api = config.api === "mock" ? new MockApiClient() : new HttpApiClient(config.apiBase);
  const player = config.playAudio ? new HtmlAudioPlayer() : new SilentPlayer();
  const makeSource: AudioSourceFactory = () => new MicrophoneSource();
  return { config, api, player, makeSource };
}
