import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { useAuth } from "@/hooks/use-auth";

interface AuthGuardProps {
  children: ReactNode;
}

export default function AuthGuard({ children }: AuthGuardProps) {
  const { user, loading, profile } = useAuth();

  if (loading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <Loader2 className="text-primary size-8 animate-spin" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  if (profile && profile.status !== "approved") {
    return <Navigate to="/waitlist" replace />;
  }

  return <>{children}</>;
}
