/** Citation problems reported by the backend, e.g. "recommended_actions[3]: no evidence cited". */

const SECTION_LABEL: Record<string, string> = {
  root_cause: "Probable cause",
  contributing_factors: "Contributing factor",
  timeline: "Timeline entry",
  ruled_out: "Ruled-out cause",
  recommended_actions: "Recommended action",
};

export type CitationProblem = {
  /** "recommended_actions:3", matching the claim it belongs to; "root_cause" for the cause. */
  key: string;
  label: string;
  problem: string;
};

const PATTERN = /^(\w+)(?:\[(\d+)\])?:\s*(.+)$/;

export function parseProblem(error: string): CitationProblem {
  const match = PATTERN.exec(error);
  if (!match) return { key: "", label: "Diagnosis", problem: error };
  const [, section = "", index, problem = ""] = match;
  const name = SECTION_LABEL[section] ?? section;
  return {
    key: index === undefined ? section : `${section}:${index}`,
    label: index === undefined ? name : `${name} ${Number(index) + 1}`,
    problem,
  };
}

/** Problems grouped by the claim they belong to. */
export function problemsByClaim(errors: string[]): Map<string, string[]> {
  const result = new Map<string, string[]>();
  for (const parsed of errors.map(parseProblem)) {
    result.set(parsed.key, [...(result.get(parsed.key) ?? []), parsed.problem]);
  }
  return result;
}
