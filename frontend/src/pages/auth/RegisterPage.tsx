import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { signUp } from "@/lib/auth";
import { supabase } from "@/lib/supabase";

const registerSchema = z
  .object({
    full_name: z.string().min(2, "Il nome deve avere almeno 2 caratteri"),
    email: z.string().email("Inserisci un'email valida"),
    password: z.string().min(6, "La password deve avere almeno 6 caratteri"),
    confirm_password: z.string(),
    reason: z.string().optional(),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Le password non corrispondono",
    path: ["confirm_password"],
  });

type RegisterFormValues = z.infer<typeof registerSchema>;

export default function RegisterPage() {
  const navigate = useNavigate();
  const [error, setError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<RegisterFormValues>({
    resolver: zodResolver(registerSchema),
  });

  async function onSubmit(values: RegisterFormValues) {
    try {
      setError(null);

      const { user } = await signUp(
        values.email,
        values.password,
        values.full_name
      );

      if (user) {
        await supabase.from("waitlist").insert({
          user_id: user.id,
          email: values.email,
          full_name: values.full_name,
          reason: values.reason || null,
          status: "pending",
        });
      }

      navigate("/waitlist");
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Errore durante la registrazione. Riprova."
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
          <h1 className="text-primary text-3xl font-bold">
            Unisciti a Jarvis
          </h1>
          <p className="text-muted-foreground mt-2">
            Crea il tuo account
          </p>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="full_name">Nome completo</Label>
            <Input
              id="full_name"
              type="text"
              placeholder="Mario Rossi"
              {...register("full_name")}
            />
            {errors.full_name && (
              <p className="text-destructive text-sm">
                {errors.full_name.message}
              </p>
            )}
          </div>

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
              placeholder="Almeno 6 caratteri"
              {...register("password")}
            />
            {errors.password && (
              <p className="text-destructive text-sm">
                {errors.password.message}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="confirm_password">Conferma password</Label>
            <Input
              id="confirm_password"
              type="password"
              placeholder="Ripeti la password"
              {...register("confirm_password")}
            />
            {errors.confirm_password && (
              <p className="text-destructive text-sm">
                {errors.confirm_password.message}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="reason">
              Perché vuoi unirti?{" "}
              <span className="text-muted-foreground">(opzionale)</span>
            </Label>
            <Textarea
              id="reason"
              placeholder="Raccontaci perché sei interessato..."
              {...register("reason")}
            />
          </div>

          {error && (
            <p className="text-destructive text-center text-sm">{error}</p>
          )}

          <Button type="submit" className="w-full" disabled={isSubmitting}>
            {isSubmitting && <Loader2 className="size-4 animate-spin" />}
            Registrati
          </Button>
        </form>

        <div className="mt-6 text-center text-sm">
          <p className="text-muted-foreground">
            Hai già un account?{" "}
            <Link to="/login" className="text-primary hover:underline">
              Accedi
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
