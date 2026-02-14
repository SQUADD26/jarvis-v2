import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

type EmptyStateProps = {
  icon: LucideIcon;
  title: string;
  description?: string;
  action?: {
    label: string;
    onClick: () => void;
  };
  className?: string;
};

export default function EmptyState({
  icon: Icon,
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 py-16 text-center",
        className
      )}
    >
      <div className="rounded-full bg-white/5 p-4">
        <Icon className="size-8 text-muted-foreground" />
      </div>
      <div className="space-y-1">
        <h3 className="text-lg font-medium text-muted-foreground">{title}</h3>
        {description && (
          <p className="max-w-sm text-sm text-muted-foreground/70">
            {description}
          </p>
        )}
      </div>
      {action && (
        <Button variant="outline" size="sm" onClick={action.onClick}>
          {action.label}
        </Button>
      )}
    </div>
  );
}
