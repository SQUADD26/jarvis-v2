import * as React from "react";
import { cn } from "@/lib/utils";

type GlassPanelVariant = "default" | "elevated" | "selected" | "interactive";

type GlassPanelProps = React.HTMLAttributes<HTMLDivElement> & {
  variant?: GlassPanelVariant;
};

const variantClasses: Record<GlassPanelVariant, string> = {
  default: "glass",
  elevated: "glass-elevated",
  selected: "glass-selected",
  interactive: "glass hover:glass-elevated cursor-pointer transition-all duration-200",
};

const GlassPanel = React.forwardRef<HTMLDivElement, GlassPanelProps>(
  ({ variant = "default", className, children, ...props }, ref) => {
    return (
      <div
        ref={ref}
        className={cn("rounded-2xl p-6", variantClasses[variant], className)}
        {...props}
      >
        {children}
      </div>
    );
  }
);

GlassPanel.displayName = "GlassPanel";

export default GlassPanel;
