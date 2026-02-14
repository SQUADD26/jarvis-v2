import { Loader2, CheckCircle2, XCircle, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useWaitlist, useApproveUser, useRejectUser } from "@/hooks/use-waitlist";

export default function WaitlistAdmin() {
  const { data: entries, isLoading, error } = useWaitlist();
  const approveMutation = useApproveUser();
  const rejectMutation = useRejectUser();

  return (
    <div className="mx-auto max-w-5xl p-6">
      <div className="mb-8 flex items-center gap-3">
        <Users className="text-primary size-8" />
        <div>
          <h1 className="text-2xl font-bold">Gestione Waitlist</h1>
          <p className="text-muted-foreground text-sm">
            Approva o rifiuta le richieste di accesso
          </p>
        </div>
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="text-primary size-8 animate-spin" />
        </div>
      )}

      {error && (
        <p className="text-destructive text-center">
          Errore nel caricamento della waitlist.
        </p>
      )}

      {entries && entries.length === 0 && (
        <div className="glass rounded-xl p-12 text-center">
          <p className="text-muted-foreground">
            Nessuna richiesta in attesa di approvazione.
          </p>
        </div>
      )}

      {entries && entries.length > 0 && (
        <div className="glass overflow-hidden rounded-xl">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/10">
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                    Email
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                    Nome
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                    Motivo
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                    Stato
                  </th>
                  <th className="px-4 py-3 text-left text-sm font-medium text-muted-foreground">
                    Data
                  </th>
                  <th className="px-4 py-3 text-right text-sm font-medium text-muted-foreground">
                    Azioni
                  </th>
                </tr>
              </thead>
              <tbody>
                {entries.map((entry) => (
                  <tr
                    key={entry.id}
                    className="border-b border-white/5 last:border-0"
                  >
                    <td className="px-4 py-3 text-sm">{entry.email}</td>
                    <td className="px-4 py-3 text-sm">
                      {entry.full_name || "-"}
                    </td>
                    <td className="max-w-[200px] truncate px-4 py-3 text-sm text-muted-foreground">
                      {entry.reason || "-"}
                    </td>
                    <td className="px-4 py-3">
                      <Badge variant="secondary">{entry.status}</Badge>
                    </td>
                    <td className="px-4 py-3 text-sm text-muted-foreground">
                      {new Date(entry.created_at).toLocaleDateString("it-IT")}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <Button
                          size="sm"
                          variant="ghost"
                          className={cn(
                            "text-green-500 hover:bg-green-500/10 hover:text-green-400"
                          )}
                          disabled={approveMutation.isPending}
                          onClick={() => approveMutation.mutate(entry)}
                        >
                          <CheckCircle2 className="size-4" />
                          Approva
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          className={cn(
                            "text-red-500 hover:bg-red-500/10 hover:text-red-400"
                          )}
                          disabled={rejectMutation.isPending}
                          onClick={() => rejectMutation.mutate(entry)}
                        >
                          <XCircle className="size-4" />
                          Rifiuta
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
