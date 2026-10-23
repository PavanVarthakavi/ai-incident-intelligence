import { useMemo, useState } from "react";
import { useParams, useSearchParams } from "react-router";
import type { BudgetRead, DiagnosisRead, IncidentRead, SnapshotRead } from "../api/client";
import {
  useBudget,
  useCollectSnapshot,
  useDiagnoses,
  useIncident,
  useRunDiagnosis,
  useSnapshot,
} from "../api/queries";
import { ExhibitProvider } from "../components/exhibits/ExhibitContext";
import { Exhibits } from "../components/exhibits/Exhibits";
import { CauseBox } from "../components/report/CauseBox";
import { Provenance, ReportBody } from "../components/report/ReportBody";
import { PageStatus } from "../components/PageStatus";
import { SeverityText } from "../components/SeverityText";
import { citedBy } from "../lib/exhibits";
import { count, usd, utcTime, utcWindow } from "../lib/format";
import { problemsByClaim } from "../lib/validation";
import styles from "./IncidentPage.module.css";

export function IncidentPage() {
  const { id = "" } = useParams();
  const incident = useIncident(id);

  if (incident.isPending) return <PageStatus>Loading the incident...</PageStatus>;
  if (incident.isError) return <PageStatus error={incident.error} subject="incident" />;
  return <IncidentReport incident={incident.data} />;
}

