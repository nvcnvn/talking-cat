import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import type { AgeGroup, ApiClient } from "../api/client";
import { base64ToBlob } from "../api/client";
import type { AudioPlayer } from "../audio/AudioPlayer";
import type { AudioSource, AudioSourceFactory } from "../audio/AudioSource";
import { createEndpointer, DEFAULT_ENDPOINTER, type EndpointerOptions } from "../audio/endpointer";
import { FileSource } from "../audio/FileSource";
import { canListen, initialState, newSessionId, reduce, type ConversationState } from "./conversation";

export interface ConversationDeps {
  api: ApiClient;
  makeSource: AudioSourceFactory;
  player: AudioPlayer;
  playAudio: boolean;
  maxListenMs?: number;
  /** Silence detection knobs; the turn ends by itself so the child never has to tap twice. */
  endpointer?: Partial<EndpointerOptions>;
}

export interface ConversationController {
  state: ConversationState;
  level: number; // 0..1 mouth/ear level
  ageGroup: AgeGroup;
  setAgeGroup(a: AgeGroup): void;
  startListening(): Promise<void>;
  stopListening(opts?: { noSpeech?: boolean }): Promise<void>;
  /** Run a full turn from a prerecorded clip (or "#transcript:" text file). */
  submitClip(clip: Blob): Promise<void>;
  submitText(text: string): Promise<void>;
  interrupt(): void;
  reset(): Promise<void>;
}

const FRIENDLY_ERROR = "Meo, Miu không nghe được. Bạn thử lại nhé!";

export function useConversation(deps: ConversationDeps): ConversationController {
  const [state, dispatch] = useReducer(reduce, undefined, () => initialState());
  const [level, setLevel] = useState(0);
  const [ageGroup, setAgeGroup] = useState<AgeGroup>(() => (localStorage.getItem("ageGroup") as AgeGroup) || "3-6");
  const source = useRef<AudioSource | null>(null);
  const timer = useRef(0);
  const stateRef = useRef(state);
  stateRef.current = state;

  useEffect(() => localStorage.setItem("ageGroup", ageGroup), [ageGroup]);

  const speak = useCallback(
    async (audio: { mime: string; base64: string } | null, text: string) => {
      dispatch({ type: "SPEAK_START" });
      if (audio && deps.playAudio) {
        try {
          await deps.player.play(base64ToBlob(audio.base64, audio.mime), setLevel);
        } catch {
          /* playback failure is not fatal: text is on screen */
        }
      } else {
        // No audio: keep the cat "speaking" long enough to read the bubble.
        await deps.player.play(new Blob([text], { type: "text/plain" }), setLevel).catch(() => {});
      }
      setLevel(0);
      dispatch({ type: "SPEAK_END" });
    },
    [deps.player, deps.playAudio],
  );

  const runTurn = useCallback(
    async (clip: Blob) => {
      try {
        const res = await deps.api.talk(clip, { sessionId: stateRef.current.sessionId, ageGroup, wantAudio: deps.playAudio });
        dispatch({ type: "RESULT", heard: res.transcript.text, reply: res.reply.text, blocked: res.reply.blocked });
        await speak(res.audio, res.reply.text);
      } catch (e) {
        console.error(e);
        dispatch({ type: "FAIL", message: FRIENDLY_ERROR });
      }
    },
    [deps.api, deps.playAudio, ageGroup, speak],
  );

  const stopListening = useCallback(async (opts?: { noSpeech?: boolean }) => {
    clearTimeout(timer.current);
    const src = source.current;
    source.current = null;
    if (!src || stateRef.current.phase !== "listening") return;
    dispatch({ type: "LISTEN_STOP" });
    setLevel(0);
    try {
      const clip = await src.stop();
      if (opts?.noSpeech || clip.size < 500) {
        // nothing was said, or too short to be speech (mic path only): no backend round-trip
        const msg = "Meo, Miu chưa nghe rõ. Bạn nói lại cho Miu nghe được không?";
        dispatch({ type: "RESULT", heard: "", reply: msg, blocked: false });
        await speak(null, msg);
        return;
      }
      await runTurn(clip);
    } catch (e) {
      console.error(e);
      dispatch({ type: "FAIL", message: FRIENDLY_ERROR });
    }
  }, [runTurn, speak]);

  const startListening = useCallback(async () => {
    if (!canListen(stateRef.current)) return;
    deps.player.unlock();
    const src = deps.makeSource();
    const endpointer = createEndpointer({ ...DEFAULT_ENDPOINTER, ...deps.endpointer }, Date.now());
    src.onLevel?.((l) => {
      setLevel(l);
      const verdict = endpointer(l, Date.now());
      if (verdict !== "listening") void stopListening({ noSpeech: verdict === "no-speech" });
    });
    try {
      await src.start();
    } catch (e) {
      console.error(e);
      dispatch({ type: "FAIL", message: "Miu cần được bật micro để nghe bạn. Nhờ bố mẹ giúp nhé!" });
      return;
    }
    source.current = src;
    dispatch({ type: "LISTEN_START" });
    timer.current = window.setTimeout(() => void stopListening(), deps.maxListenMs ?? 15_000);
  }, [deps, stopListening]);

  const submitClip = useCallback(
    async (clip: Blob) => {
      if (!canListen(stateRef.current)) return;
      deps.player.unlock();
      // Same path as the microphone, just a different AudioSource.
      const src: AudioSource = new FileSource(clip);
      await src.start();
      dispatch({ type: "LISTEN_START" });
      const blob = await src.stop();
      dispatch({ type: "LISTEN_STOP" });
      await runTurn(blob);
    },
    [deps.player, runTurn],
  );

  const submitText = useCallback(
    async (text: string) => {
      const t = text.trim();
      if (!t || !canListen(stateRef.current)) return;
      deps.player.unlock();
      dispatch({ type: "TEXT_SUBMIT", text: t });
      try {
        const res = await deps.api.chat(t, { sessionId: stateRef.current.sessionId, ageGroup, wantAudio: deps.playAudio });
        dispatch({ type: "RESULT", heard: t, reply: res.reply.text, blocked: res.reply.blocked });
        if (deps.playAudio) {
          const blob = await deps.api.tts(res.reply.text);
          dispatch({ type: "SPEAK_START" });
          try {
            await deps.player.play(blob, setLevel);
          } catch {
            /* ignore */
          }
          setLevel(0);
          dispatch({ type: "SPEAK_END" });
        } else {
          await speak(null, res.reply.text);
        }
      } catch (e) {
        console.error(e);
        dispatch({ type: "FAIL", message: FRIENDLY_ERROR });
      }
    },
    [deps, ageGroup, speak],
  );

  const interrupt = useCallback(() => {
    clearTimeout(timer.current);
    source.current?.cancel();
    source.current = null;
    deps.player.stop();
    setLevel(0);
    dispatch({ type: "INTERRUPT" });
  }, [deps.player]);

  const reset = useCallback(async () => {
    interrupt();
    await deps.api.clearSession(stateRef.current.sessionId).catch(() => {});
    dispatch({ type: "RESET", sessionId: newSessionId() });
  }, [deps.api, interrupt]);

  return { state, level, ageGroup, setAgeGroup, startListening, stopListening, submitClip, submitText, interrupt, reset };
}
