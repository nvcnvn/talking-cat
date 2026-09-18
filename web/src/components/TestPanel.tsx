import { useState } from "react";

interface Props {
  onClip(clip: Blob): void;
  onText(text: string): void;
  busy: boolean;
}

/** Visible with ?test=1 or ?input=file. Lets you drive a turn from a file or typed transcript. */
export function TestPanel({ onClip, onText, busy }: Props) {
  const [transcript, setTranscript] = useState("");
  return (
    <section className="testpanel" data-testid="test-panel">
      <h3>Chế độ kiểm thử</h3>
      <label>
        Gửi file âm thanh (wav/webm/mp3) hoặc file .txt bắt đầu bằng <code>#transcript:</code>
        <input
          type="file"
          accept="audio/*,.txt,text/plain"
          data-testid="file-input"
          disabled={busy}
          onChange={(e) => {
            const f = e.target.files?.[0];
            if (f) onClip(f);
            e.target.value = "";
          }}
        />
      </label>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          if (!transcript.trim()) return;
          onClip(new Blob([`#transcript: ${transcript.trim()}\n`], { type: "text/plain" }));
          setTranscript("");
        }}
      >
        <input
          placeholder="Giả lập lời bé nói (đi qua STT giả)"
          value={transcript}
          onChange={(e) => setTranscript(e.target.value)}
          data-testid="fake-transcript"
          disabled={busy}
        />
        <button type="submit" disabled={busy} data-testid="fake-transcript-send">Gửi như giọng nói</button>
      </form>
      <button type="button" disabled={busy} onClick={() => onText("Miu ơi, con mèo kêu thế nào?")} data-testid="sample-text">
        Gửi câu hỏi mẫu qua /chat
      </button>
    </section>
  );
}
