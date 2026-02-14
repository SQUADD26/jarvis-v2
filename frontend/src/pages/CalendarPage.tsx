import { useState, useMemo } from "react";
import { motion, type Variants } from "framer-motion";
import { isSameDay } from "date-fns";
import { CalendarDays, Plus } from "lucide-react";
import PageHeader from "@/components/custom/PageHeader";
import { Button } from "@/components/ui/button";
import CalendarView from "@/components/calendar/CalendarView";
import EventList from "@/components/calendar/EventList";
import CreateEventDialog from "@/components/calendar/CreateEventDialog";
import { useCalendarEvents } from "@/hooks/use-calendar";

const container: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08 },
  },
};

const item: Variants = {
  hidden: { opacity: 0, y: 16 },
  show: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.4, ease: "easeOut" as const },
  },
};

export default function CalendarPage() {
  const [selectedDate, setSelectedDate] = useState(new Date());
  const [month, setMonth] = useState(new Date());
  const [createOpen, setCreateOpen] = useState(false);

  const { data: events = [], isLoading } = useCalendarEvents(month);

  const selectedDayEvents = useMemo(
    () =>
      events
        .filter((e) => isSameDay(new Date(e.start), selectedDate))
        .sort(
          (a, b) =>
            new Date(a.start).getTime() - new Date(b.start).getTime()
        ),
    [events, selectedDate]
  );

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      <motion.div variants={item}>
        <PageHeader
          title="Calendario"
          description="Gestisci i tuoi eventi e appuntamenti"
          icon={CalendarDays}
          actions={
            <Button
              size="sm"
              className="gap-1.5"
              onClick={() => setCreateOpen(true)}
            >
              <Plus className="size-4" />
              Nuovo evento
            </Button>
          }
        />
      </motion.div>

      <motion.div
        variants={item}
        className="grid gap-6 lg:grid-cols-[auto_1fr]"
      >
        <div className="lg:w-[340px]">
          <CalendarView
            selectedDate={selectedDate}
            onSelectDate={setSelectedDate}
            month={month}
            onMonthChange={setMonth}
            events={events}
          />
        </div>

        <div className="min-h-0">
          <EventList
            date={selectedDate}
            events={selectedDayEvents}
            isLoading={isLoading}
          />
        </div>
      </motion.div>

      <CreateEventDialog
        open={createOpen}
        onOpenChange={setCreateOpen}
        defaultDate={selectedDate}
      />
    </motion.div>
  );
}
