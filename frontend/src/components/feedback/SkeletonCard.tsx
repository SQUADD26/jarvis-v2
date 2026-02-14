import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

type SkeletonCardProps = {
  hasAvatar?: boolean;
  lines?: number;
  className?: string;
};

export default function SkeletonCard({
  hasAvatar = false,
  lines = 3,
  className,
}: SkeletonCardProps) {
  return (
    <div
      className={cn(
        "glass rounded-xl p-4 space-y-4",
        className
      )}
    >
      {hasAvatar && (
        <div className="flex items-center gap-3">
          <Skeleton className="size-10 rounded-full animate-shimmer" />
          <div className="flex-1 space-y-2">
            <Skeleton className="h-4 w-1/3 animate-shimmer" />
            <Skeleton className="h-3 w-1/4 animate-shimmer" />
          </div>
        </div>
      )}
      <div className="space-y-2">
        {Array.from({ length: lines }).map((_, i) => (
          <Skeleton
            key={i}
            className={cn(
              "h-3 animate-shimmer",
              i === lines - 1 ? "w-2/3" : "w-full"
            )}
          />
        ))}
      </div>
    </div>
  );
}
