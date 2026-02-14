import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import GlassCard from "@/components/custom/GlassCard";
import GlassIconBox from "@/components/custom/GlassIconBox";

type GlassButtonCardProps = {
  icon: LucideIcon;
  title: string;
  description: string;
  selected?: boolean;
  onClick?: () => void;
  className?: string;
};

export default function GlassButtonCard({
  icon,
  title,
  description,
  selected = false,
  onClick,
  className,
}: GlassButtonCardProps) {
  return (
    <GlassCard
      variant={selected ? "selected" : "interactive"}
      onClick={onClick}
      className={cn("flex items-center gap-4", className)}
    >
      <GlassIconBox
        icon={icon}
        size="lg"
        variant={selected ? "primary" : "default"}
      />
      <div className="min-w-0 flex-1">
        <p className={cn("text-sm font-medium", selected && "text-primary")}>
          {title}
        </p>
        <p className="text-xs text-muted-foreground">{description}</p>
      </div>
    </GlassCard>
  );
}
