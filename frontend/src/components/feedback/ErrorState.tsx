import {
  AlertTriangle,
  XCircle,
  Info,
  WifiOff,
  RefreshCw,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

type ErrorStateVariant = "destructive" | "warning" | "info" | "offline";

type ErrorStateProps = {
  variant?: ErrorStateVariant;
  title: string;
  description?: string;
  onRetry?: () => void;
  className?: string;
};

const variantConfig: Record<
  ErrorStateVariant,
  { icon: typeof AlertTriangle; iconClass: string }
> = {
  destructive: { icon: XCircle, iconClass: "text-destructive" },
  warning: { icon: AlertTriangle, iconClass: "text-yellow-500" },
  info: { icon: Info, iconClass: "text-blue-400" },
  offline: { icon: WifiOff, iconClass: "text-muted-foreground" },
};

export default function ErrorState({
  variant = "destructive",
  title,
  description,
  onRetry,
  className,
}: ErrorStateProps) {
  const config = variantConfig[variant];
  const Icon = config.icon;

  return (
    <div
      className={cn(
        "flex flex-col items-center justify-center gap-4 py-12 text-center",
        className
      )}
    >
      <div className={cn("rounded-full bg-white/5 p-3", config.iconClass)}>
        <Icon className="size-8" />
      </div>
      <div className="space-y-1">
        <h3 className="text-lg font-medium">{title}</h3>
        {description && (
          <p className="max-w-sm text-sm text-muted-foreground">
            {description}
          </p>
        )}
      </div>
      {onRetry && (
        <Button variant="outline" size="sm" onClick={onRetry}>
          <RefreshCw className="size-4" />
          Riprova
        </Button>
      )}
    </div>
  );
}
