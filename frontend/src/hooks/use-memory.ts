import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

export type MemoryCategory = "preferenza" | "fatto" | "episodio" | "task";

export type MemoryFact = {
  id: string;
  category: MemoryCategory;
  content: string;
  created_at: string;
};

const mockFacts: MemoryFact[] = [
  {
    id: "mf-1",
    category: "preferenza",
    content: "Preferisce ricevere i riassunti email alle 8 di mattina",
    created_at: "2026-02-12T08:30:00Z",
  },
  {
    id: "mf-2",
    category: "fatto",
    content: "Lavora come sviluppatore software a Milano",
    created_at: "2026-02-10T14:20:00Z",
  },
  {
    id: "mf-3",
    category: "episodio",
    content: "Ha partecipato alla conferenza React Summit il 5 febbraio 2026",
    created_at: "2026-02-05T18:00:00Z",
  },
  {
    id: "mf-4",
    category: "preferenza",
    content: "Usa il formato 24 ore per gli orari",
    created_at: "2026-02-03T09:15:00Z",
  },
  {
    id: "mf-5",
    category: "task",
    content: "Deve completare il report trimestrale entro fine febbraio",
    created_at: "2026-02-01T11:00:00Z",
  },
  {
    id: "mf-6",
    category: "fatto",
    content: "Il suo compleanno e' il 15 marzo",
    created_at: "2026-01-28T16:45:00Z",
  },
  {
    id: "mf-7",
    category: "episodio",
    content: "Ha fatto una call con il team di design il 27 gennaio per il redesign del dashboard",
    created_at: "2026-01-27T10:30:00Z",
  },
  {
    id: "mf-8",
    category: "preferenza",
    content: "Preferisce le notifiche Telegram silenziose dopo le 22:00",
    created_at: "2026-01-25T22:10:00Z",
  },
];

export function useMemoryFacts() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["memory-facts"],
    queryFn: async () => {
      // TODO: fetch from Supabase memory_facts table
      await new Promise((r) => setTimeout(r, 300));
      return mockFacts;
    },
    staleTime: 5 * 60 * 1000,
  });

  return {
    facts: data ?? [],
    isLoading,
    error: error as Error | null,
  };
}

export function useDeleteFact() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (factId: string) => {
      // TODO: delete from Supabase memory_facts
      await new Promise((r) => setTimeout(r, 400));
      return factId;
    },
    onMutate: async (factId) => {
      await queryClient.cancelQueries({ queryKey: ["memory-facts"] });
      const previous = queryClient.getQueryData<MemoryFact[]>(["memory-facts"]);
      queryClient.setQueryData<MemoryFact[]>(["memory-facts"], (old) =>
        old?.filter((f) => f.id !== factId) ?? []
      );
      return { previous };
    },
    onError: (_err, _factId, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["memory-facts"], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["memory-facts"] });
    },
  });
}
