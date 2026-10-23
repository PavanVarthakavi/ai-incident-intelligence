import type { Evidence } from "../../api/client";
import { utcTime } from "../../lib/format";
import { useExhibits } from "./exhibitState";
import { deployData, logData, metricsData, traceData } from "./evidenceData";
import { SeriesChart } from "./SeriesChart";
import styles from "./Exhibits.module.css";

const percent = (v: number) => `${(v * 100).toFixed(1)}%`;
const latency = (v: number) => (v < 1 ? `${Math.round(v * 1000)} ms` : `${v.toFixed(2)} s`);

const REFERENCE_LABEL: Record<string, string> = {
  metrics: "Open the query result in Prometheus",
  traces: "Open an example trace in Jaeger",
  logs: "Open in OpenSearch",
  deployments: "Open the deploy event in OpenSearch",
};

export function ExhibitDetail({ item }: { item: Evidence }) {
  const { citedBy, hasOrigin, returnToCitation } = useExhibits();
  const citations = citedBy.get(item.id) ?? [];

  return (
    <div className={styles.detail}>
      <KindDetail item={item} />
      <dl className={styles.facts}>
        <dt>Cited by</dt>
        <dd>
          {citations.length ? (
            <ul className={styles.citedBy}>
              {citations.map((c) => (
                <li key={c.id}>{c.label}</li>
              ))}
            </ul>
          ) : (
            "Not cited by this diagnosis"
          )}
        </dd>
        <dt>Evidence ID</dt>
        <dd>
          <code>{item.id}</code>
        </dd>
      </dl>
      <details className={styles.query}>
        <summary>Query</summary>
        <pre>{item.query}</pre>
      </details>
      {item.reference && (
        <a className={styles.reference} href={item.reference} target="_blank" rel="noreferrer">
          {REFERENCE_LABEL[item.source] ?? "Open the source"}
        </a>
      )}
      {hasOrigin && (
        <button type="button" className={styles.back} onClick={returnToCitation}>
          Back to the citation
        </button>
      )}
    </div>
  );
}

function KindDetail({ item }: { item: Evidence }) {
  if (item.kind === "service_http_metrics") {
    const m = metricsData(item.data ?? {});
    if (!m) return null;
    return (
      <div className={styles.charts}>
        <SeriesChart
          label="5xx ratio"
          points={m.series.errorRatio}
          format={percent}
          onset={m.errorOnset}
          summary={`5xx ratio for ${item.service}: max ${percent(m.stats.errorRatio.max ?? 0)}${
            m.errorOnset ? `, crossing the threshold at ${utcTime(m.errorOnset)}` : ""
          }`}
        />
        <SeriesChart
          label="p95 latency"
          points={m.series.p95}
          format={latency}
          onset={m.latencyOnset}
          summary={`p95 latency for ${item.service}: max ${latency(m.stats.p95.max ?? 0)}${
            m.latencyOnset ? `, crossing the threshold at ${utcTime(m.latencyOnset)}` : ""
          }`}
        />
      </div>
    );
  }
  if (item.kind === "trace_pattern") {
    const t = traceData(item.data ?? {});
    if (!t || t.path.length === 0) return null;
    return (
      <ol className={styles.path} aria-label="Failing call path, outermost first">
        {t.path.map((hop) => (
          <li key={`${hop.service}${hop.operation}`}>
            <span>{hop.service}</span> <code>{hop.operation}</code>
            {hop.status !== null && <b data-error={hop.status >= 500 || undefined}>{hop.status}</b>}
          </li>
        ))}
      </ol>
    );
  }
  if (item.kind === "log_pattern") {
    const l = logData(item.data ?? {});
    return (
      <dl className={styles.facts}>
        <dt>Message</dt>
        <dd>
          <code>{l.message}</code>
        </dd>
        <dt>Count</dt>
        <dd>
          {l.count} {l.severity}
          {l.firstSeen && l.lastSeen && (
            <>
              , {utcTime(l.firstSeen)} to {utcTime(l.lastSeen)} UTC
            </>
          )}
        </dd>
        {l.releases.length > 0 && (
          <>
            <dt>Release</dt>
            <dd>
              <code>{l.releases.join(", ")}</code>
            </dd>
          </>
        )}
      </dl>
    );
  }
  if (item.kind === "deployment") {
    const d = deployData(item.data ?? {});
    return (
      <dl className={styles.facts}>
        <dt>Change</dt>
        <dd>
          {d.service} <code>{d.from ?? "?"}</code> to <code>{d.to ?? "?"}</code>
        </dd>
        <dt>By</dt>
        <dd>
          {d.author}
          {d.at && <>, {utcTime(d.at)} UTC</>}
        </dd>
      </dl>
    );
  }
  return null;
}
