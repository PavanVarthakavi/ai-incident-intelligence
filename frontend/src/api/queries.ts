import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, unwrap, type IncidentCreate } from "./client";

export const PAGE_SIZE = 50;

export const keys = {
  budget: ["budget"] as const,
  incidents: (offset: number) => ["incidents", offset] as const,
  incident: (id: string) => ["incident", id] as const,
  snapshot: (incidentId: string, snapshotId: string) =>
    ["snapshot", incidentId, snapshotId] as const,
  diagnoses: (incidentId: string, snapshotId: string) =>
    ["diagnoses", incidentId, snapshotId] as const,
};

export function useBudget() {
  return useQuery({
    queryKey: keys.budget,
    queryFn: () => unwrap(api.GET("/v1/budget")),
    refetchInterval: 60_000,
  });
}

export function useIncidents(offset: number) {
  return useQuery({
    queryKey: keys.incidents(offset),
    queryFn: () =>
      unwrap(api.GET("/v1/incidents", { params: { query: { limit: PAGE_SIZE, offset } } })),
  });
}

export function useIncident(id: string) {
  return useQuery({
    queryKey: keys.incident(id),
    queryFn: () =>
      unwrap(api.GET("/v1/incidents/{incident_id}", { params: { path: { incident_id: id } } })),
  });
}

/** Snapshots never change, so they are fetched once. */
export function useSnapshot(incidentId: string, snapshotId: string | undefined) {
  return useQuery({
    queryKey: keys.snapshot(incidentId, snapshotId ?? ""),
    enabled: snapshotId !== undefined,
    staleTime: Infinity,
    queryFn: () =>
      unwrap(
        api.GET("/v1/incidents/{incident_id}/snapshots/{snapshot_id}", {
          params: { path: { incident_id: incidentId, snapshot_id: snapshotId ?? "" } },
        }),
      ),
  });
}

export function useDiagnoses(incidentId: string, snapshotId: string | undefined) {
  return useQuery({
    queryKey: keys.diagnoses(incidentId, snapshotId ?? ""),
    enabled: snapshotId !== undefined,
    queryFn: () =>
      unwrap(
        api.GET("/v1/incidents/{incident_id}/snapshots/{snapshot_id}/diagnoses", {
          params: { path: { incident_id: incidentId, snapshot_id: snapshotId ?? "" } },
        }),
      ),
  });
}

export function useCreateIncident() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: IncidentCreate) => unwrap(api.POST("/v1/incidents", { body })),
    onSuccess: () => client.invalidateQueries({ queryKey: ["incidents"] }),
  });
}

export function useCollectSnapshot(incidentId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/v1/incidents/{incident_id}/snapshots", {
          params: { path: { incident_id: incidentId } },
        }),
      ),
    onSuccess: () => client.invalidateQueries({ queryKey: keys.incident(incidentId) }),
  });
}

/** Runs a paid diagnosis. The request returns when the model has finished. */
export function useRunDiagnosis(incidentId: string, snapshotId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/v1/incidents/{incident_id}/snapshots/{snapshot_id}/diagnoses", {
          params: { path: { incident_id: incidentId, snapshot_id: snapshotId } },
        }),
      ),
    onSettled: () =>
      Promise.all([
        client.invalidateQueries({ queryKey: keys.diagnoses(incidentId, snapshotId) }),
        client.invalidateQueries({ queryKey: keys.incident(incidentId) }),
        client.invalidateQueries({ queryKey: ["incidents"] }),
        client.invalidateQueries({ queryKey: keys.budget }),
      ]),
  });
}
