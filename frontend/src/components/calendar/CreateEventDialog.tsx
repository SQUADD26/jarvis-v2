import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { format } from "date-fns";
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
import { useCreateEvent } from "@/hooks/use-calendar";

const eventSchema = z.object({
  title: z.string().min(1, "Il titolo e' obbligatorio"),
  date: z.string().min(1, "La data e' obbligatoria"),
  startTime: z.string().min(1, "L'ora di inizio e' obbligatoria"),
  endTime: z.string().min(1, "L'ora di fine e' obbligatoria"),
  description: z.string(),
}).superRefine((data, ctx) => {
  if (data.endTime <= data.startTime) {
    ctx.addIssue({
      code: z.ZodIssueCode.custom,
      message: "L'ora di fine deve essere dopo l'ora di inizio",
      path: ["endTime"],
    });
  }
});

type EventFormData = z.infer<typeof eventSchema>;

type CreateEventDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  defaultDate?: Date;
};

export default function CreateEventDialog({
  open,
  onOpenChange,
  defaultDate,
}: CreateEventDialogProps) {
  const createEvent = useCreateEvent();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<EventFormData>({
    resolver: zodResolver(eventSchema),
    defaultValues: {
      title: "",
      date: defaultDate ? format(defaultDate, "yyyy-MM-dd") : "",
      startTime: "09:00",
      endTime: "10:00",
      description: "",
    },
  });

  const onSubmit = async (data: EventFormData) => {
    await createEvent.mutateAsync({
      title: data.title,
      description: data.description ?? "",
      date: data.date,
      startTime: data.startTime,
      endTime: data.endTime,
    });
    reset();
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="glass border-white/10 sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Nuovo evento</DialogTitle>
          <DialogDescription>
            Crea un nuovo evento nel calendario
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="title">Titolo</Label>
            <Input
              id="title"
              placeholder="Es: Riunione di lavoro"
              {...register("title")}
            />
            {errors.title && (
              <p className="text-xs text-destructive">{errors.title.message}</p>
            )}
          </div>

          <div className="space-y-2">
            <Label htmlFor="date">Data</Label>
            <Input id="date" type="date" {...register("date")} />
            {errors.date && (
              <p className="text-xs text-destructive">{errors.date.message}</p>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-2">
              <Label htmlFor="startTime">Ora inizio</Label>
              <Input id="startTime" type="time" {...register("startTime")} />
              {errors.startTime && (
                <p className="text-xs text-destructive">
                  {errors.startTime.message}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="endTime">Ora fine</Label>
              <Input id="endTime" type="time" {...register("endTime")} />
              {errors.endTime && (
                <p className="text-xs text-destructive">
                  {errors.endTime.message}
                </p>
              )}
            </div>
          </div>

          <div className="space-y-2">
            <Label htmlFor="description">Descrizione</Label>
            <Textarea
              id="description"
              placeholder="Dettagli sull'evento..."
              rows={3}
              {...register("description")}
            />
          </div>

          <DialogFooter>
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
            >
              Annulla
            </Button>
            <Button type="submit" disabled={createEvent.isPending}>
              {createEvent.isPending ? "Creazione..." : "Crea evento"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
