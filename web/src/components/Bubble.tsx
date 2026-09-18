interface Props {
  heard: string;
  reply: string;
  blocked: boolean;
  error: string | null;
}

export function Bubble({ heard, reply, blocked, error }: Props) {
  const text = error ?? reply ?? "";
  return (
    <div className="bubbles">
      {heard && (
        <p className="bubble bubble--kid" data-testid="heard">
          {heard}
        </p>
      )}
      {text && (
        <p className={`bubble bubble--cat ${blocked ? "bubble--gentle" : ""}`} data-testid="reply">
          {text}
        </p>
      )}
      {!heard && !text && (
        <p className="bubble bubble--cat bubble--hint" data-testid="reply">
          Chào bạn! Mình là Miu. Chạm vào nút micro rồi nói chuyện với Miu nhé!
        </p>
      )}
    </div>
  );
}
