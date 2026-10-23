/** Formatting for an operations audience: UTC everywhere, labelled once. */

const time = new Intl.DateTimeFormat("en-GB", {
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
  hour12: false,
  timeZone: "UTC",
});

const date = new Intl.DateTimeFormat("en-GB", {
  day: "numeric",
  month: "short",
  year: "numeric",
  timeZone: "UTC",
});

/** "09:13:45" (UTC). */
export function utcTime(iso: string): string {
  return time.format(new Date(iso));
}

/** utcTime for an ISO timestamp; anything unparseable is returned as written. */
export function maybeUtcTime(value: string): string {
  return Number.isNaN(Date.parse(value)) ? value : utcTime(value);
}

/** "23 Oct 2026". */
export function utcDate(iso: string): string {
  return date.format(new Date(iso));
}

/** "23 Oct 2026, 09:11:42 to 09:16:13 UTC", with the date repeated only when it changes. */
export function utcWindow(start: string, end: string): string {
  const startDate = utcDate(start);
  const endDate = utcDate(end);
  const tail = endDate === startDate ? utcTime(end) : `${endDate}, ${utcTime(end)}`;
  return `${startDate}, ${utcTime(start)} to ${tail} UTC`;
}

/** "$0.061"; three decimals below a dollar, two above. */
export function usd(value: string | number | null | undefined): string {
  if (value === null || value === undefined) return "unknown";
  const amount = Number(value);
  return `$${amount.toFixed(amount < 1 ? 3 : 2)}`;
}

/** "19 s", "2 min 05 s". */
export function seconds(total: number): string {
  if (total < 60) return `${Math.round(total)} s`;
  const minutes = Math.floor(total / 60);
  const rest = Math.round(total % 60);
  return `${minutes} min ${String(rest).padStart(2, "0")} s`;
}

/** Seconds between two ISO timestamps, or null if either is missing. */
export function elapsed(start: string, end: string | null | undefined): number | null {
  if (!end) return null;
  return (new Date(end).getTime() - new Date(start).getTime()) / 1000;
}

export function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** "1 exhibit", "8 exhibits". */
export function count(n: number, noun: string): string {
  return `${n} ${noun}${n === 1 ? "" : "s"}`;
}
