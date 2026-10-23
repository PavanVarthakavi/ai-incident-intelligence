import { Link, useSearchParams } from "react-router";
import type { DiagnosisBrief } from "../api/client";
import { PAGE_SIZE, useIncidents } from "../api/queries";
import { PageStatus } from "../components/PageStatus";
import { SeverityText } from "../components/SeverityText";
import { count, utcDate, utcTime, utcWindow } from "../lib/format";
import styles from "./IncidentsPage.module.css";

export function IncidentsPage() {
  const [params, setParams] = useSearchParams();
  const page = Math.max(1, Number(params.get("page")) || 1);
  const incidents = useIncidents((page - 1) * PAGE_SIZE);

  if (incidents.isPending) return <PageStatus>Loading incidents...</PageStatus>;
  if (incidents.isError) return <PageStatus error={incidents.error} subject="incident list" />;

  const { items, total } = incidents.data;
  const pages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <section className={styles.sheet}>
      <header className={styles.head}>
        <h1 className={styles.title}>Incidents</h1>
        <span className={styles.count}>{count(total, "incident")}, newest first</span>
        <Link to="/incidents/new" className={styles.new}>
          New incident
        </Link>
      </header>

      {items.length === 0 ? (
        <div className={styles.empty}>
          <p className={styles.emptyTitle}>No incidents yet.</p>
          <p>
            Create one for a time window: the backend collects its metrics, traces, logs, and
            deploys into a snapshot you can diagnose.
          </p>
        </div>
      ) : (
        <table className={styles.table}>
          <thead>
            <tr>
              <th scope="col" className={styles.sev}>
                Severity
              </th>
              <th scope="col">Incident</th>
              <th scope="col" className={styles.diag}>
                Latest diagnosis
              </th>
              <th scope="col" className={styles.opened}>
                Opened (UTC)
              </th>
            </tr>
          </thead>
          <tbody>
            {items.map((incident) => (
              <tr key={incident.id}>
                <td className={styles.sev}>
                  <SeverityText severity={incident.severity} />
                </td>
                <td>
                  <Link to={`/incidents/${incident.id}`} className={styles.link}>
                    {incident.title}
                  </Link>
                  <span className={styles.window}>
                    {utcWindow(incident.window.start, incident.window.end)}
                    {incident.services?.length ? ` \u00b7 ${incident.services.join(", ")}` : ""}
                  </span>
                </td>
                <td className={styles.diag}>
                  <DiagnosisCell brief={incident.latest_diagnosis} />
                </td>
                <td className={styles.opened}>
                  {utcDate(incident.created_at)}
                  <span className={styles.window}>{utcTime(incident.created_at)}</span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {pages > 1 && (
        <nav className={styles.pager} aria-label="Pages">
          <button
            type="button"
            disabled={page <= 1}
            onClick={() => setParams({ page: String(page - 1) })}
          >
            Newer
          </button>
          <span>
            Page {page} of {pages}
          </span>
          <button
            type="button"
            disabled={page >= pages}
            onClick={() => setParams({ page: String(page + 1) })}
          >
            Older
          </button>
        </nav>
      )}
    </section>
  );
}

function DiagnosisCell({ brief }: { brief: DiagnosisBrief | null | undefined }) {
  if (!brief) return <span className={styles.muted}>Not diagnosed</span>;
  switch (brief.status) {
    case "valid":
      return brief.root_cause_service ? (
        <span>
          <b>{brief.root_cause_service}</b>, {brief.confidence} confidence
        </span>
      ) : (
        <span>No probable cause</span>
      );
    case "invalid":
      return <span className={styles.bad}>Failed the citation check</span>;
    case "refused":
      return <span className={styles.bad}>Declined by the model</span>;
    case "error":
      return <span className={styles.bad}>Failed</span>;
    default:
      return <span className={styles.muted}>Running</span>;
  }
}
