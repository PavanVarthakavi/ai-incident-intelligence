import { useEffect, useState } from "react";
import type { DiagnosisRead } from "../../api/client";
import { capitalize, seconds } from "../../lib/format";
import { parseProblem } from "../../lib/validation";
import { ExhibitTags } from "../exhibits/ExhibitTag";
import styles from "./Report.module.css";

type Props = {
  diagnosis: DiagnosisRead | undefined;
  running: boolean;
  children?: React.ReactNode; // the run control, shown when there is no diagnosis yet
};

/** The probable cause, or the honest reason there is none. */
export function CauseBox({ diagnosis, running, children }: Props) {
  if (running) return <Running />;
  if (!diagnosis) {
    return (
      <Box label="Probable cause" tone="empty">
        <p className={styles.causeEmpty}>Not diagnosed yet.</p>
        {children && <div className={styles.causeAction}>{children}</div>}
      </Box>
    );
  }

  const { status, output } = diagnosis;
  if (status === "refused") {
    return (
      <Box label="Probable cause" tone="failed">
        <p className={styles.causeEmpty}>The model declined to diagnose this snapshot.</p>
        {diagnosis.error_message && <p className={styles.causeNote}>{diagnosis.error_message}</p>}
      </Box>
    );
  }
  if (status === "error" || !output) {
    return (
      <Box label="Probable cause" tone="failed">
        <p className={styles.causeEmpty}>The diagnosis failed before producing a result.</p>
        <p className={styles.causeNote}>
          {diagnosis.error_message ?? `The model stopped (${diagnosis.stop_reason ?? "unknown"}).`}
        </p>
      </Box>
    );
  }
  if (status === "running") {
    return (
      <Box label="Probable cause" tone="empty">
        <p className={styles.causeEmpty}>A diagnosis of this snapshot is still running.</p>
      </Box>
    );
  }

  const invalid = status === "invalid";
  const label = invalid ? "Probable cause, failed the citation check" : "Probable cause";
  const root = output.root_cause;

  return (
    <Box label={label} tone={invalid ? "invalid" : "valid"}>
      {root ? (
        <>
          <p className={styles.causeStatement}>{root.statement}</p>
          <div className={styles.causeFacts}>
            <span>
              Exhibits <ExhibitTags ids={root.evidence_ids} />
            </span>
            <span>
              Confidence <b>{capitalize(root.confidence)}</b>
            </span>
            {root.service && (
              <span>
                Service <b>{root.service}</b>
              </span>
            )}
          </div>
        </>
      ) : (
        <>
          <p className={styles.causeStatement}>No probable cause.</p>
          <p className={styles.causeNote}>The evidence does not point to a fault in this window.</p>
        </>
      )}
      {invalid && (
        <div className={styles.invalid} role="note">
          <p>
            Do not act on this diagnosis as written. The backend found claims whose citations do not
            hold:
          </p>
          <ul>
            {diagnosis.validation_errors.map(parseProblem).map((p) => (
              <li key={`${p.key}${p.problem}`}>
                <b>{p.label}:</b> {p.problem}
              </li>
            ))}
          </ul>
        </div>
      )}
    </Box>
  );
}

function Box({
  label,
  tone,
  children,
}: {
  label: string;
  tone: "valid" | "invalid" | "failed" | "empty";
  children: React.ReactNode;
}) {
  return (
    <section className={styles.cause} data-tone={tone} aria-label={label}>
      <h2 className={styles.causeLabel}>{label}</h2>
      {children}
    </section>
  );
}

function Running() {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const timer = setInterval(() => setElapsed((Date.now() - started) / 1000), 1000);
    return () => clearInterval(timer);
  }, []);
  return (
    <Box label="Probable cause" tone="empty">
      <p className={styles.causeEmpty} role="status">
        Diagnosing this snapshot. This usually takes 15 to 35 seconds.
      </p>
      <p className={styles.causeNote} aria-hidden="true">
        {seconds(elapsed)} elapsed
      </p>
    </Box>
  );
}
