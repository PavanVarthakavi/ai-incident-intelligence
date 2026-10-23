import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { expect, it } from "vitest";
import { renderAt } from "../test/render";
import { cases, server } from "../test/server";

it("creates the incident with the entered fields and opens it", async () => {
  const user = userEvent.setup();
  let body: Record<string, unknown> | undefined;
  server.use(
    http.post("*/v1/incidents", async ({ request }) => {
      body = (await request.json()) as Record<string, unknown>;
      return HttpResponse.json(cases.valid.incident, { status: 201 });
    }),
  );
  const { router } = renderAt("/incidents/new");

  await user.type(screen.getByLabelText("What is wrong"), "Checkout is slow");
  await user.selectOptions(screen.getByLabelText("Severity"), "high");
  await user.click(screen.getByLabelText("Last 30 minutes"));
  await user.type(screen.getByLabelText("Services"), " orders, inventory ,");
  await user.click(screen.getByRole("button", { name: "Create and collect evidence" }));

  await screen.findByText(/connection pool is exhausted/);
  expect(router.state.location.pathname).toBe(`/incidents/${cases.valid.incident.id}`);
  expect(body).toMatchObject({
    title: "Checkout is slow",
    severity: "high",
    services: ["orders", "inventory"],
    description: null,
    collect_evidence: true,
  });
  const window = body!.window as { start: string; end: string };
  expect(Date.parse(window.end) - Date.parse(window.start)).toBe(30 * 60_000);
});

it("rejects a custom window that ends before it starts, without a request", async () => {
  const user = userEvent.setup();
  let requested = false;
  server.use(
    http.post("*/v1/incidents", () => {
      requested = true;
      return HttpResponse.json({}, { status: 500 });
    }),
  );
  renderAt("/incidents/new");

  await user.type(screen.getByLabelText("What is wrong"), "Something");
  await user.click(screen.getByLabelText("Custom"));
  const start = screen.getByLabelText("Start");
  const end = screen.getByLabelText("End");
  await user.clear(start);
  await user.type(start, "2026-10-23T10:00");
  await user.clear(end);
  await user.type(end, "2026-10-23T09:00");
  await user.click(screen.getByRole("button", { name: "Create and collect evidence" }));

  expect(await screen.findByRole("alert")).toHaveTextContent("The end must be after the start.");
  expect(requested).toBe(false);
});

it("shows the backend's validation message", async () => {
  const user = userEvent.setup();
  server.use(
    http.post("*/v1/incidents", () =>
      HttpResponse.json(
        { detail: [{ msg: "Value error, window must not exceed 1 day, 0:00:00" }] },
        { status: 422 },
      ),
    ),
  );
  renderAt("/incidents/new");
  await user.type(screen.getByLabelText("What is wrong"), "Something");
  await user.click(screen.getByRole("button", { name: "Create and collect evidence" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("window must not exceed 1 day");
});
