import { screen, within } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { expect, it } from "vitest";
import { renderAt } from "../test/render";
import { server } from "../test/server";

it("lists incidents with their latest diagnosis", async () => {
  renderAt("/");
  const table = await screen.findByRole("table");
  const rows = within(table).getAllByRole("row").slice(1);
  expect(rows).toHaveLength(3);
  expect(
    within(table).getByRole("link", { name: "Checkout failing since the gateway release" }),
  ).toBeInTheDocument();
  expect(within(table).getByText("Failed the citation check")).toBeInTheDocument();
  expect(within(table).getByText("No probable cause")).toBeInTheDocument();
  expect(screen.getByText("3 incidents, newest first")).toBeInTheDocument();
});

it("explains what to do when there are no incidents", async () => {
  server.use(
    http.get("*/v1/incidents", () =>
      HttpResponse.json({ items: [], total: 0, limit: 50, offset: 0 }),
    ),
  );
  renderAt("/");
  expect(await screen.findByText("No incidents yet.")).toBeInTheDocument();
  expect(screen.getByText(/Create one for a time window/)).toBeInTheDocument();
});

it("says when the backend is down", async () => {
  server.use(http.get("*/v1/incidents", () => HttpResponse.error()));
  renderAt("/");
  expect(await screen.findByText(/could not be reached/)).toBeInTheDocument();
});
