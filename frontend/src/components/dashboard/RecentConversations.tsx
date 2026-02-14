import { MessageSquare } from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { it } from "date-fns/locale";
import { useNavigate } from "react-router-dom";
import GlassPanel from "@/components/custom/GlassPanel";
import SectionHeader from "@/components/custom/SectionHeader";

type Conversation = {
  id: string;
  preview: string;
  timestamp: string;
};

// TODO: replace with real data from Supabase
const mockConversations: Conversation[] = [
  {
    id: "c1",
    preview: "Quali sono i miei impegni per domani?",
    timestamp: new Date(Date.now() - 1800000).toISOString(),
  },
  {
    id: "c2",
    preview: "Cerca informazioni su React Server Components e fammi un riassunto",
    timestamp: new Date(Date.now() - 7200000).toISOString(),
  },
  {
    id: "c3",
    preview: "Ricordami di chiamare Marco alle 15:00",
    timestamp: new Date(Date.now() - 18000000).toISOString(),
  },
  {
    id: "c4",
    preview: "Quante email non lette ho oggi?",
    timestamp: new Date(Date.now() - 43200000).toISOString(),
  },
  {
    id: "c5",
    preview: "Aggiorna la knowledge base con il documento sulle API",
    timestamp: new Date(Date.now() - 86400000).toISOString(),
  },
];

export default function RecentConversations() {
  const navigate = useNavigate();
  const conversations = mockConversations;

  return (
    <GlassPanel>
      <SectionHeader title="Conversazioni recenti" className="mb-4" />
      {conversations.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-8 text-muted-foreground">
          <MessageSquare className="size-8 mb-2 opacity-40" />
          <p className="text-sm">Nessuna conversazione recente</p>
        </div>
      ) : (
        <ul className="space-y-1">
          {conversations.map((conv) => (
            <li key={conv.id}>
              <button
                onClick={() => navigate("/chat")}
                className="flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-white/5"
              >
                <MessageSquare className="size-4 shrink-0 text-muted-foreground" />
                <span className="flex-1 truncate text-sm">{conv.preview}</span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {formatDistanceToNow(new Date(conv.timestamp), {
                    addSuffix: true,
                    locale: it,
                  })}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </GlassPanel>
  );
}
