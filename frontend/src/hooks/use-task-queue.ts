import { useQuery } from "@tanstack/react-query";

type Task = {
  id: string;
  type: string;
  status: "pending" | "running" | "completed" | "failed";
  payload: Record<string, unknown>;
  created_at: string;
  scheduled_at: string | null;
};

type TaskQueueReturn = {
  pendingCount: number;
  tasks: Task[];
  isLoading: boolean;
  error: Error | null;
};

const mockTasks: Task[] = [
  {
    id: "t1",
    type: "reminder",
    status: "pending",
    payload: { message: "Chiamare il dentista" },
    created_at: new Date(Date.now() - 3600000).toISOString(),
    scheduled_at: new Date(Date.now() + 7200000).toISOString(),
  },
  {
    id: "t2",
    type: "email_digest",
    status: "pending",
    payload: { recipient: "roberto@example.com" },
    created_at: new Date(Date.now() - 1800000).toISOString(),
    scheduled_at: null,
  },
  {
    id: "t3",
    type: "reminder",
    status: "pending",
    payload: { message: "Riunione con il team" },
    created_at: new Date(Date.now() - 900000).toISOString(),
    scheduled_at: new Date(Date.now() + 14400000).toISOString(),
  },
];

export function useTaskQueue(): TaskQueueReturn {
  const { data, isLoading, error } = useQuery({
    queryKey: ["task-queue"],
    queryFn: async () => {
      // TODO: fetch from Supabase task_queue
      await new Promise((r) => setTimeout(r, 250));
      return mockTasks;
    },
    staleTime: 30000,
  });

  const tasks = data ?? [];
  const pendingCount = tasks.filter((t) => t.status === "pending").length;

  return {
    pendingCount,
    tasks,
    isLoading,
    error: error as Error | null,
  };
}
