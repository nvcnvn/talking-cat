import type { AudioSource } from "./AudioSource";

/** A prerecorded clip (or a "#transcript:" text file for fake STT). Used by tests and the demo panel. */
export class FileSource implements AudioSource {
  readonly kind = "file" as const;
  constructor(private file: Blob) {}
  async start() {}
  async stop() {
    return this.file;
  }
  cancel() {}
}
