import { useState, useMemo } from "react";
import { formatDistanceToNow } from "date-fns";
import { it } from "date-fns/locale";
import { motion } from "framer-motion";
import { Search, Star } from "lucide-react";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { Email } from "@/hooks/use-emails";

type InboxListProps = {
  emails: Email[];
  selectedId: string | null;
  onSelect: (email: Email) => void;
  isLoading: boolean;
};

const itemVariants = {
  hidden: { opacity: 0, x: -8 },
  show: { opacity: 1, x: 0, transition: { duration: 0.25, ease: "easeOut" as const } },
};

function getInitials(name: string): string {
  const parts = name.split(" ");
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return name.slice(0, 2).toUpperCase();
}

function getAvatarColor(name: string): string {
  const colors = [
    "bg-primary/20 text-primary",
    "bg-blue-500/20 text-blue-400",
    "bg-purple-500/20 text-purple-400",
    "bg-amber-500/20 text-amber-400",
    "bg-rose-500/20 text-rose-400",
    "bg-cyan-500/20 text-cyan-400",
  ];
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = name.charCodeAt(i) + ((hash << 5) - hash);
  }
  return colors[Math.abs(hash) % colors.length];
}

export default function InboxList({
  emails,
  selectedId,
  onSelect,
  isLoading,
}: InboxListProps) {
  const [search, setSearch] = useState("");

  const filteredEmails = useMemo(() => {
    if (!search.trim()) return emails;
    const q = search.toLowerCase();
    return emails.filter(
      (e) =>
        e.from.toLowerCase().includes(q) ||
        e.subject.toLowerCase().includes(q) ||
        e.snippet.toLowerCase().includes(q)
    );
  }, [emails, search]);

  return (
    <div className="flex flex-col h-full">
      <div className="p-4 pb-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 size-4 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Cerca email..."
            className="pl-9"
          />
        </div>
      </div>

      <ScrollArea className="flex-1">
        <div className="px-2 pb-2">
          {isLoading ? (
            <div className="space-y-1 px-2">
              {[1, 2, 3, 4, 5].map((i) => (
                <div
                  key={i}
                  className="rounded-lg p-3 animate-pulse space-y-2"
                >
                  <div className="flex items-center gap-3">
                    <div className="size-9 rounded-full bg-white/5" />
                    <div className="flex-1 space-y-1.5">
                      <div className="h-3.5 w-1/3 bg-white/5 rounded" />
                      <div className="h-3 w-2/3 bg-white/5 rounded" />
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : filteredEmails.length === 0 ? (
            <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
              {search ? "Nessun risultato" : "Nessuna email"}
            </div>
          ) : (
            <motion.div
              initial="hidden"
              animate="show"
              variants={{
                hidden: { opacity: 0 },
                show: {
                  opacity: 1,
                  transition: { staggerChildren: 0.03 },
                },
              }}
              className="space-y-0.5"
            >
              {filteredEmails.map((email) => (
                <motion.button
                  key={email.id}
                  variants={itemVariants}
                  onClick={() => onSelect(email)}
                  className={cn(
                    "w-full text-left rounded-lg p-3 transition-all duration-150 group",
                    selectedId === email.id
                      ? "glass-selected"
                      : "hover:bg-white/[0.03]"
                  )}
                >
                  <div className="flex items-start gap-3">
                    <div className="relative shrink-0">
                      <div
                        className={cn(
                          "size-9 rounded-full flex items-center justify-center text-xs font-medium",
                          getAvatarColor(email.from)
                        )}
                      >
                        {getInitials(email.from)}
                      </div>
                      {!email.read && (
                        <div className="absolute -top-0.5 -right-0.5 size-2.5 rounded-full bg-primary ring-2 ring-background" />
                      )}
                    </div>

                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-2">
                        <span
                          className={cn(
                            "text-sm truncate",
                            !email.read
                              ? "font-semibold text-foreground"
                              : "font-medium text-muted-foreground"
                          )}
                        >
                          {email.from}
                        </span>
                        <div className="flex items-center gap-1.5 shrink-0">
                          {email.starred && (
                            <Star className="size-3 fill-amber-400 text-amber-400" />
                          )}
                          <span className="text-[11px] text-muted-foreground">
                            {formatDistanceToNow(new Date(email.date), {
                              addSuffix: false,
                              locale: it,
                            })}
                          </span>
                        </div>
                      </div>
                      <p
                        className={cn(
                          "text-sm truncate",
                          !email.read
                            ? "text-foreground/90"
                            : "text-muted-foreground"
                        )}
                      >
                        {email.subject}
                      </p>
                      <p className="text-xs text-muted-foreground/60 truncate mt-0.5">
                        {email.snippet}
                      </p>
                    </div>
                  </div>
                </motion.button>
              ))}
            </motion.div>
          )}
        </div>
      </ScrollArea>
    </div>
  );
}
