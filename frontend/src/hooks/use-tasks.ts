import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

export type TaskStatus = "da_fare" | "in_corso" | "completato";
export type TaskPriority = "alta" | "media" | "bassa";

export type Task = {
  id: string;
  title: string;
  description: string;
  status: TaskStatus;
  priority: TaskPriority;
  project: string;
  due_date: string | null;
  created_at: string;
  updated_at: string;
};

const mockTasks: Task[] = [
  {
    id: "task-1",
    title: "Implementare autenticazione OAuth",
    description: "Aggiungere login con Google e GitHub tramite Supabase Auth",
    status: "in_corso",
    priority: "alta",
    project: "Jarvis v2",
    due_date: new Date(Date.now() + 2 * 86400000).toISOString(),
    created_at: new Date(Date.now() - 5 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 86400000).toISOString(),
  },
  {
    id: "task-2",
    title: "Ottimizzare query vector search",
    description:
      "Le query di ricerca semantica impiegano troppo tempo con dataset > 10k documenti. Valutare indici HNSW.",
    status: "da_fare",
    priority: "alta",
    project: "Jarvis v2",
    due_date: new Date(Date.now() + 5 * 86400000).toISOString(),
    created_at: new Date(Date.now() - 3 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 3 * 86400000).toISOString(),
  },
  {
    id: "task-3",
    title: "Scrivere test per il router semantico",
    description:
      "Aggiungere unit test per la classificazione degli intenti con copertura minima dell'80%",
    status: "da_fare",
    priority: "media",
    project: "Jarvis v2",
    due_date: new Date(Date.now() + 7 * 86400000).toISOString(),
    created_at: new Date(Date.now() - 2 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 2 * 86400000).toISOString(),
  },
  {
    id: "task-4",
    title: "Redesign pagina contatti",
    description:
      "Riprogettare la pagina contatti con il nuovo design system e aggiungere form di contatto",
    status: "completato",
    priority: "media",
    project: "Sito Web Personale",
    due_date: new Date(Date.now() - 2 * 86400000).toISOString(),
    created_at: new Date(Date.now() - 10 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 1 * 86400000).toISOString(),
  },
  {
    id: "task-5",
    title: "Aggiungere sezione portfolio",
    description: "Creare griglia progetti con filtri per categoria e animazioni di ingresso",
    status: "in_corso",
    priority: "alta",
    project: "Sito Web Personale",
    due_date: new Date(Date.now() + 3 * 86400000).toISOString(),
    created_at: new Date(Date.now() - 7 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 86400000).toISOString(),
  },
  {
    id: "task-6",
    title: "Configurare SEO e meta tag",
    description: "Implementare meta tag dinamici, sitemap.xml e schema.org per tutte le pagine",
    status: "da_fare",
    priority: "bassa",
    project: "Sito Web Personale",
    due_date: null,
    created_at: new Date(Date.now() - 4 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 4 * 86400000).toISOString(),
  },
  {
    id: "task-7",
    title: "Setup navigazione con React Navigation",
    description: "Configurare stack navigator, tab navigator e deep linking per l'app mobile",
    status: "da_fare",
    priority: "alta",
    project: "App Mobile",
    due_date: new Date(Date.now() + 10 * 86400000).toISOString(),
    created_at: new Date(Date.now() - 1 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 1 * 86400000).toISOString(),
  },
  {
    id: "task-8",
    title: "Implementare notifiche push",
    description:
      "Integrare Firebase Cloud Messaging per notifiche push su Android e iOS",
    status: "da_fare",
    priority: "media",
    project: "App Mobile",
    due_date: new Date(Date.now() + 14 * 86400000).toISOString(),
    created_at: new Date(Date.now() - 1 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 1 * 86400000).toISOString(),
  },
  {
    id: "task-9",
    title: "Creare componente chat vocale",
    description:
      "Widget per registrazione audio con visualizzazione waveform e invio al backend STT",
    status: "completato",
    priority: "alta",
    project: "Jarvis v2",
    due_date: new Date(Date.now() - 5 * 86400000).toISOString(),
    created_at: new Date(Date.now() - 15 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 5 * 86400000).toISOString(),
  },
  {
    id: "task-10",
    title: "Design sistema di theming",
    description:
      "Definire token CSS per colori, tipografia e spaziature con supporto dark mode",
    status: "completato",
    priority: "media",
    project: "App Mobile",
    due_date: new Date(Date.now() - 3 * 86400000).toISOString(),
    created_at: new Date(Date.now() - 12 * 86400000).toISOString(),
    updated_at: new Date(Date.now() - 3 * 86400000).toISOString(),
  },
];

export function useTasks(filter?: TaskStatus | "tutti") {
  return useQuery({
    queryKey: ["tasks", filter],
    queryFn: async () => {
      // TODO: fetch from Supabase
      await new Promise((r) => setTimeout(r, 300));

      if (!filter || filter === "tutti") {
        return mockTasks;
      }
      return mockTasks.filter((t) => t.status === filter);
    },
    staleTime: 30_000,
  });
}

export function useUpdateTask() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      taskId,
      updates,
    }: {
      taskId: string;
      updates: Partial<Pick<Task, "status" | "title" | "description" | "priority">>;
    }) => {
      // TODO: update in Supabase
      await new Promise((r) => setTimeout(r, 200));
      return { taskId, ...updates };
    },
    onMutate: async ({ taskId, updates }) => {
      await queryClient.cancelQueries({ queryKey: ["tasks"] });

      const previousTasks = queryClient.getQueriesData<Task[]>({ queryKey: ["tasks"] });

      queryClient.setQueriesData<Task[]>({ queryKey: ["tasks"] }, (old) =>
        old?.map((t) =>
          t.id === taskId ? { ...t, ...updates, updated_at: new Date().toISOString() } : t
        )
      );

      return { previousTasks };
    },
    onError: (_err, _vars, context) => {
      if (context?.previousTasks) {
        for (const [queryKey, data] of context.previousTasks) {
          queryClient.setQueryData(queryKey, data);
        }
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
  });
}
