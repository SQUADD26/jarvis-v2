import { useState } from "react";
import type { LucideIcon } from "lucide-react";
import { Mail, Calendar, BookOpen, Video, ExternalLink } from "lucide-react";
import GlassCard from "@/components/custom/GlassCard";
import GlassIconBox from "@/components/custom/GlassIconBox";
import SectionHeader from "@/components/custom/SectionHeader";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

type Integration = {
  id: string;
  name: string;
  description: string;
  icon: LucideIcon;
  iconClassName: string;
  connected: boolean;
};

const initialIntegrations: Integration[] = [
  {
    id: "gmail",
    name: "Gmail",
    description: "Leggi e gestisci le tue email direttamente da Jarvis",
    icon: Mail,
    iconClassName: "bg-red-500/10 text-red-400",
    connected: false,
  },
  {
    id: "google-calendar",
    name: "Google Calendar",
    description: "Visualizza eventi, crea appuntamenti e gestisci il calendario",
    icon: Calendar,
    iconClassName: "bg-blue-500/10 text-blue-400",
    connected: false,
  },
  {
    id: "notion",
    name: "Notion",
    description: "Sincronizza note, database e pagine con il tuo workspace",
    icon: BookOpen,
    iconClassName: "bg-white/10 text-white",
    connected: false,
  },
  {
    id: "fathom",
    name: "Fathom",
    description: "Trascrivi e riassumi automaticamente le tue riunioni",
    icon: Video,
    iconClassName: "bg-purple-500/10 text-purple-400",
    connected: false,
  },
];

export default function IntegrationStatus() {
  const [integrations] = useState<Integration[]>(initialIntegrations);

  const handleConnect = (id: string) => {
    // TODO: implement OAuth flow for each integration
    console.log("Connect:", id);
  };

  const handleDisconnect = (id: string) => {
    // TODO: implement disconnect logic
    console.log("Disconnect:", id);
  };

  return (
    <div className="space-y-4">
      <SectionHeader title="Servizi collegati" />
      <div className="grid gap-4 sm:grid-cols-2">
        {integrations.map((integration) => (
          <GlassCard key={integration.id} className="flex flex-col gap-4">
            <div className="flex items-start gap-3">
              <GlassIconBox
                icon={integration.icon}
                size="lg"
                className={integration.iconClassName}
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <h3 className="font-medium text-foreground">
                    {integration.name}
                  </h3>
                  {integration.connected ? (
                    <Badge className="bg-green-500/10 text-green-400 border-green-500/20">
                      Connesso
                    </Badge>
                  ) : (
                    <Badge variant="secondary" className="bg-white/5 text-muted-foreground">
                      Non connesso
                    </Badge>
                  )}
                </div>
                <p className="mt-1 text-sm text-muted-foreground leading-relaxed">
                  {integration.description}
                </p>
              </div>
            </div>
            <div className="flex justify-end">
              {integration.connected ? (
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => handleDisconnect(integration.id)}
                >
                  Disconnetti
                </Button>
              ) : (
                <Button
                  size="sm"
                  onClick={() => handleConnect(integration.id)}
                >
                  <ExternalLink className="size-3.5" />
                  Connetti
                </Button>
              )}
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  );
}
