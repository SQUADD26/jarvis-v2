import { useState } from "react";
import { format } from "date-fns";
import { it } from "date-fns/locale";
import { Trash2, Brain } from "lucide-react";
import GlassCard from "@/components/custom/GlassCard";
import SectionHeader from "@/components/custom/SectionHeader";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import EmptyState from "@/components/feedback/EmptyState";
import { useMemoryFacts, useDeleteFact, type MemoryCategory } from "@/hooks/use-memory";

const categoryStyles: Record<MemoryCategory, { bg: string; text: string; label: string }> = {
  preferenza: { bg: "bg-purple-500/10", text: "text-purple-400", label: "Preferenza" },
  fatto: { bg: "bg-blue-500/10", text: "text-blue-400", label: "Fatto" },
  episodio: { bg: "bg-green-500/10", text: "text-green-400", label: "Episodio" },
  task: { bg: "bg-yellow-500/10", text: "text-yellow-400", label: "Task" },
};

export default function MemoryManager() {
  const { facts, isLoading } = useMemoryFacts();
  const deleteFact = useDeleteFact();
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const handleConfirmDelete = () => {
    if (deleteTarget) {
      deleteFact.mutate(deleteTarget);
      setDeleteTarget(null);
    }
  };

  if (!isLoading && facts.length === 0) {
    return (
      <div>
        <SectionHeader title="Memoria AI" className="mb-4" />
        <EmptyState
          icon={Brain}
          title="Nessun ricordo memorizzato"
          description="Jarvis memorizzera' automaticamente fatti e preferenze dalle tue conversazioni"
        />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <SectionHeader
        title="Memoria AI"
        action={
          <span className="text-xs text-muted-foreground">
            {facts.length} {facts.length === 1 ? "ricordo" : "ricordi"}
          </span>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2">
        {facts.map((fact) => {
          const style = categoryStyles[fact.category];
          return (
            <GlassCard key={fact.id} className="flex flex-col gap-3">
              <div className="flex items-start justify-between gap-2">
                <Badge className={`${style.bg} ${style.text} border-transparent`}>
                  {style.label}
                </Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  className="size-7 p-0 text-muted-foreground hover:text-destructive"
                  onClick={() => setDeleteTarget(fact.id)}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </div>
              <p className="text-sm text-foreground leading-relaxed">{fact.content}</p>
              <p className="text-xs text-muted-foreground">
                {format(new Date(fact.created_at), "d MMM yyyy, HH:mm", { locale: it })}
              </p>
            </GlassCard>
          );
        })}
      </div>

      <AlertDialog open={!!deleteTarget} onOpenChange={(open) => !open && setDeleteTarget(null)}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Eliminare questo ricordo?</AlertDialogTitle>
            <AlertDialogDescription>
              Questa azione non puo' essere annullata. Jarvis non avra' piu' accesso a
              questa informazione nelle conversazioni future.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Annulla</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={handleConfirmDelete}>
              Elimina
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
