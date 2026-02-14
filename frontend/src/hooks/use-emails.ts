import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";

export type Email = {
  id: string;
  from: string;
  fromEmail: string;
  to: string;
  toEmail: string;
  subject: string;
  body: string;
  snippet: string;
  date: string;
  read: boolean;
  starred: boolean;
  labels: string[];
};

export type SendEmailInput = {
  to: string;
  subject: string;
  body: string;
};

const mockEmails: Email[] = [
  {
    id: "email-1",
    from: "Marco Bianchi",
    fromEmail: "marco.bianchi@studio.it",
    to: "Roberto Bondici",
    toEmail: "roberto@example.com",
    subject: "Documenti per la riunione di giovedi",
    body: "Ciao Roberto,\n\nTi invio in allegato i documenti che abbiamo discusso per la riunione di giovedi. Ti chiedo di darci un'occhiata prima dell'incontro cosi possiamo essere allineati.\n\nIn particolare, vorrei che verificassi i numeri nella sezione 3 del report trimestrale. Ho notato alcune discrepanze che potremmo dover discutere.\n\nFammi sapere se hai domande.\n\nA presto,\nMarco",
    snippet: "Ti invio in allegato i documenti che abbiamo discusso per la riunione di giovedi...",
    date: new Date(Date.now() - 1800000).toISOString(),
    read: false,
    starred: false,
    labels: ["lavoro"],
  },
  {
    id: "email-2",
    from: "Sara Colombo",
    fromEmail: "sara.colombo@gmail.com",
    to: "Roberto Bondici",
    toEmail: "roberto@example.com",
    subject: "Re: Festa di sabato",
    body: "Ciao Roberto!\n\nGrazie per la conferma! Allora ti aspetto sabato alle 20:00 a casa mia. Porta pure qualcosa da bere se vuoi, ma non e' obbligatorio.\n\nCi saranno anche Luca, Francesca e Paolo. Sara' una bella serata!\n\nA sabato,\nSara",
    snippet: "Grazie per la conferma! Allora ti aspetto sabato alle 20:00 a casa mia...",
    date: new Date(Date.now() - 3600000).toISOString(),
    read: false,
    starred: true,
    labels: ["personale"],
  },
  {
    id: "email-3",
    from: "Amazon",
    fromEmail: "noreply@amazon.it",
    to: "Roberto Bondici",
    toEmail: "roberto@example.com",
    subject: "Il tuo ordine e' stato spedito",
    body: "Gentile cliente,\n\nIl tuo ordine #405-1234567 e' stato spedito e sara' consegnato entro il 16 febbraio.\n\nArticolo: Logitech MX Master 3S\nIndirizzo di consegna: Via Roma 42, Milano\n\nPuoi tracciare il tuo pacco qui: https://amazon.it/tracking/...\n\nGrazie per aver acquistato su Amazon.it",
    snippet: "Il tuo ordine #405-1234567 e' stato spedito e sara' consegnato entro il 16 febbraio...",
    date: new Date(Date.now() - 7200000).toISOString(),
    read: true,
    starred: false,
    labels: ["acquisti"],
  },
  {
    id: "email-4",
    from: "Dr. Giuseppe Rossi",
    fromEmail: "studio.rossi@pec.it",
    to: "Roberto Bondici",
    toEmail: "roberto@example.com",
    subject: "Conferma appuntamento 20 febbraio",
    body: "Gentile Sig. Bondici,\n\nLe confermo l'appuntamento per il giorno 20 febbraio alle ore 15:00 presso il nostro studio in Via Manzoni 15.\n\nLe ricordo di portare la tessera sanitaria e i referti precedenti.\n\nCordiali saluti,\nDr. Giuseppe Rossi",
    snippet: "Le confermo l'appuntamento per il giorno 20 febbraio alle ore 15:00...",
    date: new Date(Date.now() - 14400000).toISOString(),
    read: true,
    starred: false,
    labels: ["salute"],
  },
  {
    id: "email-5",
    from: "LinkedIn",
    fromEmail: "notifications@linkedin.com",
    to: "Roberto Bondici",
    toEmail: "roberto@example.com",
    subject: "3 nuove connessioni e 5 nuovi messaggi",
    body: "Ciao Roberto,\n\nHai 3 nuove richieste di connessione e 5 messaggi non letti.\n\nLe tue connessioni recenti:\n- Andrea Ferretti, Senior Developer presso TechCorp\n- Maria Verdi, Product Manager presso StartupXYZ\n- Giovanni Neri, CTO presso InnovateSrl\n\nVisita LinkedIn per vedere i tuoi messaggi.",
    snippet: "Hai 3 nuove richieste di connessione e 5 messaggi non letti...",
    date: new Date(Date.now() - 28800000).toISOString(),
    read: true,
    starred: false,
    labels: ["social"],
  },
  {
    id: "email-6",
    from: "Giulia Ferri",
    fromEmail: "giulia.ferri@company.it",
    to: "Roberto Bondici",
    toEmail: "roberto@example.com",
    subject: "Aggiornamento progetto Jarvis",
    body: "Ciao Roberto,\n\nVolevo aggiornarti sullo stato del progetto. Abbiamo completato il modulo di autenticazione e stiamo procedendo con l'integrazione delle API.\n\nIl deployment in staging e' previsto per venerdi. Ti mandero' il link per i test.\n\nPossiamo fare un sync domani alle 11?\n\nGrazie,\nGiulia",
    snippet: "Volevo aggiornarti sullo stato del progetto. Abbiamo completato il modulo di autenticazione...",
    date: new Date(Date.now() - 43200000).toISOString(),
    read: false,
    starred: true,
    labels: ["lavoro"],
  },
  {
    id: "email-7",
    from: "Netflix",
    fromEmail: "info@netflix.com",
    to: "Roberto Bondici",
    toEmail: "roberto@example.com",
    subject: "Nuove uscite di questa settimana",
    body: "Ciao Roberto,\n\nEcco le novita' di questa settimana su Netflix:\n\n- The White Lotus - Stagione 3\n- Squid Game - Stagione 3\n- Un nuovo documentario originale\n\nBuona visione!",
    snippet: "Ecco le novita' di questa settimana su Netflix...",
    date: new Date(Date.now() - 86400000).toISOString(),
    read: true,
    starred: false,
    labels: ["promozioni"],
  },
  {
    id: "email-8",
    from: "Paolo Russo",
    fromEmail: "paolo.russo@gmail.com",
    to: "Roberto Bondici",
    toEmail: "roberto@example.com",
    subject: "Calcetto mercoledi sera?",
    body: "Ehi Roberto,\n\nSiamo in 8 per il calcetto di mercoledi sera alle 21 al centro sportivo. Ci sei?\n\nFammi sapere!\n\nPaolo",
    snippet: "Siamo in 8 per il calcetto di mercoledi sera alle 21 al centro sportivo...",
    date: new Date(Date.now() - 172800000).toISOString(),
    read: true,
    starred: false,
    labels: ["personale"],
  },
];

export function useInbox() {
  return useQuery({
    queryKey: ["inbox"],
    queryFn: async () => {
      await new Promise((r) => setTimeout(r, 300));
      return mockEmails;
    },
    staleTime: 30_000,
  });
}

export function useSendEmail() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (_input: SendEmailInput) => {
      await new Promise((r) => setTimeout(r, 500));
      return { success: true, messageId: `msg-${Date.now()}` };
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inbox"] });
    },
  });
}
