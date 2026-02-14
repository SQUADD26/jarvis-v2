import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  startOfMonth,
  endOfMonth,
  setHours,
  setMinutes,
  addDays,
} from "date-fns";

export type CalendarEvent = {
  id: string;
  title: string;
  description: string;
  start: string;
  end: string;
  allDay: boolean;
  color?: string;
};

export type CreateEventInput = {
  title: string;
  description: string;
  date: string;
  startTime: string;
  endTime: string;
};

function generateMockEvents(month: Date): CalendarEvent[] {
  const start = startOfMonth(month);
  const events: CalendarEvent[] = [
    {
      id: "evt-1",
      title: "Riunione team sviluppo",
      description: "Standup settimanale con il team di sviluppo",
      start: setMinutes(setHours(addDays(start, 2), 10), 0).toISOString(),
      end: setMinutes(setHours(addDays(start, 2), 11), 0).toISOString(),
      allDay: false,
      color: "lime",
    },
    {
      id: "evt-2",
      title: "Pranzo con Marco",
      description: "Ristorante Da Luigi, prenotazione per 2",
      start: setMinutes(setHours(addDays(start, 5), 13), 0).toISOString(),
      end: setMinutes(setHours(addDays(start, 5), 14), 30).toISOString(),
      allDay: false,
    },
    {
      id: "evt-3",
      title: "Dentista",
      description: "Controllo semestrale - Studio Dr. Rossi",
      start: setMinutes(setHours(addDays(start, 8), 15), 0).toISOString(),
      end: setMinutes(setHours(addDays(start, 8), 16), 0).toISOString(),
      allDay: false,
    },
    {
      id: "evt-4",
      title: "Presentazione progetto",
      description: "Presentazione al cliente del nuovo prototipo",
      start: setMinutes(setHours(addDays(start, 12), 9), 30).toISOString(),
      end: setMinutes(setHours(addDays(start, 12), 11), 0).toISOString(),
      allDay: false,
      color: "lime",
    },
    {
      id: "evt-5",
      title: "Palestra",
      description: "Sessione con il personal trainer",
      start: setMinutes(setHours(addDays(start, 14), 18), 0).toISOString(),
      end: setMinutes(setHours(addDays(start, 14), 19), 30).toISOString(),
      allDay: false,
    },
    {
      id: "evt-6",
      title: "Compleanno Sara",
      description: "Festa a casa di Sara - portare il regalo",
      start: addDays(start, 18).toISOString(),
      end: addDays(start, 18).toISOString(),
      allDay: true,
    },
    {
      id: "evt-7",
      title: "Call con il commercialista",
      description: "Revisione documenti fiscali trimestrali",
      start: setMinutes(setHours(addDays(start, 20), 11), 0).toISOString(),
      end: setMinutes(setHours(addDays(start, 20), 12), 0).toISOString(),
      allDay: false,
    },
    {
      id: "evt-8",
      title: "Cena aziendale",
      description: "Ristorante Il Giardino - evento trimestrale",
      start: setMinutes(setHours(addDays(start, 24), 20), 0).toISOString(),
      end: setMinutes(setHours(addDays(start, 24), 23), 0).toISOString(),
      allDay: false,
      color: "lime",
    },
    {
      id: "evt-9",
      title: "Deploy produzione",
      description: "Release v2.4 - coordinamento con ops",
      start: setMinutes(setHours(addDays(start, 12), 14), 0).toISOString(),
      end: setMinutes(setHours(addDays(start, 12), 16), 0).toISOString(),
      allDay: false,
    },
    {
      id: "evt-10",
      title: "Visita medica",
      description: "Controllo annuale presso ASL",
      start: setMinutes(setHours(addDays(start, 26), 8), 30).toISOString(),
      end: setMinutes(setHours(addDays(start, 26), 10), 0).toISOString(),
      allDay: false,
    },
  ];

  const monthStart = startOfMonth(month);
  const monthEnd = endOfMonth(month);

  return events.filter((e) => {
    const eventDate = new Date(e.start);
    return eventDate >= monthStart && eventDate <= monthEnd;
  });
}

export function useCalendarEvents(month: Date) {
  return useQuery({
    queryKey: ["calendar-events", month.getFullYear(), month.getMonth()],
    queryFn: async () => {
      await new Promise((r) => setTimeout(r, 300));
      return generateMockEvents(month);
    },
    staleTime: 60_000,
  });
}

export function useCreateEvent() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (input: CreateEventInput) => {
      await new Promise((r) => setTimeout(r, 500));

      const [startH, startM] = input.startTime.split(":").map(Number);
      const [endH, endM] = input.endTime.split(":").map(Number);
      const baseDate = new Date(input.date);

      const event: CalendarEvent = {
        id: `evt-${Date.now()}`,
        title: input.title,
        description: input.description,
        start: setMinutes(setHours(baseDate, startH), startM).toISOString(),
        end: setMinutes(setHours(baseDate, endH), endM).toISOString(),
        allDay: false,
      };

      return event;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["calendar-events"] });
    },
  });
}
