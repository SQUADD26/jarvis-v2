import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import { Separator } from "@/components/ui/separator";

type SectionHeaderProps = {
  title: string;
  action?: ReactNode;
  className?: string;
};

export default function SectionHeader({
  title,
  action,
  className,
}: SectionHeaderProps) {
  return (
    <div className={cn("space-y-2", className)}>
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium uppercase tracking-wider text-muted-foreground">
          {title}
        </h2>
        {action && <div className="shrink-0">{action}</div>}
      </div>
      <Separator />
    </div>
  );
}
