import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import GlassIconBox from "@/components/custom/GlassIconBox";

type PageHeaderProps = {
  title: string;
  description?: string;
  icon?: LucideIcon;
  actions?: ReactNode;
  className?: string;
};

export default function PageHeader({
  title,
  description,
  icon,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <div className={cn("flex items-start justify-between gap-4", className)}>
      <div className="flex items-center gap-3">
        {icon && <GlassIconBox icon={icon} size="lg" variant="primary" />}
        <div>
          <h1 className="text-2xl font-heading font-semibold">{title}</h1>
          {description && (
            <p className="text-sm text-muted-foreground">{description}</p>
          )}
        </div>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}
