import { scrollBehavior } from "../../lib/motion";
import { useEffect, useRef } from "react";
import type { Evidence, SnapshotRead } from "../../api/client";
import { tidySummary } from "../../lib/exhibits";
import { capitalize, count, utcTime } from "../../lib/format";
import { exhibitRowId, useExhibits } from "./exhibitState";
import { ExhibitDetail } from "./ExhibitDetail";
import styles from "./Exhibits.module.css";

const SOURCE_LABEL: Record<string, string> = {
  metrics: "Metrics",
  traces: "Traces",
  logs: "Logs",
  deployments: "Deployment",
};

/** The snapshot's evidence, numbered, with the active citation highlighted and in view. */
export function Exhibits({ snapshot }: { snapshot: SnapshotRead }) {
  const { evidence, active, pinned } = useExhibits();
  const focus = active ?? pinned;

  return (
    <section className={styles.column} aria-labelledby="exhibits-heading" data-exhibit-scroll="">
      <header className={styles.head}>
        <h2 id="exhibits-heading" className={styles.heading}>
          Exhibits
        </h2>
        <span className={styles.headMeta}>
          {count(evidence.length, "item")}, collected {utcTime(snapshot.collected_at)} UTC
        </span>
      </header>
      {snapshot.source_errors.length > 0 && (
        <ul
          id="source-errors"
          className={styles.sourceErrors}
          aria-label="Sources that could not be collected"
        >
          {snapshot.source_errors.map((error) => (
            <li key={error.source}>
              <strong>{capitalize(error.source)} missing.</strong> {error.message}
            </li>
          ))}
        </ul>
      )}
      {snapshot.empty_sources.length > 0 && (
        <p id="empty-sources" className={styles.emptySources}>
          Queried, nothing found: {snapshot.empty_sources.join(", ")}.
        </p>
      )}
      {evidence.length === 0 ? (
        <p className={styles.empty}>
          No evidence in this window. The services may have been quiet, or every source failed.
        </p>
      ) : (
        <ol className={styles.list}>
          {evidence.map((item, index) => (
            <ExhibitRow key={item.id} item={item} number={index + 1} focused={focus === item.id} />
          ))}
        </ol>
      )}
    </section>
  );
}

function ExhibitRow({
  item,
  number,
  focused,
}: {
  item: Evidence;
  number: number;
  focused: boolean;
}) {
  const { pinned, togglePin } = useExhibits();
  const ref = useRef<HTMLLIElement>(null);
  const open = pinned === item.id;

  // Hovering a citation scrolls only the exhibits column, so the page never moves under the
  // pointer. Opening an exhibit may scroll the page (narrow layouts, where exhibits sit below).
  useEffect(() => {
    const row = ref.current;
    if (!row || !focused) return;
    const column = row.closest<HTMLElement>("[data-exhibit-scroll]");
    if (column && column.scrollHeight > column.clientHeight) {
      const top =
        row.getBoundingClientRect().top - column.getBoundingClientRect().top + column.scrollTop;
      const bottom = top + row.offsetHeight;
      if (top < column.scrollTop || bottom > column.scrollTop + column.clientHeight) {
        column.scrollTo({ top: top - 16, behavior: scrollBehavior() });
      }
    } else if (open) {
      row.scrollIntoView({ block: "start", behavior: scrollBehavior() });
    }
  }, [focused, open]);

  return (
    <li
      ref={ref}
      id={exhibitRowId(item.id)}
      className={styles.row}
      data-focused={focused ? "" : undefined}
    >
      <button
        type="button"
        className={styles.rowButton}
        aria-expanded={open}
        onClick={() => togglePin(item.id)}
      >
        <span className={styles.rowTag}>EX-{number}</span>
        <span className={styles.rowBody}>
          <span className={styles.rowMeta}>
            {item.service ?? "all services"} &middot; {SOURCE_LABEL[item.source] ?? item.source}
            {item.observed_at && <> &middot; {utcTime(item.observed_at)}</>}
          </span>
          <span className={styles.rowSummary}>{tidySummary(item.summary)}</span>
        </span>
      </button>
      {open && <ExhibitDetail item={item} />}
    </li>
  );
}
