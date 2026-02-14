import { Link } from "react-router-dom";
import { Hourglass } from "lucide-react";
import { cn } from "@/lib/utils";

export default function WaitlistPage() {
  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div
        className={cn(
          "glass rounded-xl p-8 w-full max-w-md text-center",
          "animate-fade-in-up"
        )}
      >
        <div className="mx-auto mb-6 flex size-16 items-center justify-center rounded-full bg-primary/10">
          <Hourglass className="text-primary size-8" />
        </div>

        <h1 className="text-2xl font-bold">Grazie per la registrazione!</h1>

        <p className="text-muted-foreground mt-4">
          La tua richiesta è in fase di revisione. Ti invieremo un'email quando
          il tuo account sarà approvato.
        </p>

        <div className="mt-8">
          <Link
            to="/login"
            className="text-primary text-sm hover:underline"
          >
            Torna al login
          </Link>
        </div>
      </div>
    </div>
  );
}
