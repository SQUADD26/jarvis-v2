import { format, differenceInMinutes } from "date-fns";
import { it } from "date-fns/locale";
import { motion, AnimatePresence } from "framer-motion";
import { Clock, CalendarDays } from "lucide-react";
import GlassCard from "@/components/custom/GlassCard";
import GlassIconBox from "@/components/custom/GlassIconBox";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { CalendarEvent } from "@/hooks/use-calendar";

type EventListProps = {
  date: Date;
  events: CalendarEvent[];
  isLoading: boolean;
};

function formatDuration(start: string, end: string): string {
  const mins = differenceInMinutes(new Date(end), new Date(start));
  if (mins < 60) return `${mins} min`;
  const hours = Math.floor(mins / 60);
  const remainder = mins % 60;
  if (remainder === 0) return `${hours}h`;
  return `${hours}h ${remainder}min`;
}

const listVariants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.06 },
  },
};

const itemVariants = {
  hidden: { opacity: 0, y: 12 },
  show: { opacity: 1, y: 0, transition: { duration: 0.3, ease: "easeOut" as const } },
  exit: { opacity: 0, y: -8, transition: { duration: 0.2 } },
};

export default function EventList({ date, events, isLoading }: EventListProps) {
  const formattedDate = format(date, "EEEE d MMMM", { locale: it });

  return (
    <div className="glass rounded-2xl p-6 flex flex-col h-full min-h-[400px]">
      <div className="flex items-center justify-between mb-4">
        <div>
          <h2 className="text-lg font-semibold capitalize">{formattedDate}</h2>
          <p className="text-sm text-muted-foreground">
            {events.length === 0
              ? "Nessun evento"
              : `${events.length} event${events.length === 1 ? "o" : "i"}`}
          </p>
        </div>
      </div>

      <ScrollArea className="flex-1">
        <AnimatePresence mode="wait">
          {isLoading ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="space-y-3"
            >
              {[1, 2, 3].map((i) => (
                <div
                  key={i}
                  className="glass rounded-xl p-4 animate-pulse space-y-2"
                >
                  <div className="h-4 w-2/3 bg-white/5 rounded" />
                  <div className="h-3 w-1/3 bg-white/5 rounded" />
                </div>
              ))}
            </motion.div>
          ) : events.length === 0 ? (
            <motion.div
              key="empty"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="flex flex-col items-center justify-center py-16 text-muted-foreground"
            >
              <CalendarDays className="size-12 mb-3 opacity-30" />
              <p className="text-sm">Nessun evento per questo giorno</p>
              <p className="text-xs mt-1 opacity-60">
                Crea un nuovo evento con il pulsante in alto
              </p>
            </motion.div>
          ) : (
            <motion.div
              key={date.toISOString()}
              variants={listVariants}
              initial="hidden"
              animate="show"
              className="space-y-3 pr-2"
            >
              {events.map((event) => (
                <motion.div key={event.id} variants={itemVariants}>
                  <GlassCard
                    variant="interactive"
                    className="space-y-2"
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-3 min-w-0">
                        <GlassIconBox
                          icon={Clock}
                          size="sm"
                          variant="primary"
                        />
                        <div className="min-w-0">
                          <h3 className="font-medium text-sm truncate">
                            {event.title}
                          </h3>
                          {!event.allDay && (
                            <p className="text-xs text-muted-foreground">
                              {format(new Date(event.start), "HH:mm")} -{" "}
                              {format(new Date(event.end), "HH:mm")}
                            </p>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        {event.allDay ? (
                          <Badge variant="secondary" className="text-[10px]">
                            Tutto il giorno
                          </Badge>
                        ) : (
                          <Badge variant="outline" className="text-[10px]">
                            {formatDuration(event.start, event.end)}
                          </Badge>
                        )}
                      </div>
                    </div>
                    {event.description && (
                      <p className="text-xs text-muted-foreground pl-11 line-clamp-2">
                        {event.description}
                      </p>
                    )}
                  </GlassCard>
                </motion.div>
              ))}
            </motion.div>
          )}
        </AnimatePresence>
      </ScrollArea>
    </div>
  );
}
