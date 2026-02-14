import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import SkeletonCard from "@/components/feedback/SkeletonCard";

type PageLoadingSkeletonProps = {
  className?: string;
};

export default function PageLoadingSkeleton({
  className,
}: PageLoadingSkeletonProps) {
  return (
    <div className={cn("space-y-6", className)}>
      {/* Page header skeleton */}
      <div className="flex items-center gap-3">
        <Skeleton className="size-12 rounded-lg animate-shimmer" />
        <div className="space-y-2">
          <Skeleton className="h-6 w-48 animate-shimmer" />
          <Skeleton className="h-4 w-32 animate-shimmer" />
        </div>
      </div>

      {/* Content skeleton */}
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        <SkeletonCard lines={3} />
        <SkeletonCard lines={4} />
        <SkeletonCard lines={2} />
      </div>
    </div>
  );
}
