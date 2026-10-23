import { useRouteError } from "react-router";
import { PageStatus } from "./PageStatus";

/** Shown when a page throws while rendering. */
export function RouteError() {
  const error = useRouteError();
  return (
    <PageStatus error={error instanceof Error ? error : new Error(String(error))} subject="page" />
  );
}
