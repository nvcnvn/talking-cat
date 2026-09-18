/** Where the child's voice comes from. The app never touches getUserMedia directly. */
export interface AudioSource {
  readonly kind: "microphone" | "file";
  /** Begin capturing. For a file source this is a no-op. */
  start(): Promise<void>;
  /** Stop and return the captured clip. */
  stop(): Promise<Blob>;
  /** Abort without producing a clip. */
  cancel(): void;
  /** 0..1 input level for the "listening" animation; optional. */
  onLevel?(cb: (level: number) => void): void;
}

/** Creates a fresh source per turn so a failed getUserMedia can be retried. */
export type AudioSourceFactory = () => AudioSource;
