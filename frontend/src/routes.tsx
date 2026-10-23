import { ApiError } from "./api/client";
import { Layout } from "./components/layout/Layout";
import { PageStatus } from "./components/PageStatus";
import { RouteError } from "./components/RouteError";
import { IncidentPage } from "./pages/IncidentPage";
import { IncidentsPage } from "./pages/IncidentsPage";
import { NewIncidentPage } from "./pages/NewIncidentPage";

export const routes = [
  {
    element: <Layout />,
    errorElement: <RouteError />,
    children: [
      { index: true, element: <IncidentsPage /> },
      { path: "incidents/new", element: <NewIncidentPage /> },
      { path: "incidents/:id", element: <IncidentPage /> },
      { path: "*", element: <PageStatus error={new ApiError(404, "Not found")} subject="page" /> },
    ],
  },
];
