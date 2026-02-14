import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

export type SourceType = "url" | "file" | "text";

export type RagSource = {
  id: string;
  title: string;
  source_type: SourceType;
  source_url: string | null;
  chunk_count: number;
  content_preview: string;
  created_at: string;
};

export type RagStats = {
  totalDocuments: number;
  totalChunks: number;
  lastUpdated: string | null;
};

const mockSources: RagSource[] = [
  {
    id: "rag-1",
    title: "Documentazione LangGraph",
    source_type: "url",
    source_url: "https://langchain-ai.github.io/langgraph/",
    chunk_count: 42,
    content_preview: "LangGraph is a library for building stateful, multi-actor applications...",
    created_at: new Date(Date.now() - 7 * 86400000).toISOString(),
  },
  {
    id: "rag-2",
    title: "Guida Supabase Vector Search",
    source_type: "url",
    source_url: "https://supabase.com/docs/guides/ai",
    chunk_count: 28,
    content_preview:
      "Supabase provides a toolkit for developing AI applications using pgvector...",
    created_at: new Date(Date.now() - 5 * 86400000).toISOString(),
  },
  {
    id: "rag-3",
    title: "Appunti riunione progetto Q1",
    source_type: "text",
    source_url: null,
    chunk_count: 8,
    content_preview:
      "Obiettivi Q1: completare integrazione calendario, migliorare accuratezza router semantico...",
    created_at: new Date(Date.now() - 3 * 86400000).toISOString(),
  },
  {
    id: "rag-4",
    title: "API Reference Gemini",
    source_type: "url",
    source_url: "https://ai.google.dev/api/generate-content",
    chunk_count: 56,
    content_preview:
      "The Gemini API lets you generate content using Google's generative AI models...",
    created_at: new Date(Date.now() - 2 * 86400000).toISOString(),
  },
  {
    id: "rag-5",
    title: "Specifiche tecniche architettura",
    source_type: "file",
    source_url: null,
    chunk_count: 15,
    content_preview:
      "Architettura multi-agente con orchestratore centrale basato su LangGraph StateGraph...",
    created_at: new Date(Date.now() - 1 * 86400000).toISOString(),
  },
  {
    id: "rag-6",
    title: "Best practice Redis caching",
    source_type: "url",
    source_url: "https://redis.io/docs/manual/patterns/",
    chunk_count: 34,
    content_preview: "Redis patterns and best practices for caching, session management...",
    created_at: new Date(Date.now() - 12 * 3600000).toISOString(),
  },
];

export function useRagSources() {
  return useQuery({
    queryKey: ["rag-sources"],
    queryFn: async () => {
      // TODO: fetch from Supabase rag_documents
      await new Promise((r) => setTimeout(r, 300));
      return mockSources;
    },
    staleTime: 60_000,
  });
}

export function useRagStats() {
  return useQuery({
    queryKey: ["rag-stats"],
    queryFn: async () => {
      // TODO: aggregate from Supabase rag_documents
      await new Promise((r) => setTimeout(r, 200));
      const stats: RagStats = {
        totalDocuments: mockSources.length,
        totalChunks: mockSources.reduce((sum, s) => sum + s.chunk_count, 0),
        lastUpdated: mockSources.length > 0
          ? mockSources.reduce((latest, s) =>
              s.created_at > latest ? s.created_at : latest,
            mockSources[0].created_at)
          : null,
      };
      return stats;
    },
    staleTime: 60_000,
  });
}

export function useDeleteSource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (sourceId: string) => {
      // TODO: delete from Supabase
      await new Promise((r) => setTimeout(r, 300));
      return sourceId;
    },
    onMutate: async (sourceId) => {
      await queryClient.cancelQueries({ queryKey: ["rag-sources"] });
      const previous = queryClient.getQueryData<RagSource[]>(["rag-sources"]);

      queryClient.setQueryData<RagSource[]>(["rag-sources"], (old) =>
        old?.filter((s) => s.id !== sourceId)
      );

      return { previous };
    },
    onError: (_err, _id, context) => {
      if (context?.previous) {
        queryClient.setQueryData(["rag-sources"], context.previous);
      }
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["rag-sources"] });
      queryClient.invalidateQueries({ queryKey: ["rag-stats"] });
    },
  });
}

export function useImportSource() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (payload: {
      title: string;
      source_type: "url" | "text";
      content: string;
    }) => {
      // TODO: call Supabase Edge Function or API
      await new Promise((r) => setTimeout(r, 1000));
      const newSource: RagSource = {
        id: `rag-${Date.now()}`,
        title: payload.title,
        source_type: payload.source_type,
        source_url: payload.source_type === "url" ? payload.content : null,
        chunk_count: Math.floor(Math.random() * 30) + 5,
        content_preview: payload.content.slice(0, 100),
        created_at: new Date().toISOString(),
      };
      return newSource;
    },
    onSuccess: (newSource) => {
      queryClient.setQueryData<RagSource[]>(["rag-sources"], (old) =>
        old ? [newSource, ...old] : [newSource]
      );
      queryClient.invalidateQueries({ queryKey: ["rag-stats"] });
    },
  });
}
