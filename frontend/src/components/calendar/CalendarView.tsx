import { useMemo } from "react";
import { it } from "date-fns/locale";
import { Calendar } from "@/components/ui/calendar";
import type { CalendarEvent } from "@/hooks/use-calendar";

type CalendarViewProps = {
  selectedDate: Date;
  onSelectDate: (date: Date) => void;
  month: Date;
  onMonthChange: (month: Date) => void;
  events: CalendarEvent[];
};

export default function CalendarView({
  selectedDate,
  onSelectDate,
  month,
  onMonthChange,
  events,
}: CalendarViewProps) {
  const eventDates = useMemo(() => {
    const dates = new Set<string>();
    for (const event of events) {
      const d = new Date(event.start);
      dates.add(`${d.getFullYear()}-${d.getMonth()}-${d.getDate()}`);
    }
    return dates;
  }, [events]);

  const modifiers = useMemo(
    () => ({
      hasEvent: (date: Date) =>
        eventDates.has(
          `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`
        ),
    }),
    [eventDates]
  );

  const modifiersClassNames = useMemo(
    () => ({
      hasEvent:
        "relative after:absolute after:bottom-1 after:left-1/2 after:-translate-x-1/2 after:size-1 after:rounded-full after:bg-primary",
    }),
    []
  );

  return (
    <div className="glass rounded-2xl p-4 flex items-center justify-center">
      <Calendar
        locale={it}
        mode="single"
        selected={selectedDate}
        onSelect={(date) => date && onSelectDate(date)}
        month={month}
        onMonthChange={onMonthChange}
        modifiers={modifiers}
        modifiersClassNames={modifiersClassNames}
        className="w-full [--cell-size:--spacing(10)] md:[--cell-size:--spacing(11)]"
        classNames={{
          month_caption: "flex items-center justify-center h-(--cell-size) w-full px-(--cell-size) capitalize",
          day: "relative w-full h-full p-0 text-center group/day aspect-square select-none",
        }}
      />
    </div>
  );
}
