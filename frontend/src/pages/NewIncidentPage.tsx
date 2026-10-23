import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import type { Severity } from "../api/client";
import { useCreateIncident } from "../api/queries";
import styles from "./NewIncidentPage.module.css";

const PRESETS = [
  { minutes: 15, label: "Last 15 minutes" },
  { minutes: 30, label: "Last 30 minutes" },
  { minutes: 60, label: "Last hour" },
] as const;
const MAX_WINDOW_MS = 24 * 60 * 60 * 1000;

/** "2026-10-23T09:11" in UTC, the format a datetime-local input expects. */
const toInput = (date: Date) => date.toISOString().slice(0, 16);
const fromInput = (value: string) => new Date(`${value}:00Z`);

export function NewIncidentPage() {
  const navigate = useNavigate();
  const create = useCreateIncident();
  const [preset, setPreset] = useState<number | "custom">(15);
  const [start, setStart] = useState(() => toInput(new Date(Date.now() - 15 * 60_000)));
  const [end, setEnd] = useState(() => toInput(new Date()));
  const [problem, setProblem] = useState<string | null>(null);

  function windowFor(): { start: string; end: string } | string {
    if (preset !== "custom") {
      const now = Date.now();
      return {
        start: new Date(now - preset * 60_000).toISOString(),
        end: new Date(now).toISOString(),
      };
    }
    const s = fromInput(start);
    const e = fromInput(end);
    if (Number.isNaN(s.getTime()) || Number.isNaN(e.getTime())) return "Enter a start and an end.";
    if (e <= s) return "The end must be after the start.";
    if (e.getTime() - s.getTime() > MAX_WINDOW_MS) return "The window can be at most 24 hours.";
    return { start: s.toISOString(), end: e.toISOString() };
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const range = windowFor();
    if (typeof range === "string") {
      setProblem(range);
      return;
    }
    setProblem(null);
    const services = String(form.get("services") ?? "")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    const severity = String(form.get("severity") ?? "");
    create.mutate(
      {
        title: String(form.get("title") ?? ""),
        description: String(form.get("description") ?? "").trim() || null,
        severity: severity ? (severity as Severity) : null,
        window: range,
        services: services.length ? services : null,
        collect_evidence: true,
      },
      { onSuccess: (incident) => navigate(`/incidents/${incident.id}`) },
    );
  }

  return (
    <section className={styles.sheet}>
      <h1 className={styles.title}>New incident</h1>
      <p className={styles.intro}>
        The backend collects metrics, traces, logs, and deploys for the window into a snapshot.
        Collecting is free; diagnosing it is a separate, paid step.
      </p>
      <form className={styles.form} onSubmit={submit}>
        <div className={styles.field}>
          <label htmlFor="title">What is wrong</label>
          <input
            id="title"
            name="title"
            required
            maxLength={200}
            placeholder="Checkout requests are failing"
            autoComplete="off"
          />
        </div>

        <div className={styles.field}>
          <label htmlFor="severity">Severity</label>
          <select id="severity" name="severity" defaultValue="">
            <option value="">Not set</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>

        <fieldset className={styles.field}>
          <legend>Window (UTC)</legend>
          <div className={styles.presets}>
            {PRESETS.map((p) => (
              <label key={p.minutes} className={styles.choice}>
                <input
                  type="radio"
                  name="preset"
                  checked={preset === p.minutes}
                  onChange={() => setPreset(p.minutes)}
                />
                {p.label}
              </label>
            ))}
            <label className={styles.choice}>
              <input
                type="radio"
                name="preset"
                checked={preset === "custom"}
                onChange={() => setPreset("custom")}
              />
              Custom
            </label>
          </div>
          {preset === "custom" && (
            <div className={styles.range}>
              <label>
                Start
                <input
                  type="datetime-local"
                  value={start}
                  onChange={(e) => setStart(e.target.value)}
                  required
                />
              </label>
              <label>
                End
                <input
                  type="datetime-local"
                  value={end}
                  onChange={(e) => setEnd(e.target.value)}
                  required
                />
              </label>
            </div>
          )}
          <p className={styles.hint}>At most 24 hours. Times are UTC.</p>
        </fieldset>

        <div className={styles.field}>
          <label htmlFor="services">Services</label>
          <input
            id="services"
            name="services"
            placeholder="All services"
            aria-describedby="services-hint"
            autoComplete="off"
          />
          <p id="services-hint" className={styles.hint}>
            Optional. Comma-separated, for example: orders, inventory.
          </p>
        </div>

        <div className={styles.field}>
          <label htmlFor="description">What was reported</label>
          <textarea
            id="description"
            name="description"
            rows={3}
            maxLength={5000}
            aria-describedby="description-hint"
          />
          <p id="description-hint" className={styles.hint}>
            Optional. Shown to the model as the reporter&apos;s words; it may be wrong.
          </p>
        </div>

        {(problem || create.error) && (
          <p className={styles.error} role="alert">
            {problem ?? create.error?.message}
          </p>
        )}

        <div className={styles.submit}>
          <button type="submit" disabled={create.isPending}>
            {create.isPending ? "Collecting evidence..." : "Create and collect evidence"}
          </button>
        </div>
      </form>
    </section>
  );
}
