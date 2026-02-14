import * as React from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import Spinner from "@/components/feedback/Spinner";

type ButtonProps = React.ComponentProps<typeof Button>;

type AsyncButtonProps = ButtonProps & {
  isLoading?: boolean;
  loadingText?: string;
  icon?: LucideIcon;
};

const AsyncButton = React.forwardRef<HTMLButtonElement, AsyncButtonProps>(
  ({ isLoading = false, loadingText, icon: Icon, children, disabled, className, ...props }, ref) => {
    return (
      <Button
        ref={ref}
        disabled={disabled || isLoading}
        className={cn(className)}
        {...props}
      >
        {isLoading ? (
          <>
            <Spinner size="sm" variant="muted" />
            {loadingText && <span>{loadingText}</span>}
          </>
        ) : (
          <>
            {Icon && <Icon className="size-4" />}
            {children}
          </>
        )}
      </Button>
    );
  }
);

AsyncButton.displayName = "AsyncButton";

export default AsyncButton;
