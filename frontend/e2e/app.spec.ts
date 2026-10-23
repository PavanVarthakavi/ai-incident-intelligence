import AxeBuilder from "@axe-core/playwright";
import { expect, test, type Page } from "@playwright/test";

/** WCAG 2.2 AA, as PRODUCT.md requires. */
async function expectAccessible(page: Page) {
  const results = await new AxeBuilder({ page })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  expect(results.violations.map((v) => `${v.id}: ${v.help}`)).toEqual([]);
}

async function openIncident(page: Page, title: string, nth = 0) {
  await page.goto("/");
  await page.getByRole("link", { name: title }).nth(nth).click();
  await expect(page.getByRole("heading", { level: 1, name: title })).toBeVisible();
}

test("the incident list shows the seeded incidents and is accessible", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { name: "Incidents" })).toBeVisible();
  await expect(page.getByRole("row")).toHaveCount(4); // header + 3 seeded
  await expect(page.getByText("Failed the citation check")).toBeVisible();
  await expectAccessible(page);
});

test("a diagnosis links every claim to its exhibits", async ({ page }) => {
  await openIncident(page, "Checkout failing since the gateway release");
  const cause = page.getByRole("region", { name: "Probable cause" });
  await expect(cause).toContainText("connection pool is exhausted");
  await expectAccessible(page);

  const tag = cause.getByRole("button", { name: /^EX-\d+:/ }).first();
  const rowId = await tag.getAttribute("aria-controls");
  await tag.hover();
  await expect(page.locator(`#${rowId}`)).toHaveAttribute("data-focused", "");

  await tag.click();
  const row = page.locator(`#${rowId}`);
  await expect(row.getByText("Cited by")).toBeVisible();
  await expect(row.getByText("Probable cause", { exact: true })).toBeVisible();
  await expectAccessible(page);
});

test("exhibits open from the keyboard", async ({ page }) => {
  await openIncident(page, "Checkout failing since the gateway release");
  const tag = page
    .getByRole("region", { name: "Probable cause" })
    .getByRole("button", { name: /^EX-\d+:/ })
    .first();
  await tag.focus();
  await page.keyboard.press("Enter");
  await expect(tag).toHaveAttribute("aria-expanded", "true");
});

test("an invalid diagnosis is never presented as valid", async ({ page }) => {
  await openIncident(page, "Checkout requests are failing");
  await expect(
    page.getByRole("region", { name: "Probable cause, failed the citation check" }),
  ).toContainText("Do not act on this diagnosis");
  await expect(page.getByText("Citation problem: no evidence cited")).toBeVisible();
  await expectAccessible(page);
});

test("running a diagnosis stores and shows the new one, at no cost offline", async ({ page }) => {
  await openIncident(page, "Checkout is completely down");
  await page.getByRole("button", { name: "Run the diagnosis again" }).click();
  await expect(page.getByText(/^offline-stand-in \u00b7 cost \$0\.000/)).toBeVisible();
  await expect(page.getByLabel("Diagnosis")).toContainText("2 of 2, valid");
});

test("a new incident is created and opened", async ({ page }) => {
  await page.goto("/incidents/new");
  await expectAccessible(page);
  await page.getByLabel("What is wrong").fill("E2E: checkout is slow");
  await page.getByLabel("Severity").selectOption("medium");
  await page.getByRole("button", { name: "Create and collect evidence" }).click();
  // Collection queries every backend, which takes a few seconds.
  await expect(page.getByRole("heading", { level: 1, name: "E2E: checkout is slow" })).toBeVisible({
    timeout: 30_000,
  });
  await expect(page.getByRole("heading", { name: "Exhibits" })).toBeVisible();
  await expectAccessible(page);
});

test("an unknown incident says so", async ({ page }) => {
  await page.goto("/incidents/00000000-0000-0000-0000-000000000000");
  await expect(page.getByText("This incident does not exist.")).toBeVisible();
});
