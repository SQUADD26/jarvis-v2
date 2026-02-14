import { format } from "date-fns";
import { it } from "date-fns/locale";
import { FileText, Layers, Clock } from "lucide-react";
import GlassCard from "@/components/custom/GlassCard";
import GlassIconBox from "@/components/custom/GlassIconBox";
import type { RagStats } from "@/hooks/use-rag-sources";

type KnowledgeStatsProps = {
  stats: RagStats | undefined;
  isLoading: boolean;
};

export default function KnowledgeStats({ stats, isLoading }: KnowledgeStatsProps) {
  const items = [
    {
      icon: FileText,
      label: "Documenti",
      value: stats?.totalDocuments ?? 0,
    },
    {
      icon: Layers,
      label: "Chunks",
      value: stats?.totalChunks ?? 0,
    },
    {
      icon: Clock,
      label: "Ultimo Aggiornamento",
      value: stats?.lastUpdated
        ? format(new Date(stats.lastUpdated), "d MMM yyyy, HH:mm", { locale: it })
        : "N/A",
    },
  ];

  return (
    <div className="grid gap-4 sm:grid-cols-3">
      {items.map((stat) => (
        <GlassCard key={stat.label} className="flex items-center gap-3">
          <GlassIconBox icon={stat.icon} size="md" variant="primary" />
          <div className="min-w-0">
            <p className="text-xs text-muted-foreground">{stat.label}</p>
            {isLoading ? (
              <div className="mt-1 h-5 w-16 animate-pulse rounded bg-white/5" />
            ) : (
              <p className="text-lg font-semibold tabular-nums">{stat.value}</p>
            )}
          </div>
        </GlassCard>
      ))}
    </div>
  );
}
