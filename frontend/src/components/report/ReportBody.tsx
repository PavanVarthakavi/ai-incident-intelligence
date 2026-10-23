import type { DiagnosisOutput, DiagnosisRead } from "../../api/client";
import { elapsed, maybeUtcTime, seconds, usd } from "../../lib/format";
import { findingNumber, findings } from "../../lib/exhibits";
import { ExhibitTags } from "../exhibits/ExhibitTag";
import styles from "./Report.module.css";

/** Everything after the probable cause: summary, findings, timeline, actions. */
export function ReportBody({
  output,
  problems = new Map(),
}: {
  output: DiagnosisOutput;
  /** Citation problems by claim (see lib/validation), marked on the claim itself. */
  problems?: Map<string, string[]>;
}) {
  const rows = findings(output);
  const flag = (key: string | null) => (key ? problems.get(key) : undefined);
  return (
    <>
      {rows.length > 0 && (
        <Section title="Findings">
          <table className={styles.table}>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} data-kind={row.kind} data-flagged={flag(row.path) ? "" : undefined}>
                  <th scope="row" className={styles.number}>
                    {findingNumber(i)}
                  </th>
                  <td>
                    <b className={styles.lead}>{row.kind}.</b> {row.statement}
                    <Problems list={flag(row.path)} />
                  </td>
                  <td className={styles.refs}>
                    <ExhibitTags ids={row.evidence_ids} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}

      <Section title="Summary">
        <p className={styles.summary}>{output.summary}</p>
      </Section>

      {output.timeline.length > 0 && (
        <Section title="Timeline (UTC)">
          <table className={styles.table}>
            <tbody>
              {output.timeline.map((entry, i) => (
                <tr key={i} data-flagged={flag(`timeline:${i}`) ? "" : undefined}>
                  <th scope="row" className={styles.time}>
                    {maybeUtcTime(entry.time)}
                  </th>
                  <td>
                    {entry.event}
                    <Problems list={flag(`timeline:${i}`)} />
                  </td>
                  <td className={styles.refs}>
                    <ExhibitTags ids={entry.evidence_ids} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Section>
      )}

      {output.recommended_actions.length > 0 && (
        <Section title="Recommended actions">
          <ol className={styles.actions}>
            {output.recommended_actions.map((action, i) => (
              <li key={i} data-flagged={flag(`recommended_actions:${i}`) ? "" : undefined}>
                <div>
                  <p className={styles.action}>{action.action}</p>
                  <p className={styles.rationale}>{action.rationale}</p>
                  <Problems list={flag(`recommended_actions:${i}`)} />
                </div>
                <span className={styles.refs}>
                  <ExhibitTags ids={action.evidence_ids} />
                </span>
              </li>
            ))}
          </ol>
        </Section>
      )}
    </>
  );
}

/** Who produced the diagnosis, at what cost, from which prompt. */
export function Provenance({ diagnosis }: { diagnosis: DiagnosisRead }) {
  const took = elapsed(diagnosis.created_at, diagnosis.completed_at);
  const parts = [
    diagnosis.effort === "none"
      ? (diagnosis.model_used ?? diagnosis.model_requested)
      : `${diagnosis.model_used ?? diagnosis.model_requested}, ${diagnosis.effort} effort`,
    diagnosis.fallback_used ? "answered by the fallback model" : null,
    `cost ${usd(diagnosis.cost_usd)}`,
    took !== null ? `took ${seconds(took)}` : null,
    `prompt v${diagnosis.prompt_version}`,
    `${diagnosis.input_tokens.toLocaleString("en-US")} tokens in, ${diagnosis.output_tokens.toLocaleString("en-US")} out`,
  ].filter(Boolean);
  return <p className={styles.provenance}>{parts.join(" \u00b7 ")}</p>;
}

function Problems({ list }: { list: string[] | undefined }) {
  if (!list) return null;
  return <span className={styles.problem}>Citation problem: {list.join("; ")}</span>;
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className={styles.section}>
      <h2 className={styles.sectionTitle}>{title}</h2>
      {children}
    </section>
  );
}
