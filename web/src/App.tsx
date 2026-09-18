import { useState } from "react";
import { Bubble } from "./components/Bubble";
import { Cat } from "./components/Cat";
import { ParentGate } from "./components/ParentGate";
import { TalkButton } from "./components/TalkButton";
import { TestPanel } from "./components/TestPanel";
import type { Runtime } from "./runtime";
import { useConversation } from "./state/useConversation";

export function App({ runtime }: { runtime: Runtime }) {
  const { config } = runtime;
  const convo = useConversation({ api: runtime.api, makeSource: runtime.makeSource, player: runtime.player, playAudio: config.playAudio, endpointer: config.endpointer, autoListen: config.handsFree });
  const { state } = convo;
  const [gate, setGate] = useState(false);
  const [typing, setTyping] = useState(false);
  const [text, setText] = useState("");
  const busy = state.phase === "thinking" || state.phase === "speaking" || state.phase === "listening";

  return (
    <main className="app" data-phase={state.phase}>
      <header className="top">
        <span className="brand">Mèo Miu</span>
        <div className="top__actions">
          <button type="button" className="icon" aria-label="Bàn phím" onClick={() => setTyping((v) => !v)} data-testid="toggle-keyboard">⌨️</button>
          <button type="button" className="icon" aria-label="Cài đặt" onClick={() => setGate(true)} data-testid="open-settings">⚙️</button>
        </div>
      </header>

      <section className="stage">
        <Cat phase={state.phase} level={convo.level} />
        <Bubble heard={state.heard} reply={state.reply} blocked={state.blocked} error={state.error} />
      </section>

      <footer className="controls">
        {config.input === "mic" && (
          <TalkButton phase={state.phase} onStart={() => void convo.startListening()} onStop={() => void convo.stopListening()} onInterrupt={convo.interrupt} />
        )}
        {typing && (
          <form
            className="typebar"
            onSubmit={(e) => {
              e.preventDefault();
              void convo.submitText(text);
              setText("");
            }}
          >
            <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Gõ để nói với Miu..." disabled={busy} data-testid="text-input" autoFocus />
            <button type="submit" className="primary" disabled={busy || !text.trim()} data-testid="text-send">Gửi</button>
          </form>
        )}
        {config.input === "file" && <TestPanel onClip={(b) => void convo.submitClip(b)} onText={(t) => void convo.submitText(t)} busy={busy} />}
      </footer>

      {gate && (
        <ParentGate onClose={() => setGate(false)}>
          <h2>Cài đặt</h2>
          <label className="field">
            Độ tuổi của bé
            <select value={convo.ageGroup} onChange={(e) => convo.setAgeGroup(e.target.value as "3-6" | "7-12")} data-testid="age-select">
              <option value="3-6">3 đến 6 tuổi</option>
              <option value="7-12">7 đến 12 tuổi</option>
            </select>
          </label>
          <p className="muted">Số lượt đã nói chuyện: {state.turns}</p>
          <button type="button" onClick={() => void convo.reset()} data-testid="reset-session">Bắt đầu cuộc trò chuyện mới</button>
        </ParentGate>
      )}
    </main>
  );
}
