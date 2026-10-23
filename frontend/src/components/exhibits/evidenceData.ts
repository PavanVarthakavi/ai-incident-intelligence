/** Typed readers for the `data` of each evidence kind. Unknown shapes return null. */

type Data = Record<string, unknown>;

const isRecord = (value: unknown): value is Data =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const num = (value: unknown): number | null => (typeof value === "number" ? value : null);
const str = (value: unknown): string | null => (typeof value === "string" ? value : null);
const strings = (value: unknown): string[] =>
  Array.isArray(value) ? value.filter((v): v is string => typeof v === "string") : [];

export type Point = { t: number; v: number };
export type Stat = { avg: number | null; max: number | null };

export type MetricsData = {
  series: { errorRatio: Point[]; p95: Point[]; rate: Point[] };
  stats: { errorRatio: Stat; p95: Stat; rate: Stat };
  errorOnset: string | null;
  latencyOnset: string | null;
};

function series(value: unknown): Point[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((pair) => {
    if (!Array.isArray(pair)) return [];
    const t = Date.parse(String(pair[0]));
    const v = Number(pair[1]);
    return Number.isNaN(t) || Number.isNaN(v) ? [] : [{ t, v }];
  });
}

function stat(stats: Data, key: string): Stat {
  const entry = isRecord(stats[key]) ? (stats[key] as Data) : {};
  return { avg: num(entry.avg), max: num(entry.max) };
}

export function metricsData(data: Data): MetricsData | null {
  if (!isRecord(data.series)) return null;
  const s = data.series as Data;
  const stats = isRecord(data.stats) ? (data.stats as Data) : {};
  return {
    series: {
      errorRatio: series(s.error_ratio),
      p95: series(s.p95_latency_s),
      rate: series(s.request_rate_rps),
    },
    stats: {
      errorRatio: stat(stats, "error_ratio"),
      p95: stat(stats, "p95_latency_s"),
      rate: stat(stats, "request_rate_rps"),
    },
    errorOnset: str(data.error_ratio_onset),
    latencyOnset: str(data.p95_latency_onset),
  };
}

export type Hop = { service: string; operation: string; status: number | null };
export type TraceData = {
  path: Hop[];
  minDuration: number | null;
  maxDuration: number | null;
  sampled: number | null;
  releases: string[];
  examples: { id: string; url: string | null }[];
};

export function traceData(data: Data): TraceData | null {
  const raw = Array.isArray(data.error_path) ? data.error_path : null;
  const durations = isRecord(data.duration_s) ? (data.duration_s as Data) : {};
  const examples = Array.isArray(data.example_traces) ? data.example_traces : [];
  return {
    path: (raw ?? []).flatMap((hop) =>
      Array.isArray(hop)
        ? [{ service: String(hop[0]), operation: String(hop[1]), status: num(hop[2]) }]
        : [],
    ),
    minDuration: num(durations.min),
    maxDuration: num(durations.max),
    sampled: num(data.sampled_traces),
    releases: isRecord(data.releases) ? Object.keys(data.releases as Data) : [],
    examples: examples.flatMap((e) =>
      isRecord(e) && typeof e.trace_id === "string" ? [{ id: e.trace_id, url: str(e.url) }] : [],
    ),
  };
}

export type LogData = {
  message: string | null;
  count: number | null;
  severity: string | null;
  firstSeen: string | null;
  lastSeen: string | null;
  releases: string[];
  traceIds: string[];
};

export function logData(data: Data): LogData {
  return {
    message: str(data.message),
    count: num(data.count),
    severity: str(data.severity),
    firstSeen: str(data.first_seen),
    lastSeen: str(data.last_seen),
    releases: strings(data.releases),
    traceIds: strings(data.example_trace_ids),
  };
}

export type DeployData = {
  service: string | null;
  from: string | null;
  to: string | null;
  author: string | null;
  at: string | null;
  description: string | null;
};

export function deployData(data: Data): DeployData {
  return {
    service: str(data.service),
    from: str(data.previous_version),
    to: str(data.version),
    author: str(data.author),
    at: str(data.timestamp),
    description: str(data.description),
  };
}
