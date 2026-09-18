import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

// The real MicrophoneSource path, fed by Chromium's fake device from a WAV that is 1.5s of
// speech followed by nothing (%noloop). Nobody taps twice: the silence must end the turn.
const fixture = path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures", "speech-1.5s.wav");

test.use({
  launchOptions: {
    args: [
      "--use-fake-ui-for-media-stream",
      "--use-fake-device-for-media-stream",
      `--use-file-for-fake-audio-capture=${fixture}%noloop`,
    ],
  },
});

test("the child stops talking and the turn submits itself", async ({ page }) => {
  await page.goto("/?api=mock&audio=off");
  const cat = page.getByTestId("cat");

  await page.getByTestId("talk-button").click();
  await expect(cat).toHaveAttribute("data-phase", "listening");

  // No second click anywhere in this test.
  await expect(cat).toHaveAttribute("data-phase", /thinking|speaking/, { timeout: 8_000 });
  await expect(page.getByTestId("reply")).not.toHaveClass(/bubble--hint/, { timeout: 15_000 });
});

test("silence alone never reaches the backend", async ({ page }) => {
  const posts: string[] = [];
  // Real HTTP client, so a stray turn would show up as a request; nothing should reach it.
  await page.route("**/api/**", (r) => {
    posts.push(r.request().url());
    return r.abort();
  });
  // Levels are clamped to 1, so a threshold above 1 is unreachable: nobody ever spoke.
  await page.goto("/?audio=off&vadThreshold=2");
  const t0 = Date.now();
  await page.getByTestId("talk-button").click();
  // The exact "nothing was said" line, not the mic-permission or network error line.
  await expect(page.getByTestId("reply")).toContainText("chưa nghe rõ", { timeout: 12_000 });
  expect(Date.now() - t0).toBeGreaterThan(5_000); // it waited, rather than failing fast
  expect(posts).toHaveLength(0);
});

test("hands-free: the mic reopens after the cat answers, with no second tap", async ({ page }) => {
  test.setTimeout(60_000);
  const cat = page.getByTestId("cat");
  await page.goto("/?api=mock&audio=off");

  await page.getByTestId("talk-button").click(); // the only tap in this test
  await expect(cat).toHaveAttribute("data-phase", /thinking|speaking/, { timeout: 10_000 });
  await expect(cat).toHaveAttribute("data-phase", "listening", { timeout: 20_000 });
});

test("hands-free stops after two turns with nothing said, instead of listening forever", async ({ page }) => {
  test.setTimeout(90_000);
  const cat = page.getByTestId("cat");
  // Unreachable threshold: the child is present but never speaks (Chromium replays the fake
  // capture file on every getUserMedia, so silence has to come from the threshold instead).
  await page.goto("/?api=mock&audio=off&vadThreshold=2");

  await page.getByTestId("talk-button").click();
  await expect(page.getByTestId("reply")).toContainText("chưa nghe rõ", { timeout: 20_000 });

  // Idle between turns is transient, so require it to still be idle a few seconds later.
  await expect
    .poll(
      async () => {
        const before = await cat.getAttribute("data-phase");
        await page.waitForTimeout(3_000);
        return before === "idle" && (await cat.getAttribute("data-phase")) === "idle";
      },
      { timeout: 60_000, intervals: [1_000] },
    )
    .toBe(true);
});
