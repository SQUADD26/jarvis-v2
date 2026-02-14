import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import { signIn } from "@/lib/auth";

const loginSchema = z.object({
  email: z.string().email("Inserisci un'email valida"),
  password: z.string().min(6, "La password deve avere almeno 6 caratteri"),
});

type LoginFormValues = z.infer<typeof loginSchema>;

export default function LoginPage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormValues>({
    resolver: zodResolver(loginSchema),
  });

  async function onSubmit(values: LoginFormValues) {
    try {
      setError(null);
      await signIn(values.email, values.password);
      navigate("/chat");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Errore durante l'accesso. Riprova."
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
        <div className="mb-8 text-center">
          <h1 className="text-primary text-3xl font-bold">Jarvis</h1>
          <p className="text-muted-foreground mt-2">
            Accedi al tuo assistente
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
              <p className="text-destructive text-sm">{errors.email.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="password">Password</Label>
            <Input
              id="password"
              type="password"
              placeholder="La tua password"
              {...register("password")}
            />
            {errors.password && (
              <p className="text-destructive text-sm">
                {errors.password.message}
              </p>
            )}
          </div>

          {error && (
            <p className="text-destructive text-center text-sm">{error}</p>
          )}

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting && <Loader2 className="size-4 animate-spin" />}
            Accedi
          </Button>
        </form>

        <div className="mt-6 space-y-2 text-center text-sm">
          <p className="text-muted-foreground">
            Non hai un account?{" "}
            <Link to="/register" className="text-primary hover:underline">
              Registrati
            </Link>
          </p>
          <p>
            <Link
              to="/forgot-password"
              className="text-muted-foreground hover:text-primary hover:underline"
            >
              Password dimenticata?
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
