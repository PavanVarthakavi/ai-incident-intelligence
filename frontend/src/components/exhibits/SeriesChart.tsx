import type { Point } from "./evidenceData";
import { utcTime } from "../../lib/format";
import styles from "./Exhibits.module.css";

const W = 400;
const H = 64;
const PAD_TOP = 6;

type Props = {
  label: string;
  points: Point[];
  format: (value: number) => string;
  onset: string | null;
  summary: string;
};

/** One series over the snapshot window, with its onset marked when there is one. */
export function SeriesChart({ label, points, format, onset, summary }: Props) {
  if (points.length < 2) return null;
  const first = points[0]!.t;
  const last = points[points.length - 1]!.t;
  const max = Math.max(...points.map((p) => p.v));
  const top = max > 0 ? max : 1;
  const x = (t: number) => ((t - first) / (last - first || 1)) * W;
  const y = (v: number) => PAD_TOP + (1 - v / top) * (H - PAD_TOP);
  const line = points.map((p) => `${x(p.t).toFixed(1)},${y(p.v).toFixed(1)}`).join(" ");
  const onsetT = onset ? Date.parse(onset) : NaN;
  const onsetX = Number.isNaN(onsetT) ? null : x(onsetT);

  return (
    <figure className={styles.chart}>
      <figcaption className={styles.chartHead}>
        <span>{label}</span>
        <span>max {format(max)}</span>
      </figcaption>
      <svg viewBox={`0 0 ${W} ${H}`} preserveAspectRatio="none" role="img" aria-label={summary}>
        <line x1="0" y1={H - 0.5} x2={W} y2={H - 0.5} className={styles.chartBase} />
        {onsetX !== null && (
          <line x1={onsetX} y1="0" x2={onsetX} y2={H} className={styles.chartOnset} />
        )}
        <polyline points={line} className={styles.chartLine} />
      </svg>
      <div className={styles.chartAxis}>
        <span>{utcTime(new Date(first).toISOString())}</span>
        {onset && <span className={styles.chartOnsetLabel}>onset {utcTime(onset)}</span>}
        <span>{utcTime(new Date(last).toISOString())}</span>
      </div>
    </figure>
  );
}
