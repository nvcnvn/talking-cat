import { expect, test } from "@playwright/test";
import path from "node:path";
import { fileURLToPath } from "node:url";

// With no E2E_BASE_URL the page uses the in-browser mock API (?api=mock).
// With E2E_BASE_URL pointing at docker compose (fake providers), it hits the real HTTP path.
const external = !!process.env.E2E_BASE_URL;
const mock = !external || process.env.E2E_MOCK === "1";
const url = (extra = "") => `/?test=1&audio=off${mock ? "&api=mock" : ""}${extra}`;
const fixture = (name: string) => path.join(path.dirname(fileURLToPath(import.meta.url)), "fixtures", name);

test("a prerecorded 'clip' goes through the whole turn and the cat animates", async ({ page }) => {
  await page.goto(url());
  const cat = page.getByTestId("cat");
  await expect(cat).toHaveAttribute("data-phase", "idle");

  await page.getByTestId("file-input").setInputFiles(fixture("elephant.txt"));
  await expect(cat).toHaveAttribute("data-phase", /thinking|speaking/);
  await expect(page.getByTestId("heard")).toHaveText("Miu ơi con voi kêu thế nào");
  await expect(page.getByTestId("reply")).toContainText("con voi");
  await expect(cat).toHaveAttribute("data-phase", "idle", { timeout: 10_000 });
});

test("unsafe input is redirected gently, never answered", async ({ page }) => {
  await page.goto(url());
  await page.getByTestId("file-input").setInputFiles(fixture("unsafe.txt"));
  const reply = page.getByTestId("reply");
  await expect(reply).toContainText("Miu", { timeout: 10_000 });
  await expect(reply).not.toContainText("giết");
  await expect(reply).toHaveClass(/bubble--gentle/);
});

test("typed transcript path and keyboard chat both work", async ({ page }) => {
  await page.goto(url());
  await page.getByTestId("fake-transcript").fill("em thích màu xanh");
  await page.getByTestId("fake-transcript-send").click();
  await expect(page.getByTestId("heard")).toHaveText("em thích màu xanh");
  await expect(page.getByTestId("cat")).toHaveAttribute("data-phase", "idle", { timeout: 10_000 });

  await page.getByTestId("toggle-keyboard").click();
  await page.getByTestId("text-input").fill("Miu ơi một cộng một bằng mấy");
  await page.getByTestId("text-send").click();
  await expect(page.getByTestId("heard")).toHaveText("Miu ơi một cộng một bằng mấy");
  await expect(page.getByTestId("reply")).not.toBeEmpty();
});

test("parent gate blocks settings until the sum is right", async ({ page }) => {
  await page.goto(url());
  await page.getByTestId("open-settings").click();
  const gate = page.getByTestId("parent-gate");
  const [a, b] = (await gate.locator("strong").innerText()).match(/\d+/g)!.map(Number);
  await expect(page.getByTestId("gate-submit")).toBeDisabled();
  await page.getByTestId("gate-input").fill(String(a * b));
  await page.getByTestId("gate-submit").click();
  await expect(page.getByTestId("age-select")).toBeVisible();
});

// Real providers only (make up && E2E_REAL=1): a synthesized Vietnamese question goes through
// Whisper, GLM and edge-tts in the browser, and the cat actually plays the reply.
test("real audio clip through the real pipeline", async ({ page }) => {
  test.skip(process.env.E2E_REAL !== "1", "needs the real stack");
  test.setTimeout(90_000);
  await page.goto("/?test=1"); // audio ON: exercises HtmlAudioPlayer too
  await page.getByTestId("file-input").setInputFiles(fixture("elephant.mp3"));
  const cat = page.getByTestId("cat");
  await expect(page.getByTestId("heard")).toContainText("voi", { timeout: 60_000 });
  await expect(page.getByTestId("reply")).not.toBeEmpty();
  await expect(cat).toHaveAttribute("data-phase", "speaking", { timeout: 30_000 });
  await expect(cat).toHaveAttribute("data-phase", "idle", { timeout: 30_000 });
});
