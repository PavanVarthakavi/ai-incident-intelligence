import { execFileSync } from "node:child_process";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end tests against the real backend and a real PostgreSQL test database, with the
 * offline model so no run costs money. The database URL comes from E2E_DATABASE_URL, or the
 * backend's APP_TEST_DATABASE_URL setting; its name must end in "_test".
 */
const venv = resolve("../backend/.venv/bin/python");
const python = process.env.PYTHON ?? (existsSync(venv) ? venv : "python");

function databaseUrl(): string {
  if (process.env.E2E_DATABASE_URL) return process.env.E2E_DATABASE_URL;
  // Resolve APP_TEST_DATABASE_URL the way the backend's tests do (it may use ${...} references).
  const code =
    "from tests.conftest import _TestEnv; u = _TestEnv().test_database_url; " +
    "print(u.get_secret_value() if u else '')";
  const url = execFileSync(python, ["-c", code], { cwd: "../backend", encoding: "utf8" }).trim();
  if (!url) throw new Error("Set E2E_DATABASE_URL, or APP_TEST_DATABASE_URL in ../.env");
  return url;
}

const API_PORT = 8100;
const WEB_PORT = 5180;
const backendEnv = {
  APP_DATABASE_URL: databaseUrl(),
  APP_LLM_PROVIDER: "offline",
  APP_ENVIRONMENT: "test",
};

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  globalSetup: "./e2e/global-setup.ts",
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      // Locally, use the installed Chrome; CI installs Playwright's Chromium.
      use: { ...devices["Desktop Chrome"], channel: process.env.CI ? undefined : "chrome" },
    },
  ],
  webServer: [
    {
      command: `${python} -m uvicorn app.main:app --port ${API_PORT}`,
      cwd: "../backend",
      env: backendEnv,
      url: `http://127.0.0.1:${API_PORT}/health`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      command: `npx vite --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      env: { BACKEND_URL: `http://127.0.0.1:${API_PORT}` },
      url: `http://127.0.0.1:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 60_000,
    },
  ],
});

export { backendEnv, python };
