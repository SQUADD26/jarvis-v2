import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type GlassIconBoxProps = {
  icon: LucideIcon;
  size?: "sm" | "md" | "lg";
  variant?: "default" | "primary" | "muted";
  className?: string;
};

const sizeClasses = {
  sm: "size-8",
  md: "size-10",
  lg: "size-12",
} as const;

const iconSizeClasses = {
  sm: "size-4",
  md: "size-5",
  lg: "size-6",
} as const;

const variantClasses = {
  default: "bg-white/5",
  primary: "bg-primary/10 text-primary",
  muted: "bg-white/[0.03] text-muted-foreground",
} as const;

export default function GlassIconBox({
  icon: Icon,
  size = "md",
  variant = "default",
  className,
}: GlassIconBoxProps) {
  return (
    <div
      className={cn(
        "flex shrink-0 items-center justify-center rounded-lg",
        sizeClasses[size],
        variantClasses[variant],
        className
      )}
    >
      <Icon className={iconSizeClasses[size]} />
    </div>
  );
}
