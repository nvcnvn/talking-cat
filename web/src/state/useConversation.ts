import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import type { AgeGroup, ApiClient } from "../api/client";
import { base64ToBlob } from "../api/client";
import type { AudioPlayer } from "../audio/AudioPlayer";
import type { AudioSource, AudioSourceFactory } from "../audio/AudioSource";
import { createEndpointer, DEFAULT_ENDPOINTER, type EndpointerOptions } from "../audio/endpointer";
import { pickThinkingIndex, THINKING_COUNT } from "../audio/thinking";
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
  /** How many "let me think" fillers exist; 0 turns them off. */
  thinkingCount?: number;
  /** Re-open the mic by itself after the cat finishes, so a small child never has to tap again. */
  autoListen?: boolean;
}

export interface ConversationController {
  state: ConversationState;
  level: number; // 0..1 mouth/ear level
  ageGroup: AgeGroup;
  setAgeGroup(a: AgeGroup): void;
  startListening(): Promise<void>;
  /** Cut the cat off and start listening in one tap. */
  bargeIn(): Promise<void>;
  stopListening(opts?: { noSpeech?: boolean }): Promise<void>;
  /** Run a full turn from a prerecorded clip (or "#transcript:" text file). */
  submitClip(clip: Blob): Promise<void>;
  submitText(text: string): Promise<void>;
  interrupt(): void;
  reset(): Promise<void>;
}

/** At ~1.5s each this covers the measured 3-7s wait; more would sound like stalling. */
const MAX_FILLERS = 3;

/** Hands-free: how many turns with nothing said before the cat stops re-opening the mic.
 * Without this the app would listen forever after the child walks away. */
const MAX_IDLE_TURNS = 2;
/** Let the speaker settle before the mic opens again, so the cat does not hear its own tail.
 * Short on purpose: the mic stream is already warm, and every ms here is a ms in which the
 * child talks to a mic that is not recording. Echo cancellation covers the tail. */
const RELISTEN_DELAY_MS = 120;

const FRIENDLY_ERROR = "Meo, Miu không nghe được. Bạn thử lại nhé!";

