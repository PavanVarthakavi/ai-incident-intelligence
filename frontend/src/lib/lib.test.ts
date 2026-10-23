import { describe, expect, it } from "vitest";
import { cases } from "../test/server";
import type { DiagnosisOutput } from "../api/client";
import { citedBy, excerpt, findings, tidySummary } from "./exhibits";
import { seconds, usd, utcWindow } from "./format";
import { parseProblem, problemsByClaim } from "./validation";

describe("format", () => {
  it("writes windows in UTC, repeating the date only when it changes", () => {
    expect(utcWindow("2026-10-23T09:11:42Z", "2026-10-23T09:16:13Z")).toBe(
      "23 Oct 2026, 09:11:42 to 09:16:13 UTC",
    );
    expect(utcWindow("2026-10-23T23:50:00Z", "2026-10-24T00:10:00Z")).toBe(
      "23 Oct 2026, 23:50:00 to 24 Oct 2026, 00:10:00 UTC",
    );
  });

  it("writes money and durations", () => {
    expect([usd("0.060836"), usd("2.0"), usd(null)]).toEqual(["$0.061", "$2.00", "unknown"]);
    expect([seconds(18.77), seconds(125)]).toEqual(["19 s", "2 min 05 s"]);
  });
});

describe("exhibits", () => {
  const output = cases.valid.diagnoses[0]!.output as DiagnosisOutput;

  it("lists what cites each exhibit, starting with the probable cause", () => {
    const first = output.root_cause!.evidence_ids[0]!;
    expect(citedBy(output).get(first)![0]).toEqual({ id: "cause", label: "Probable cause" });
  });

  it("orders findings as contributing, ruled out, not established, keeping their paths", () => {
    const kinds = findings(output).map((f) => f.kind);
    expect(kinds.indexOf("Ruled out")).toBeGreaterThan(kinds.lastIndexOf("Contributing factor"));
    expect(findings(output)[0]!.path).toBe("contributing_factors:0");
    expect(findings(output).at(-1)!.path).toBeNull();
  });

  it("tidies summaries for the list", () => {
    expect(
      tidySummary(
        "first at 2026-10-23T09:14:12Z (release 3.1.5); example traces: de56d9800be16db71b8d60f2d05d39f4, bc1aae4f967c0c1a00ad192c17b8355a",
      ),
    ).toBe("first at 09:14:12 (release 3.1.5)");
  });

  it("cuts excerpts at a word", () => {
    expect(excerpt("Gateway as the origin of the errors is unlikely given the traces", 30)).toBe(
      "Gateway as the origin of the...",
    );
  });
});

describe("validation problems", () => {
  it("names the claim in words", () => {
    expect(parseProblem("recommended_actions[3]: no evidence cited")).toEqual({
      key: "recommended_actions:3",
      label: "Recommended action 4",
      problem: "no evidence cited",
    });
    expect(parseProblem("root_cause: cites 'ev-x', which is not in the snapshot").label).toBe(
      "Probable cause",
    );
  });

  it("groups problems by claim", () => {
    const grouped = problemsByClaim(["timeline[0]: a", "timeline[0]: b", "ruled_out[1]: c"]);
    expect(grouped.get("timeline:0")).toEqual(["a", "b"]);
    expect(grouped.get("ruled_out:1")).toEqual(["c"]);
  });
});
