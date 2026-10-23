import type { DiagnosisOutput, Evidence } from "../api/client";
import { maybeUtcTime } from "./format";

/**
 * Exhibit numbers follow the snapshot's collection order, so EX-5 names the same evidence in
 * every view and every diagnosis of that snapshot.
 */
export function exhibitNumbers(evidence: Evidence[]): Map<string, number> {
  return new Map(evidence.map((item, index) => [item.id, index + 1]));
}

export type CitationSource = { id: string; label: string };

/** For each evidence ID, the diagnosis parts that cite it, in reading order. */
export function citedBy(output: DiagnosisOutput): Map<string, CitationSource[]> {
  const result = new Map<string, CitationSource[]>();
  const add = (ids: string[], source: CitationSource) => {
    for (const id of ids) {
      const list = result.get(id) ?? [];
      if (!list.some((s) => s.id === source.id)) list.push(source);
      result.set(id, list);
    }
  };
  if (output.root_cause)
    add(output.root_cause.evidence_ids, { id: "cause", label: "Probable cause" });
  findings(output).forEach((finding, i) =>
    add(finding.evidence_ids, {
      id: `finding-${i}`,
      label: `${finding.kind}: ${excerpt(finding.statement)}`,
    }),
  );
  output.timeline.forEach((entry, i) =>
    add(entry.evidence_ids, {
      id: `timeline-${i}`,
      label: `Timeline, ${maybeUtcTime(entry.time)}`,
    }),
  );
  output.recommended_actions.forEach((action, i) =>
    add(action.evidence_ids, { id: `action-${i}`, label: `Action: ${excerpt(action.action)}` }),
  );
  return result;
}

export type FindingKind = "Contributing factor" | "Ruled out" | "Not established";

/** Findings are section 2 of the report, after the probable cause: 2.1, 2.2, ... */
export const findingNumber = (index: number) => `2.${index + 1}`;

export type Finding = {
  kind: FindingKind;
  statement: string;
  evidence_ids: string[];
  /** Where the claim sits in the output, as the backend's validator names it. */
  path: string | null;
};

/** The report's findings: contributing factors, then ruled-out causes, then unknowns. */
export function findings(output: DiagnosisOutput): Finding[] {
  return [
    ...output.contributing_factors.map((c, i) => ({
      kind: "Contributing factor" as const,
      ...c,
      path: `contributing_factors:${i}`,
    })),
    ...output.ruled_out.map((c, i) => ({
      kind: "Ruled out" as const,
      ...c,
      path: `ruled_out:${i}`,
    })),
    ...output.unknowns.map((statement) => ({
      kind: "Not established" as const,
      statement,
      evidence_ids: [],
      path: null,
    })),
  ];
}

/** The start of a sentence, cut at a word boundary. */
export function excerpt(text: string, max = 56): string {
  if (text.length <= max) return text;
  const cut = text.slice(0, max);
  return `${cut.slice(0, cut.lastIndexOf(" ")).replace(/[,;:.]$/, "")}...`;
}

const ISO = /\b\d{4}-\d{2}-\d{2}T(\d{2}:\d{2}:\d{2})(?:\.\d+)?Z\b/g;
const EXAMPLE_TRACES = /;?\s*example traces?:\s*[0-9a-f]{16,}(?:,\s*[0-9a-f]{16,})*/gi;

/** An evidence summary for the exhibit list: times instead of timestamps, no trace IDs. */
export function tidySummary(summary: string): string {
  return summary
    .replace(EXAMPLE_TRACES, "")
    .replace(ISO, "$1")
    .replace(/\s*<-\s*/g, " \u2190 ");
}
