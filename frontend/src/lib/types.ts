// Types miroirs des schémas Pydantic (backend/app/schemas). À compléter phase par phase.

export type User = {
  id: string;
  email: string;
};

export type JobStatus = "pending" | "running" | "done" | "failed";

export type Job = {
  id: string;
  type: string;
  status: JobStatus;
  entity_kind: string | null;
  entity_id: string | null;
  progress: number;
  message: string | null;
  error: string | null;
  result: Record<string, unknown> | null;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
};
