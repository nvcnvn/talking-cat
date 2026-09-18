import { defineConfig } from "@playwright/test";

// Two ways to run:
//   default            -> starts `vite preview` and mocks /api in the browser (no backend needed)
//   E2E_BASE_URL=...   -> hits an already running stack (e.g. docker compose with fake providers)
const external = process.env.E2E_BASE_URL;

export default defineConfig({
  testDir: "tests/e2e",
  timeout: 30_000,
  use: {
    baseURL: external || "http://localhost:4173",
    // Fake microphone so the "real mic" path can also be exercised with a file.
    launchOptions: {
      args: ["--use-fake-ui-for-media-stream", "--use-fake-device-for-media-stream"],
    },
  },
  webServer: external
    ? undefined
    : { command: "npm run build && npm run preview", url: "http://localhost:4173", reuseExistingServer: true, timeout: 120_000 },
});
