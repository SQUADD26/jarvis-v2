import { useState } from "react";
import { Globe, AlignLeft, Upload } from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import AsyncButton from "@/components/custom/AsyncButton";
import { useImportSource } from "@/hooks/use-rag-sources";

type ImportDialogProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
};

export default function ImportDialog({ open, onOpenChange }: ImportDialogProps) {
  const [tab, setTab] = useState<"url" | "text">("url");
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [text, setText] = useState("");
  const { mutate: importSource, isPending } = useImportSource();

  const isValid =
    title.trim().length > 0 &&
    (tab === "url" ? url.trim().length > 0 : text.trim().length > 0);

  function handleSubmit() {
    if (!isValid) return;

    importSource(
      {
        title: title.trim(),
        source_type: tab,
        content: tab === "url" ? url.trim() : text.trim(),
      },
      {
        onSuccess: () => {
          resetForm();
          onOpenChange(false);
        },
      }
    );
  }

  function resetForm() {
    setTitle("");
    setUrl("");
    setText("");
    setTab("url");
  }

  return (
    <Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) resetForm();
        onOpenChange(v);
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Importa nella Knowledge Base</DialogTitle>
          <DialogDescription>
            Aggiungi un URL o del testo per arricchire le conoscenze di Jarvis.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium" htmlFor="import-title">
              Titolo
            </label>
            <Input
              id="import-title"
              placeholder="es. Documentazione React"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>

          <Tabs value={tab} onValueChange={(v) => setTab(v as "url" | "text")}>
            <TabsList className="w-full bg-white/5">
              <TabsTrigger value="url" className="flex-1 gap-1.5">
                <Globe className="size-3.5" />
                URL
              </TabsTrigger>
              <TabsTrigger value="text" className="flex-1 gap-1.5">
                <AlignLeft className="size-3.5" />
                Testo
              </TabsTrigger>
            </TabsList>

            <TabsContent value="url" className="mt-3 space-y-2">
              <label className="text-sm font-medium" htmlFor="import-url">
                Indirizzo URL
              </label>
              <Input
                id="import-url"
                type="url"
                placeholder="https://esempio.com/documento"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                La pagina verra scaricata e suddivisa in chunks per la ricerca semantica.
              </p>
            </TabsContent>

            <TabsContent value="text" className="mt-3 space-y-2">
              <label className="text-sm font-medium" htmlFor="import-text">
                Contenuto testuale
              </label>
              <Textarea
                id="import-text"
                placeholder="Incolla qui il testo da importare..."
                rows={6}
                value={text}
                onChange={(e) => setText(e.target.value)}
              />
              <p className="text-xs text-muted-foreground">
                Il testo verra suddiviso in chunks e indicizzato per la ricerca semantica.
              </p>
            </TabsContent>
          </Tabs>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Annulla
          </Button>
          <AsyncButton
            disabled={!isValid}
            isLoading={isPending}
            loadingText="Importazione..."
            icon={Upload}
            onClick={handleSubmit}
          >
            Importa
          </AsyncButton>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
