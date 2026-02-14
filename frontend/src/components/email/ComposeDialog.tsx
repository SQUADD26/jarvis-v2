import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { useSendEmail } from "@/hooks/use-emails";

const emailSchema = z.object({
  to: z.string().email("Indirizzo email non valido"),
  subject: z.string().min(1, "L'oggetto e' obbligatorio"),
  body: z.string().min(1, "Il messaggio non puo' essere vuoto"),
});

type EmailFormData = z.infer<typeof emailSchema>;

type ComposeDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export default function ComposeDialog({
  open,
  onOpenChange,
}: ComposeDialogProps) {
  const sendEmail = useSendEmail();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<EmailFormData>({
    resolver: zodResolver(emailSchema),
    defaultValues: {
      to: "",
      subject: "",
      body: "",
    },
  });

  const onSubmit = async (data: EmailFormData) => {
    await sendEmail.mutateAsync({
      to: data.to,
      subject: data.subject,
      body: data.body,
    });
    reset();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="glass border-white/10 sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>Nuova email</DialogTitle>
          <DialogDescription>Componi e invia una nuova email</DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="to">Destinatario</Label>
            <Input
              id="to"
              type="email"
              placeholder="nome@esempio.it"
              {...register("to")}
            />
            {errors.to && (
              <p className="text-xs text-destructive">{errors.to.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="subject">Oggetto</Label>
            <Input
              id="subject"
              placeholder="Oggetto dell'email"
              {...register("subject")}
            />
            {errors.subject && (
              <p className="text-xs text-destructive">
                {errors.subject.message}
              </p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="body">Messaggio</Label>
            <Textarea
              id="body"
              placeholder="Scrivi il tuo messaggio..."
              rows={8}
              {...register("body")}
            />
            {errors.body && (
              <p className="text-xs text-destructive">{errors.body.message}</p>
            )}
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Annulla
            </Button>
            <Button type="submit" disabled={sendEmail.isPending}>
              {sendEmail.isPending ? "Invio..." : "Invia"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