export function useConversation(deps: ConversationDeps): ConversationController {
  const [state, dispatch] = useReducer(reduce, undefined, () => initialState());
  const [level, setLevel] = useState(0);
  const [ageGroup, setAgeGroup] = useState<AgeGroup>(() => (localStorage.getItem("ageGroup") as AgeGroup) || "3-6");
  const source = useRef<AudioSource | null>(null);
  const timer = useRef(0);
  const relisten = useRef(0);
  const armed = useRef(false); // hands-free loop is running
  const idleTurns = useRef(0); // consecutive turns where the child said nothing
  const startRef = useRef<(force?: boolean) => Promise<void>>();
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

  /** Hands-free: open the mic again once the cat has finished, unless the child has gone quiet. */
  const maybeRelisten = useCallback(() => {
    if (deps.autoListen === false || !armed.current) return;
    if (idleTurns.current >= MAX_IDLE_TURNS) {
      armed.current = false;
      return;
    }
    relisten.current = window.setTimeout(() => armed.current && void startRef.current?.(), RELISTEN_DELAY_MS);
  }, [deps.autoListen]);

  const runTurn = useCallback(
    async (clip: Blob) => {
      // Sentences arrive while the LLM is still writing: queue them and play in order, never
      // making the reader wait for playback. Until the first real sentence is ready, the gap is
      // filled with "ummm, let me think" clips so the cat is never just silent.
      const queue: { blob: Blob | null; text: string }[] = [];
      const clipCount = deps.thinkingCount ?? THINKING_COUNT;
      let draining: Promise<void> | null = null;
      let answering = false; // true once the real reply starts, or the turn is over
      let fillersLeft = deps.playAudio && clipCount > 0 ? MAX_FILLERS : 0;

      const nextFiller = async (): Promise<Blob | null> => {
        try {
          return await deps.api.thinking(pickThinkingIndex(clipCount));
        } catch {
          return null; // a missing filler is not a failure of the turn
        }
      };

      const drain = async () => {
        for (;;) {
          if (!queue.length) {
            if (answering || fillersLeft <= 0) break;
            fillersLeft--;
            const blob = await nextFiller();
            if (!blob || answering) continue;
            queue.push({ blob, text: "" });
          }
          const next = queue.shift()!;
          await deps.player.play(next.blob ?? new Blob([next.text], { type: "text/plain" }), setLevel).catch(() => {});
        }
        setLevel(0);
        draining = null;
      };

      let heard = "";
      try {
        draining = drain();
        await deps.api.talkStream(clip, { sessionId: stateRef.current.sessionId, ageGroup, wantAudio: deps.playAudio }, (e) => {
          if (e.type === "transcript") {
            heard = e.transcript.text;
            dispatch({ type: "HEARD", text: heard });
          } else if (e.type === "chunk") {
            answering = true;
            dispatch({ type: "REPLY_CHUNK", text: e.text });
            queue.push({ blob: e.audio && deps.playAudio ? base64ToBlob(e.audio.base64, e.audio.mime) : null, text: e.text });
            draining ??= drain();
          } else {
            dispatch({ type: "RESULT", heard, reply: e.reply.text, blocked: e.reply.blocked });
          }
        });
        answering = true; // nothing more is coming: stop topping up fillers
        await draining;
        dispatch({ type: "SPEAK_END" });
        idleTurns.current = 0;
        maybeRelisten();
      } catch (e) {
        answering = true;
        armed.current = false; // an error ends the hands-free loop: the child taps to try again
        console.error(e);
        dispatch({ type: "FAIL", message: FRIENDLY_ERROR });
      }
    },
    [deps.api, deps.player, deps.playAudio, deps.thinkingCount, ageGroup, maybeRelisten],
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
        idleTurns.current += 1;
        maybeRelisten();
        return;
      }
      await runTurn(clip);
    } catch (e) {
      armed.current = false;
      console.error(e);
      dispatch({ type: "FAIL", message: FRIENDLY_ERROR });
    }
  }, [runTurn, speak, maybeRelisten]);

  const startListening = useCallback(async (force = false) => {
    if (!force && !canListen(stateRef.current)) return;
    deps.player.unlock();
    const src = deps.makeSource();
    const vad = { ...DEFAULT_ENDPOINTER, ...deps.endpointer };
    const endpointer = createEndpointer(vad, Date.now());
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
    armed.current = deps.autoListen !== false;
    dispatch({ type: "LISTEN_START" });
    // The endpointer owns the real ceiling (it knows whether the child is still talking);
    // this timer only covers a source that never reports a level at all.
    timer.current = window.setTimeout(() => void stopListening(), deps.maxListenMs ?? vad.maxMs + 3000);
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
    armed.current = false; // tapping the cat ends the hands-free loop
    clearTimeout(relisten.current);
    clearTimeout(timer.current);
    source.current?.cancel();
    source.current = null;
    deps.player.stop();
    setLevel(0);
    dispatch({ type: "INTERRUPT" });
  }, [deps.player]);

  /** The child taps while the cat is talking because they want to say something, not because
   * they want silence: stop the cat and open the mic in the same tap. */
  const bargeIn = useCallback(async () => {
    interrupt();
    await startListening(true);
  }, [interrupt, startListening]);

  const reset = useCallback(async () => {
    interrupt();
    await deps.api.clearSession(stateRef.current.sessionId).catch(() => {});
    dispatch({ type: "RESET", sessionId: newSessionId() });
  }, [deps.api, interrupt]);

  startRef.current = startListening;

  return { state, level, ageGroup, setAgeGroup, startListening, bargeIn, stopListening, submitClip, submitText, interrupt, reset };
}
