import { Component } from "react";
import type { ReactNode, ErrorInfo } from "react";
import ErrorState from "@/components/feedback/ErrorState";

type ErrorBoundaryProps = {
  children: ReactNode;
  fallback?: ReactNode;
};

type ErrorBoundaryState = {
  hasError: boolean;
  error: Error | null;
};

export default class ErrorBoundary extends Component<
  ErrorBoundaryProps,
  ErrorBoundaryState
> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, errorInfo);
  }

  handleRetry = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }

      return (
        <ErrorState
          variant="destructive"
          title="Qualcosa è andato storto"
          description={
            this.state.error?.message ||
            "Si è verificato un errore imprevisto. Riprova."
          }
          onRetry={this.handleRetry}
        />
      );
    }

    return this.props.children;
  }
}
