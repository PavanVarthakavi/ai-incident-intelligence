import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

/** Typed client for the backend; in development Vite proxies /v1 to it. */
export const api = createClient<paths>({
  baseUrl: globalThis.location?.origin ?? "",
  // Look fetch up per request, so test mocks installed after import still apply.
  fetch: (request) => globalThis.fetch(request),
});

type Schemas = components["schemas"];
export type IncidentSummary = Schemas["IncidentSummary"];
export type IncidentRead = Schemas["IncidentRead"];
export type IncidentCreate = Schemas["IncidentCreate"];
export type IncidentPage = Schemas["IncidentPage"];
export type SnapshotSummary = Schemas["SnapshotSummary"];
export type SnapshotRead = Schemas["SnapshotRead"];
export type Evidence = Schemas["Evidence"];
export type SourceError = Schemas["SourceError"];
export type DiagnosisRead = Schemas["DiagnosisRead"];
export type DiagnosisBrief = Schemas["DiagnosisBrief"];
export type DiagnosisOutput = Schemas["DiagnosisOutput"];
export type BudgetRead = Schemas["BudgetRead"];
export type Severity = Schemas["Severity"];
export type Confidence = NonNullable<DiagnosisBrief["confidence"]>;

/** An HTTP error from the backend, carrying FastAPI's `detail` as the message. */
export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

function detailOf(error: unknown): string | undefined {
  if (typeof error !== "object" || error === null || !("detail" in error)) return undefined;
  const { detail } = error as { detail: unknown };
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => (typeof item?.msg === "string" ? item.msg : JSON.stringify(item)))
      .join("; ");
  }
  return undefined;
}

/** Resolve an openapi-fetch call to its data, or throw an ApiError. */
export async function unwrap<T>(
  call: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let result: { data?: T; error?: unknown; response: Response };
  try {
    result = await call;
  } catch {
    throw new ApiError(0, "The backend could not be reached. Is it running on port 8000?");
  }
  const { data, error, response } = result;
  if (error !== undefined || data === undefined) {
    throw new ApiError(
      response.status,
      detailOf(error) ?? `The backend answered ${response.status} ${response.statusText}.`,
    );
  }
  return data;
}
