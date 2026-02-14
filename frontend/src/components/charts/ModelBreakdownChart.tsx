import { useMemo } from "react";
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip } from "recharts";
import GlassPanel from "@/components/custom/GlassPanel";
import SectionHeader from "@/components/custom/SectionHeader";
import { useLlmStats } from "@/hooks/use-llm-stats";

const COLORS = [
  "oklch(0.87 0.2 120)", // primary - lime green
  "oklch(0.7 0.15 200)", // chart-2 - blue
  "oklch(0.65 0.12 300)", // chart-3 - purple
];

type ModelSlice = {
  name: string;
  cost: number;
};

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: ModelSlice }>;
}) {
  if (!active || !payload?.length) return null;
  const data = payload[0].payload;

  return (
    <div className="glass rounded-lg px-3 py-2 text-sm shadow-lg border border-white/10">
      <p className="text-muted-foreground">{data.name}</p>
      <p className="font-semibold text-primary">€{data.cost.toFixed(2)}</p>
    </div>
  );
}

export default function ModelBreakdownChart() {
  const { dailyStats } = useLlmStats();

  const chartData = useMemo<ModelSlice[]>(() => {
    const grouped = new Map<string, number>();

    for (const stat of dailyStats) {
      const prev = grouped.get(stat.model) ?? 0;
      grouped.set(stat.model, prev + stat.total_cost);
    }

    return Array.from(grouped.entries())
      .map(([name, cost]) => ({
        name,
        cost: Math.round(cost * 100) / 100,
      }))
      .sort((a, b) => b.cost - a.cost);
  }, [dailyStats]);

  const total = chartData.reduce((sum, d) => sum + d.cost, 0);

  return (
    <GlassPanel>
      <SectionHeader title="Costi per modello" className="mb-4" />
      <div className="h-[220px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={chartData}
              cx="50%"
              cy="50%"
              innerRadius={55}
              outerRadius={80}
              paddingAngle={4}
              dataKey="cost"
              stroke="none"
            >
              {chartData.map((_, index) => (
                <Cell
                  key={`cell-${index}`}
                  fill={COLORS[index % COLORS.length]}
                />
              ))}
            </Pie>
            <Tooltip content={<CustomTooltip />} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="mt-2 space-y-2">
        {chartData.map((item, index) => (
          <div key={item.name} className="flex items-center gap-2 text-sm">
            <div
              className="size-3 rounded-full"
              style={{ backgroundColor: COLORS[index % COLORS.length] }}
            />
            <span className="flex-1 text-muted-foreground">{item.name}</span>
            <span className="font-medium">€{item.cost.toFixed(2)}</span>
            <span className="text-xs text-muted-foreground">
              ({((item.cost / total) * 100).toFixed(0)}%)
            </span>
          </div>
        ))}
      </div>
    </GlassPanel>
  );
}
