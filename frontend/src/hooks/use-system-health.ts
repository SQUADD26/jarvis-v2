import { useQuery } from "@tanstack/react-query";

type SystemHealthStatus = {
  api: boolean;
  worker: boolean;
  redis: boolean;
  supabase: boolean;
  isLoading: boolean;
};

export function useSystemHealth(): SystemHealthStatus {
  const { data, isLoading } = useQuery({
    queryKey: ["system-health"],
    queryFn: async () => {
      // TODO: ping /api/health endpoint
      await new Promise((r) => setTimeout(r, 200));
      return {
        api: true,
        worker: true,
        redis: true,
        supabase: true,
      };
    },
    refetchInterval: 30000,
    staleTime: 10000,
  });

  return {
    api: data?.api ?? false,
    worker: data?.worker ?? false,
    redis: data?.redis ?? false,
    supabase: data?.supabase ?? false,
    isLoading,
  };
}
