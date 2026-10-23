import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { renderAt } from "../test/render";
import { budget, cases, server } from "../test/server";

const pathOf = (name: keyof typeof cases) => `/incidents/${cases[name].incident.id}`;
const cause = () => screen.getByRole("region", { name: /probable cause/i });

describe("a valid diagnosis", () => {
  it("states the probable cause with its confidence, service, and exhibits", async () => {
    renderAt(pathOf("valid"));
    expect(await screen.findByText(/connection pool is exhausted/)).toBeInTheDocument();
    expect(screen.getByText("Valid: every claim cites this snapshot")).toBeInTheDocument();
    const box = cause();
    expect(within(box).getByText("Medium")).toBeInTheDocument();
    expect(within(box).getByText("inventory")).toBeInTheDocument();
    expect(within(box).getAllByRole("button", { name: /^EX-\d+:/ })).toHaveLength(5);
  });

  it("highlights an exhibit while its citation is pointed at", async () => {
    const user = userEvent.setup();
    renderAt(pathOf("valid"));
    const [tag] = within(
      await screen.findByRole("region", { name: /probable cause/i }),
    ).getAllByRole("button", { name: /^EX-\d+:/ });
    const row = document.getElementById(tag!.getAttribute("aria-controls")!)!;

    await user.hover(tag!);
    expect(row).toHaveAttribute("data-focused");
    await user.unhover(tag!);
    expect(row).not.toHaveAttribute("data-focused");
  });

  it("opens an exhibit's details, including what cites it, on click", async () => {
    const user = userEvent.setup();
    renderAt(pathOf("valid"));
    const tags = within(
      await screen.findByRole("region", { name: /probable cause/i }),
    ).getAllByRole("button", { name: /^EX-\d+:/ });

    await user.click(tags[0]!);

    expect(tags[0]).toHaveAttribute("aria-expanded", "true");
    const row = document.getElementById(tags[0]!.getAttribute("aria-controls")!)!;
    expect(within(row).getByText("Cited by")).toBeInTheDocument();
    expect(within(row).getByText("Probable cause")).toBeInTheDocument();
    expect(within(row).getByText("Query")).toBeInTheDocument();
  });

  it("shows the reporter's words and the findings by kind", async () => {
    renderAt(pathOf("valid"));
    expect(
      await screen.findByText("Errors started right after gateway was deployed."),
    ).toBeInTheDocument();
    expect(await screen.findByRole("rowheader", { name: "2.1" })).toBeInTheDocument();
    expect(screen.getAllByText("Ruled out.").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Contributing factor.").length).toBeGreaterThan(0);
  });
});

describe("an invalid diagnosis", () => {
  it("is marked as failing the citation check, in the box and on the claim", async () => {
    renderAt(pathOf("invalid"));
    const box = await screen.findByRole("region", {
      name: "Probable cause, failed the citation check",
    });
    expect(within(box).getByText(/Do not act on this diagnosis/)).toBeInTheDocument();
    expect(within(box).getByText("Recommended action 4:")).toBeInTheDocument();
    expect(screen.getByText("Citation problem: no evidence cited")).toBeInTheDocument();
    expect(screen.getByText("Invalid: 1 citation problem")).toBeInTheDocument();
  });

  it("names the source that could not be collected", async () => {
    renderAt(pathOf("invalid"));
    const errors = await screen.findByRole("list", { name: /could not be collected/ });
    expect(within(errors).getByText(/Logs missing/)).toBeInTheDocument();
  });
});

describe("a healthy snapshot", () => {
  it("says there is no probable cause", async () => {
    renderAt(pathOf("healthy"));
    expect(await screen.findByText("No probable cause.")).toBeInTheDocument();
  });
});

describe("running a diagnosis", () => {
  const undiagnosed = () =>
    server.use(
      http.get("*/v1/incidents/:id/snapshots/:sid/diagnoses", () => HttpResponse.json([])),
    );

  it("offers a paid run with its typical cost and the budget left", async () => {
    undiagnosed();
    renderAt(pathOf("valid"));
    expect(await screen.findByText("Not diagnosed yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run diagnosis" })).toBeEnabled();
    expect(
      screen.getByText("Paid call, typically $0.051. $1.80 of today's $2.00 budget left."),
    ).toBeInTheDocument();
  });

  it("shows the new diagnosis when the run finishes", async () => {
    const user = userEvent.setup();
    let diagnoses: unknown[] = [];
    server.use(
      http.get("*/v1/incidents/:id/snapshots/:sid/diagnoses", () => HttpResponse.json(diagnoses)),
      http.post("*/v1/incidents/:id/snapshots/:sid/diagnoses", () => {
        diagnoses = cases.valid.diagnoses;
        return HttpResponse.json(cases.valid.diagnoses[0], { status: 201 });
      }),
    );
    renderAt(pathOf("valid"));

    await user.click(await screen.findByRole("button", { name: "Run diagnosis" }));

    expect(await screen.findByText(/connection pool is exhausted/)).toBeInTheDocument();
  });

  it("explains a refusal from the budget", async () => {
    const user = userEvent.setup();
    undiagnosed();
    server.use(
      http.post("*/v1/incidents/:id/snapshots/:sid/diagnoses", () =>
        HttpResponse.json(
          { detail: "daily LLM budget of $2.0 would be exceeded" },
          { status: 429 },
        ),
      ),
    );
    renderAt(pathOf("valid"));

    await user.click(await screen.findByRole("button", { name: "Run diagnosis" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "daily LLM budget of $2.0 would be exceeded",
    );
  });

  it("is unavailable when the backend has no model", async () => {
    undiagnosed();
    server.use(http.get("*/v1/budget", () => HttpResponse.json({ ...budget, enabled: false })));
    renderAt(pathOf("valid"));
    expect(
      await screen.findByText("Diagnosis is off: the backend has no model configured."),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run diagnosis" })).toBeDisabled();
  });
});

it("reports an incident that does not exist", async () => {
  renderAt("/incidents/00000000-0000-0000-0000-000000000000");
  expect(await screen.findByText("This incident does not exist.")).toBeInTheDocument();
});

describe("worst cases", () => {
  it("does not offer a paid run on a snapshot with no evidence", async () => {
    const empty = { ...cases.healthy.snapshot, evidence: [], evidence_count: 0, source_counts: {} };
    server.use(
      http.get("*/v1/incidents/:id/snapshots/:sid", () => HttpResponse.json(empty)),
      http.get("*/v1/incidents/:id/snapshots/:sid/diagnoses", () => HttpResponse.json([])),
    );
    renderAt(pathOf("healthy"));
    expect(await screen.findByRole("button", { name: "Run diagnosis" })).toBeDisabled();
    expect(screen.getByText(/Nothing to diagnose/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Collect a new snapshot" })).toBeEnabled();
  });

  it("clamps a long report and can show all of it", async () => {
    const user = userEvent.setup();
    const description = "Customers see errors. ".repeat(40);
    server.use(
      http.get("*/v1/incidents/:id", () =>
        HttpResponse.json({ ...cases.valid.incident, description }),
      ),
    );
    renderAt(pathOf("valid"));
    const more = await screen.findByRole("button", { name: "Show the full report" });
    await user.click(more);
    expect(screen.getByRole("button", { name: "Show less" })).toBeInTheDocument();
  });
});
