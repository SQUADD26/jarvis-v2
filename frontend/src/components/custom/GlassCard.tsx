import * as React from "react";
import { cn } from "@/lib/utils";

type GlassCardVariant = "default" | "elevated" | "selected" | "interactive";

type GlassCardProps = React.HTMLAttributes<HTMLDivElement> & {
  variant?: GlassCardVariant;
};

const variantClasses: Record<GlassCardVariant, string> = {
  default: "glass",
  elevated: "glass-elevated",
  selected: "glass-selected",
  interactive: "glass hover:glass-elevated cursor-pointer transition-all duration-200",
};

const GlassCard = React.forwardRef<HTMLDivElement, GlassCardProps>(
  ({ variant = "default", className, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn("rounded-xl p-4", variantClasses[variant], className)}
        {...props}
      >
        {children}
      </div>
    );
  }
);

GlassCard.displayName = "GlassCard";

export default GlassCard;