function IncidentReport({ incident }: { incident: IncidentRead }) {
  const [params, setParams] = useSearchParams();
  const snapshots = incident.snapshots;
  const snapshotId = params.get("snapshot") ?? snapshots.at(-1)?.id;
  const snapshot = useSnapshot(incident.id, snapshotId);
  const diagnoses = useDiagnoses(incident.id, snapshotId);
  const diagnosis =
    diagnoses.data?.find((d) => d.id === params.get("diagnosis")) ?? diagnoses.data?.[0];
  const cited = useMemo(
    () => (diagnosis?.output ? citedBy(diagnosis.output) : new Map()),
    [diagnosis],
  );

  const select = (key: "snapshot" | "diagnosis", value: string) =>
    setParams(
      (current) => {
        const next = new URLSearchParams(current);
        next.set(key, value);
        if (key === "snapshot") next.delete("diagnosis");
        return next;
      },
      { replace: true },
    );

  return (
    <ExhibitProvider evidence={snapshot.data?.evidence ?? []} citedBy={cited}>
      <article className={styles.sheet}>
        <div className={styles.report}>
          <h1 className={styles.title}>{incident.title}</h1>
          <p className={styles.meta}>
            <SeverityText severity={incident.severity} />
            <span>{utcWindow(incident.window.start, incident.window.end)}</span>
            {snapshot.data && <span>{sourceLine(snapshot.data)}</span>}
            <Validity diagnosis={diagnosis} />
          </p>
          <div className={styles.ids}>
            <span>
              Incident <code>{incident.id.slice(0, 8)}</code>
            </span>
            {snapshots.length > 0 && snapshotId && (
              <label>
                Snapshot{" "}
                <select value={snapshotId} onChange={(e) => select("snapshot", e.target.value)}>
                  {snapshots.map((s, i) => (
                    <option key={s.id} value={s.id}>
                      {i + 1} of {snapshots.length}, collected {utcTime(s.collected_at)}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {diagnoses.data && diagnosis && diagnoses.data.length > 1 ? (
              <label>
                Diagnosis{" "}
                <select value={diagnosis.id} onChange={(e) => select("diagnosis", e.target.value)}>
                  {diagnoses.data.map((d, i) => (
                    <option key={d.id} value={d.id}>
                      {diagnoses.data.length - i} of {diagnoses.data.length}, {d.status},{" "}
                      {utcTime(d.created_at)}
                    </option>
                  ))}
                </select>
              </label>
            ) : (
              diagnosis && <span>Diagnosis 1 of 1</span>
            )}
          </div>
          {incident.description && <Reported text={incident.description} />}

          {snapshots.length === 0 ? (
            <NoSnapshot incidentId={incident.id} />
          ) : snapshot.isError ? (
            <PageStatus error={snapshot.error} subject="snapshot" inline />
          ) : diagnoses.isError ? (
            <PageStatus error={diagnoses.error} subject="diagnoses" inline />
          ) : snapshot.data && diagnoses.data ? (
            <Diagnosis
              incidentId={incident.id}
              snapshotId={snapshot.data.id}
              evidenceCount={snapshot.data.evidence_count}
              diagnosis={diagnosis}
            />
          ) : (
            <PageStatus inline>Loading the evidence...</PageStatus>
          )}
        </div>
        <aside className={styles.exhibits}>
          {snapshot.data && <Exhibits snapshot={snapshot.data} />}
        </aside>
      </article>
    </ExhibitProvider>
  );
}

function Diagnosis({
  incidentId,
  snapshotId,
  evidenceCount,
  diagnosis,
}: {
  incidentId: string;
  snapshotId: string;
  evidenceCount: number;
  diagnosis: DiagnosisRead | undefined;
}) {
  const run = useRunDiagnosis(incidentId, snapshotId);
  const collect = useCollectSnapshot(incidentId);
  const [, setParams] = useSearchParams();
  const budget = useBudget();

  const collectControl = (
    <div className={styles.control}>
      <button
        type="button"
        className={styles.secondary}
        disabled={collect.isPending}
        onClick={() =>
          collect.mutate(undefined, {
            onSuccess: (created) =>
              setParams((p) => {
                const next = new URLSearchParams(p);
                next.set("snapshot", created.id);
                next.delete("diagnosis");
                return next;
              }),
          })
        }
      >
        {collect.isPending ? "Collecting..." : "Collect a new snapshot"}
      </button>
      <p className={styles.controlNote}>
        Free. Queries the same window again; this snapshot stays as it is.
      </p>
      {collect.error && <p className={styles.controlError}>{collect.error.message}</p>}
    </div>
  );

  const runControl = (
    <RunControl
      label={diagnosis ? "Run the diagnosis again" : "Run diagnosis"}
      nothingToDiagnose={evidenceCount === 0}
      budget={budget.data}
      pending={run.isPending}
      onRun={() =>
        run.mutate(undefined, {
          onSuccess: (created) =>
            setParams((p) => {
              const next = new URLSearchParams(p);
              next.set("diagnosis", created.id);
              return next;
            }),
        })
      }
      error={run.error}
    />
  );

  return (
    <>
      <CauseBox diagnosis={diagnosis} running={run.isPending}>
        <div className={styles.controlRow}>
          {runControl}
          {evidenceCount === 0 && collectControl}
        </div>
      </CauseBox>
      {!run.isPending && diagnosis?.output && (
        <ReportBody
          output={diagnosis.output}
          problems={problemsByClaim(diagnosis.validation_errors)}
        />
      )}
      {diagnosis && (
        <div className={styles.controls}>
          {runControl}
          {collectControl}
        </div>
      )}
      {diagnosis && !run.isPending && <Provenance diagnosis={diagnosis} />}
    </>
  );
}

function RunControl({
  label,
  nothingToDiagnose,
  budget,
  pending,
  onRun,
  error,
}: {
  label: string;
  nothingToDiagnose: boolean;
  budget: BudgetRead | undefined;
  pending: boolean;
  onRun: () => void;
  error: Error | null;
}) {
  const enabled = budget?.enabled ?? true;
  return (
    <div className={styles.control}>
      <button
        type="button"
        className={styles.primary}
        disabled={pending || !enabled || nothingToDiagnose}
        onClick={onRun}
      >
        {pending ? "Diagnosing..." : label}
      </button>
      <p className={styles.controlNote}>
        {nothingToDiagnose
          ? "Nothing to diagnose: this snapshot has no evidence. Collect a new one first."
          : !enabled
            ? "Diagnosis is off: the backend has no model configured."
            : budget
              ? `${budget.typical_cost_usd ? `Paid call, typically ${usd(budget.typical_cost_usd)}` : "Paid call"}. ${usd(budget.remaining_usd)} of today's ${usd(budget.limit_usd)} budget left.`
              : "Paid call."}
      </p>
      {error && (
        <p className={styles.controlError} role="alert">
          {error.message}
        </p>
      )}
    </div>
  );
}

/** The reporter's words, clamped so a long paste never pushes the diagnosis down. */
function Reported({ text }: { text: string }) {
  const [open, setOpen] = useState(false);
  const long = text.length > 280 || text.split("\n").length > 3;
  return (
    <div className={styles.reported}>
      <p className={styles.reportedText} data-clamped={long && !open ? "" : undefined}>
        <span className={styles.reportedLabel}>Reported</span> {text}
      </p>
      {long && (
        <button type="button" className={styles.more} onClick={() => setOpen((v) => !v)}>
          {open ? "Show less" : "Show the full report"}
        </button>
      )}
    </div>
  );
}

function NoSnapshot({ incidentId }: { incidentId: string }) {
  const collect = useCollectSnapshot(incidentId);
  return (
    <section className={styles.noSnapshot}>
      <h2>No evidence collected yet</h2>
      <p>Collect a snapshot of metrics, traces, logs, and deploys for this window first.</p>
      <button
        type="button"
        className={styles.primary}
        disabled={collect.isPending}
        onClick={() => collect.mutate()}
      >
        {collect.isPending ? "Collecting..." : "Collect evidence"}
      </button>
      {collect.error && (
        <p className={styles.controlError} role="alert">
          {collect.error.message}
        </p>
      )}
    </section>
  );
}

function Validity({ diagnosis }: { diagnosis: DiagnosisRead | undefined }) {
  if (!diagnosis) return <span>Not diagnosed</span>;
  switch (diagnosis.status) {
    case "valid":
      return <span className={styles.valid}>Valid: every claim cites this snapshot</span>;
    case "invalid":
      return (
        <span className={styles.invalidText}>
          Invalid: {count(diagnosis.validation_errors.length, "citation problem")}
        </span>
      );
    case "refused":
      return <span className={styles.invalidText}>Declined by the model</span>;
    case "error":
      return <span className={styles.invalidText}>Diagnosis failed</span>;
    default:
      return <span>Diagnosis running</span>;
  }
}

function sourceLine(snapshot: SnapshotRead): string {
  const sources = Object.values(snapshot.source_counts).filter((n) => n > 0).length;
  return `${count(snapshot.evidence_count, "exhibit")} from ${count(sources, "source")}`;
}
