/** Short "ummm, let me think" fillers covering the wait before the cat's first sentence.
 *
 * The audio comes from the backend (`GET /api/thinking/{i}`), synthesised with the same TTS
 * provider as the reply itself - a filler in a different voice sounds like a different cat.
 */
/** The backend owns the list of lines and wraps any index it is given, so the client just rolls
 * a die over a wide range: adding lines there needs no change here. 0 turns fillers off. */
export const THINKING_COUNT = 64;

export function pickThinkingIndex(count = THINKING_COUNT, rnd: () => number = Math.random): number {
  return Math.floor(rnd() * count) % count;
}
