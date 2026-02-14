import { useState } from "react";
import { Link } from "react-router-dom";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2, ArrowLeft, CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { resetPassword } from "@/lib/auth";

const forgotPasswordSchema = z.object({
  email: z.string().email("Inserisci un'email valida"),
});

type ForgotPasswordFormValues = z.infer<typeof forgotPasswordSchema>;

export default function ForgotPasswordPage() {
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<ForgotPasswordFormValues>({
    resolver: zodResolver(forgotPasswordSchema),
  });

  async function onSubmit(values: ForgotPasswordFormValues) {
    try {
      setError(null);
      await resetPassword(values.email);
      setSuccess(true);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Errore durante l'invio. Riprova."
      );
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div
        className={cn(
          "glass rounded-xl p-8 w-full max-w-md",
          "animate-fade-in-up"
        )}
      >
        {success ? (
          <div className="text-center">
            <div className="mx-auto mb-6 flex size-16 items-center justify-center rounded-full bg-primary/10">
              <CheckCircle2 className="text-primary size-8" />
            </div>
            <h1 className="text-2xl font-bold">Email inviata</h1>
            <p className="text-muted-foreground mt-4">
              Ti abbiamo inviato un'email con il link per reimpostare la
              password.
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
        ) : (
          <>
            <div className="mb-8 text-center">
              <h1 className="text-primary text-3xl font-bold">
                Password dimenticata
              </h1>
              <p className="text-muted-foreground mt-2">
                Inserisci la tua email per ricevere il link di reset
              </p>
            </div>

            <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="la-tua@email.com"
                  {...register("email")}
                />
                {errors.email && (
                  <p className="text-destructive text-sm">
                    {errors.email.message}
                  </p>
                )}
              </div>

              {error && (
                <p className="text-destructive text-center text-sm">{error}</p>
              )}

              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="size-4 animate-spin" />}
                Invia link di reset
              </Button>
            </form>

            <div className="mt-6 text-center">
              <Link
                to="/login"
                className="text-muted-foreground hover:text-primary inline-flex items-center gap-1 text-sm hover:underline"
              >
                <ArrowLeft className="size-4" />
                Torna al login
              </Link>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
