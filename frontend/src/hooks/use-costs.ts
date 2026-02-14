import { useQuery } from "@tanstack/react-query";

export type DailyStatRow = {
  date: string;
  model: string;
  call_count: number;
  input_tokens: number;
  output_tokens: number;
  total_cost: number;
};

type MonthlyCosts = {
  totalMonth: number;
  avgDay: number;
  totalCalls: number;
  topModel: string;
  trendPercent: number;
};

function generateMockDaily(days: number): DailyStatRow[] {
  const rows: DailyStatRow[] = [];
  const models = ["gemini-2.0-flash", "gemini-2.5-pro"];
  const now = new Date();

  for (let i = days - 1; i >= 0; i--) {
    const date = new Date(now);
    date.setDate(date.getDate() - i);
    const dateStr = date.toISOString().split("T")[0];

    for (const model of models) {
      const isFlash = model === "gemini-2.0-flash";
      const baseCost = isFlash ? 0.8 : 2.2;
      const variance = (Math.random() - 0.3) * baseCost * 0.6;
      const cost = Math.max(0.05, baseCost + variance);
      const calls = Math.round(isFlash ? 25 + Math.random() * 30 : 8 + Math.random() * 15);
      const inputTokens = Math.round(calls * (isFlash ? 1200 : 3500) + Math.random() * 5000);
      const outputTokens = Math.round(calls * (isFlash ? 800 : 2200) + Math.random() * 3000);

      rows.push({
        date: dateStr,
        model,
        call_count: calls,
        input_tokens: inputTokens,
        output_tokens: outputTokens,
        total_cost: Math.round(cost * 100) / 100,
      });
    }
  }

  return rows;
}

const mockDaily = generateMockDaily(30);

export function useDailyStats(days = 30) {
  const { data, isLoading, error } = useQuery({
    queryKey: ["costs-daily", days],
    queryFn: async () => {
      // TODO: fetch from Supabase llm_stats_daily view
      await new Promise((r) => setTimeout(r, 250));
      return mockDaily.slice(-days * 2);
    },
    staleTime: 5 * 60 * 1000,
  });

  return {
    dailyStats: data ?? [],
    isLoading,
    error: error as Error | null,
  };
}

export function useMonthlyCosts() {
  const { dailyStats, isLoading, error } = useDailyStats(30);

  const now = new Date();
  const monthStart = new Date(now.getFullYear(), now.getMonth(), 1)
    .toISOString()
    .split("T")[0];

  const monthStats = dailyStats.filter((s) => s.date >= monthStart);
  const totalMonth = monthStats.reduce((sum, s) => sum + s.total_cost, 0);
  const totalCalls = monthStats.reduce((sum, s) => sum + s.call_count, 0);

  const daysInMonth = now.getDate();
  const avgDay = daysInMonth > 0 ? totalMonth / daysInMonth : 0;

  // Top model by cost
  const costByModel = new Map<string, number>();
  for (const s of monthStats) {
    costByModel.set(s.model, (costByModel.get(s.model) ?? 0) + s.total_cost);
  }
  let topModel = "N/A";
  let maxCost = 0;
  for (const [model, cost] of costByModel) {
    if (cost > maxCost) {
      maxCost = cost;
      topModel = model;
    }
  }

  // Compare with previous month period
  const prevMonthEnd = new Date(now.getFullYear(), now.getMonth(), 0);
  const prevMonthStart = new Date(prevMonthEnd.getFullYear(), prevMonthEnd.getMonth(), 1);
  const prevStartStr = prevMonthStart.toISOString().split("T")[0];
  const prevEndStr = prevMonthEnd.toISOString().split("T")[0];
  const prevStats = dailyStats.filter((s) => s.date >= prevStartStr && s.date <= prevEndStr);
  const prevTotal = prevStats.reduce((sum, s) => sum + s.total_cost, 0);
  const trendPercent = prevTotal > 0 ? ((totalMonth - prevTotal) / prevTotal) * 100 : 0;

  const monthlyCosts: MonthlyCosts = {
    totalMonth: Math.round(totalMonth * 100) / 100,
    avgDay: Math.round(avgDay * 100) / 100,
    totalCalls,
    topModel,
    trendPercent: Math.round(trendPercent),
  };

  return {
    monthlyCosts,
    isLoading,
    error,
  };
}
