import { useMemo, useState, type ReactNode } from "react";

/** Simple arithmetic gate so small children cannot reach settings. */
export function ParentGate({ onClose, children }: { onClose(): void; children: ReactNode }) {
  const [a, b] = useMemo(() => [3 + Math.floor(Math.random() * 6), 3 + Math.floor(Math.random() * 6)], []);
  const [answer, setAnswer] = useState("");
  const [open, setOpen] = useState(false);
  const ok = Number(answer) === a * b;

  return (
    <div className="modal" role="dialog" aria-modal="true" data-testid="parent-gate">
      <div className="modal__card">
        {!open ? (
          <>
            <h2>Dành cho bố mẹ</h2>
            <p>
              Trả lời phép tính để mở: <strong>{a} × {b} = ?</strong>
            </p>
            <input
              inputMode="numeric"
              autoFocus
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && ok && setOpen(true)}
              data-testid="gate-input"
            />
            <div className="modal__row">
              <button type="button" onClick={onClose}>Đóng</button>
              <button type="button" className="primary" disabled={!ok} onClick={() => setOpen(true)} data-testid="gate-submit">
                Mở
              </button>
            </div>
          </>
        ) : (
          <>
            {children}
            <div className="modal__row">
              <button type="button" className="primary" onClick={onClose}>Xong</button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
