import type { Severity } from "../api/client";
import styles from "./SeverityText.module.css";

/** Severity as a word; red only for high and critical, so colour is never the only signal. */
export function SeverityText({ severity }: { severity: Severity | null | undefined }) {
  if (!severity) return <span className={styles.none}>No severity</span>;
  const urgent = severity === "critical" || severity === "high";
  return (
    <span className={styles.severity} data-urgent={urgent ? "" : undefined}>
      {severity.toUpperCase()}
    </span>
  );
}
