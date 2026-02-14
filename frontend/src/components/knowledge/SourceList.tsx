import { useState } from "react";
import { format } from "date-fns";
import { it } from "date-fns/locale";
import {
  Globe,
  FileText,
  AlignLeft,
  Trash2,
  Layers,
  Calendar,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import GlassCard from "@/components/custom/GlassCard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import AsyncButton from "@/components/custom/AsyncButton";
import EmptyState from "@/components/feedback/EmptyState";
import type { RagSource, SourceType } from "@/hooks/use-rag-sources";
import { useDeleteSource } from "@/hooks/use-rag-sources";
import { cn } from "@/lib/utils";

const typeConfig: Record<
  SourceType,
  { label: string; icon: typeof Globe; className: string }
> = {
  url: {
    label: "URL",
    icon: Globe,
    className: "bg-blue-500/15 text-blue-400 border-blue-500/30",
  },
  file: {
    label: "File",
    icon: FileText,
    className: "bg-purple-500/15 text-purple-400 border-purple-500/30",
  },
  text: {
    label: "Testo",
    icon: AlignLeft,
    className: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  },
};

type SourceListProps = {
  sources: RagSource[];
};

export default function SourceList({ sources }: SourceListProps) {
  const [deleteTarget, setDeleteTarget] = useState<RagSource | null>(null);
  const { mutate: deleteSource, isPending: isDeleting } = useDeleteSource();

  function handleConfirmDelete() {
    if (!deleteTarget) return;
    deleteSource(deleteTarget.id, {
      onSettled: () => setDeleteTarget(null),
    });
  }

  if (sources.length === 0) {
    return (
      <EmptyState
        icon={FileText}
        title="Nessun documento"
        description="Importa documenti, URL o testi per arricchire la knowledge base di Jarvis."
      />
    );
  }

  return (
    <>
      <div className="space-y-2">
        <AnimatePresence mode="popLayout">
          {sources.map((source) => {
            const config = typeConfig[source.source_type];
            const TypeIcon = config.icon;

            return (
              <motion.div
                key={source.id}
                layout
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.2 }}
              >
                <GlassCard className="group flex items-center gap-3">
                  <div
                    className={cn(
                      "flex size-10 shrink-0 items-center justify-center rounded-lg",
                      "bg-white/5"
                    )}
                  >
                    <TypeIcon className="size-5 text-muted-foreground" />
                  </div>

                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex items-center gap-2">
                      <h3 className="truncate text-sm font-medium">
                        {source.title}
                      </h3>
                      <Badge className={cn("shrink-0", config.className)}>
                        {config.label}
                      </Badge>
                    </div>
                    <div className="flex items-center gap-3 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Layers className="size-3" />
                        {source.chunk_count} chunks
                      </span>
                      <span className="flex items-center gap-1">
                        <Calendar className="size-3" />
                        {format(new Date(source.created_at), "d MMM yyyy", {
                          locale: it,
                        })}
                      </span>
                    </div>
                  </div>

                  <Button
                    variant="ghost"
                    size="icon"
                    className="shrink-0 text-muted-foreground opacity-0 transition-opacity group-hover:opacity-100 hover:text-red-400"
                    onClick={() => setDeleteTarget(source)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </GlassCard>
              </motion.div>
            );
          })}
        </AnimatePresence>
      </div>

      <Dialog
        open={deleteTarget !== null}
        onOpenChange={(open) => {
          if (!open) setDeleteTarget(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Conferma eliminazione</DialogTitle>
            <DialogDescription>
              Stai per eliminare &quot;{deleteTarget?.title}&quot; e tutti i suoi chunks.
              Questa azione non puo essere annullata.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteTarget(null)}>
              Annulla
            </Button>
            <AsyncButton
              variant="destructive"
              isLoading={isDeleting}
              loadingText="Eliminazione..."
              icon={Trash2}
              onClick={handleConfirmDelete}
            >
              Elimina
            </AsyncButton>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
