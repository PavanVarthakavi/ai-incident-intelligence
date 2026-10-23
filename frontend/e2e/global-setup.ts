import { execFileSync } from "node:child_process";
import { backendEnv, python } from "../playwright.config";

/** Migrates the test database and loads three evaluation cases into it, from empty. */
export default function globalSetup() {
  const options = {
    cwd: "../backend",
    env: { ...process.env, ...backendEnv },
    stdio: "inherit" as const,
  };
  execFileSync(python, ["-m", "alembic", "upgrade", "head"], options);
  execFileSync(python, ["-m", "eval.seed", "--reset", "F14", "F17", "H05"], options);
}
