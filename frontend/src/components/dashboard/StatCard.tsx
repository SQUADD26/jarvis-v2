import type { LucideIcon } from "lucide-react";
import { TrendingUp, TrendingDown } from "lucide-react";
import { cn } from "@/lib/utils";
import GlassCard from "@/components/custom/GlassCard";
import GlassIconBox from "@/components/custom/GlassIconBox";

type StatCardProps = {
  icon: LucideIcon;
  label: string;
  value: string | number;
  trend?: { value: number; label: string };
  iconClassName?: string;
};

export default function StatCard({
  icon,
  label,
  value,
  trend,
  iconClassName,
}: StatCardProps) {
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
