import type { Phase } from "../state/conversation";

interface Props {
  phase: Phase;
  onStart(): void;
  onStop(): void;
  onInterrupt(): void;
}

const LABEL: Record<Phase, string> = {
  idle: "Chạm để nói",
  error: "Thử lại",
  listening: "Miu đang nghe... chạm để dừng",
  thinking: "Miu đang nghĩ...",
  speaking: "Miu đang nói",
};

export function TalkButton({ phase, onStart, onStop, onInterrupt }: Props) {
  const handler = phase === "listening" ? onStop : phase === "speaking" ? onInterrupt : phase === "thinking" ? undefined : onStart;
  return (
    <button
      type="button"
      className={`talk talk--${phase}`}
      data-testid="talk-button"
      onClick={handler}
      disabled={phase === "thinking"}
      aria-label={LABEL[phase]}
    >
      <span className="talk__icon" aria-hidden="true">
        {phase === "listening" ? "⏹" : phase === "speaking" ? "🔊" : phase === "thinking" ? "…" : "🎤"}
      </span>
      <span className="talk__label">{LABEL[phase]}</span>
    </button>
  );
}
