import {
  Coins,
  TrendingUp,
  TrendingDown,
  BarChart3,
  Cpu,
  CalendarDays,
} from "lucide-react";
import { cn } from "@/lib/utils";
import GlassCard from "@/components/custom/GlassCard";
import GlassIconBox from "@/components/custom/GlassIconBox";
import { useMonthlyCosts } from "@/hooks/use-costs";

type KpiCardProps = {
  icon: typeof Coins;
  iconClassName: string;
  label: string;
  value: string;
  trend?: { value: number; label: string };
};

function KpiCard({ icon, iconClassName, label, value, trend }: KpiCardProps) {
  const isPositive = trend && trend.value >= 0;

  return (
    <GlassCard className="flex flex-col gap-3">
      <div className="flex items-center justify-between">
        <GlassIconBox icon={icon} size="md" className={iconClassName} />
        {trend && (
          <div
            className={cn(
              "flex items-center gap-1 text-xs font-medium",
              isPositive ? "text-green-400" : "text-red-400"
            )}
          >
            {isPositive ? (
              <TrendingUp className="size-3" />
            ) : (
              <TrendingDown className="size-3" />
            )}
            <span>
              {isPositive ? "+" : ""}
              {trend.value}%
            </span>
          </div>
        )}
      </div>
      <div>
        <p className="text-2xl font-bold font-heading">{value}</p>
        <p className="text-sm text-muted-foreground">{label}</p>
      </div>
      {trend && (
        <p className="text-xs text-muted-foreground">{trend.label}</p>
      )}
    </GlassCard>
  );
}

export default function CostOverview() {
  const { monthlyCosts } = useMonthlyCosts();

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <KpiCard
        icon={Coins}
        iconClassName="bg-primary/10 text-primary"
        label="Totale Mese"
        value={`€${monthlyCosts.totalMonth.toFixed(2)}`}
        trend={{ value: monthlyCosts.trendPercent, label: "vs mese precedente" }}
      />
      <KpiCard
        icon={CalendarDays}
        iconClassName="bg-blue-500/10 text-blue-400"
        label="Media Giorno"
        value={`€${monthlyCosts.avgDay.toFixed(2)}`}
      />
      <KpiCard
        icon={BarChart3}
        iconClassName="bg-purple-500/10 text-purple-400"
        label="Chiamate Totali"
        value={monthlyCosts.totalCalls.toLocaleString("it-IT")}
      />
      <KpiCard
        icon={Cpu}
        iconClassName="bg-yellow-500/10 text-yellow-400"
        label="Modello Top"
        value={monthlyCosts.topModel.replace("gemini-", "")}
      />
    </div>
  );
}
