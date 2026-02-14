import { cn } from "@/lib/utils";
import GlassPanel from "@/components/custom/GlassPanel";
import SectionHeader from "@/components/custom/SectionHeader";
import { useSystemHealth } from "@/hooks/use-system-health";

type StatusItemProps = {
  label: string;
  online: boolean;
  isLoading: boolean;
};

function StatusItem({ label, online, isLoading }: StatusItemProps) {
  return (
    <div className="flex items-center gap-2">
      <div
        className={cn(
          "size-2 rounded-full",
          isLoading
            ? "bg-muted-foreground animate-pulse"
            : online
              ? "bg-green-400"
              : "bg-red-400"
        )}
      />
      <span className="text-sm">{label}</span>
      <span
        className={cn(
          "ml-auto text-xs",
          isLoading
            ? "text-muted-foreground"
            : online
              ? "text-green-400"
              : "text-red-400"
        )}
      >
        {isLoading ? "..." : online ? "Online" : "Offline"}
      </span>
    </div>
  );
}

export default function SystemHealth() {
  const { api, worker, redis, supabase, isLoading } = useSystemHealth();

  return (
    <GlassPanel>
      <SectionHeader title="Stato sistema" className="mb-4" />
      <div className="grid gap-3 sm:grid-cols-2">
        <StatusItem label="API Server" online={api} isLoading={isLoading} />
        <StatusItem label="Worker" online={worker} isLoading={isLoading} />
        <StatusItem label="Redis" online={redis} isLoading={isLoading} />
        <StatusItem label="Supabase" online={supabase} isLoading={isLoading} />
      </div>
    </GlassPanel>
  );
}
