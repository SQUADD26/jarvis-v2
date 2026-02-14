import { useQuery } from "@tanstack/react-query";

type DailyStat = {
  date: string;
  total_cost: number;
  total_tokens: number;
  call_count: number;
  model: string;
};

type LlmStatsReturn = {
  dailyStats: DailyStat[];
  totalCostToday: number;
  totalCostMonth: number;
  isLoading: boolean;
  error: Error | null;
};

function generateMockDailyStats(): DailyStat[] {
  const stats: DailyStat[] = [];
  const models = ["gemini-2.0-flash", "gemini-2.5-pro"];
  const now = new Date();

  for (let i = 29; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    const dateStr = date.toISOString().split("T")[0];

    for (const model of models) {
      const baseCost = model === "gemini-2.0-flash" ? 1.2 : 3.5;
      const variance = (Math.random() - 0.5) * baseCost;
      const cost = Math.max(0.1, baseCost + variance);
      const tokens = Math.round(cost * 15000);
      const calls = Math.round(cost * 8);

      stats.push({
        date: dateStr,
        total_cost: Math.round(cost * 100) / 100,
        total_tokens: tokens,
        call_count: calls,
        model,
      });
    }
  }

  return stats;
}

const mockStats = generateMockDailyStats();

export function useLlmStats(): LlmStatsReturn {
  const { data, isLoading, error } = useQuery({
    queryKey: ["llm-stats"],
    queryFn: async () => {
      // TODO: fetch from Supabase llm_stats_daily view
      await new Promise((r) => setTimeout(r, 300));
      return mockStats;
    },
    staleTime: 5 * 60 * 1000,
  });

  const dailyStats = data ?? [];

  const today = new Date().toISOString().split("T")[0];
  const totalCostToday = dailyStats
    .filter((s) => s.date === today)
    .reduce((sum, s) => sum + s.total_cost, 0);

  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1)
    .toISOString()
    .split("T")[0];
  const totalCostMonth = dailyStats
    .filter((s) => s.date >= monthStart)
    .reduce((sum, s) => sum + s.total_cost, 0);

  return {
    dailyStats,
    totalCostToday: Math.round(totalCostToday * 100) / 100,
    totalCostMonth: Math.round(totalCostMonth * 100) / 100,
    isLoading,
    error: error as Error | null,
  };
}
