import { cn } from "@/lib/utils";
import Spinner from "@/components/feedback/Spinner";

type LoadingOverlayProps = {
  message?: string;
  className?: string;
};

export default function LoadingOverlay({
  message,
  className,
}: LoadingOverlayProps) {
  return (
    <div
      className={cn(
        "fixed inset-0 z-50 flex flex-col items-center justify-center gap-4 bg-background/80 backdrop-blur-sm",
        className
      )}
    >
      <Spinner size="xl" variant="accent" />
      {message && (
        <p className="text-sm text-muted-foreground">{message}</p>
      )}
    </div>
  );
}
