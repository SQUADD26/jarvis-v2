import { useMemo } from "react";
import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";
import { format } from "date-fns";
import { it } from "date-fns/locale";
import GlassPanel from "@/components/custom/GlassPanel";
import SectionHeader from "@/components/custom/SectionHeader";
import { useLlmStats } from "@/hooks/use-llm-stats";

type DayPoint = {
  date: string;
  label: string;
  cost: number;
};

function CustomTooltip({
  active,
  payload,
  label,
}: {
  active?: boolean;
  payload?: Array<{ value: number }>;
  label?: string;
}) {
  if (!active || !payload?.length) return null;

  return (
    <div className="glass rounded-lg px-3 py-2 text-sm shadow-lg border border-white/10">
      <p className="text-muted-foreground">{label}</p>
      <p className="font-semibold text-primary">
        €{payload[0].value.toFixed(2)}
      </p>
    </div>
  );
}

export default function CostChart() {
  const { dailyStats } = useLlmStats();

  const chartData = useMemo<DayPoint[]>(() => {
    const grouped = new Map<string, number>();

    for (const stat of dailyStats) {
      const prev = grouped.get(stat.date) ?? 0;
      grouped.set(stat.date, prev + stat.total_cost);
    }

    return Array.from(grouped.entries())
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([date, cost]) => ({
        date,
        label: format(new Date(date), "d MMM", { locale: it }),
        cost: Math.round(cost * 100) / 100,
      }));
  }, [dailyStats]);

  return (
    <GlassPanel>
      <SectionHeader title="Costi ultimi 30 giorni" className="mb-4" />
      <div className="h-[280px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={chartData}>
            <defs>
              <linearGradient id="costGradient" x1="0" y1="0" x2="0" y2="1">
                <stop
                  offset="0%"
                  stopColor="oklch(0.87 0.2 120)"
                  stopOpacity={0.2}
                />
                <stop
                  offset="100%"
                  stopColor="oklch(0.87 0.2 120)"
                  stopOpacity={0}
                />
              </linearGradient>
            </defs>
            <CartesianGrid
              strokeDasharray="3 3"
              stroke="rgba(255,255,255,0.05)"
              vertical={false}
            />
            <XAxis
              dataKey="label"
              tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              tick={{ fill: "rgba(255,255,255,0.4)", fontSize: 12 }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v: number) => `€${v}`}
              width={50}
            />
            <Tooltip content={<CustomTooltip />} />
            <Area
              type="monotone"
              dataKey="cost"
              stroke="oklch(0.87 0.2 120)"
              strokeWidth={2}
              fill="url(#costGradient)"
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </GlassPanel>
  );
}
