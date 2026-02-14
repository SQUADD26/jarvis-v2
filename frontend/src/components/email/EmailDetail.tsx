import { format } from "date-fns";
import { it } from "date-fns/locale";
import { motion } from "framer-motion";
import {
  ArrowLeft,
  Reply,
  Forward,
  Star,
  MoreHorizontal,
  Mail,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { ScrollArea } from "@/components/ui/scroll-area";
import type { Email } from "@/hooks/use-emails";

type EmailDetailProps = {
  email: Email | null;
  onBack?: () => void;
  showBack?: boolean;
};

export default function EmailDetail({
  email,
  onBack,
  showBack = false,
}: EmailDetailProps) {
  if (!email) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
        <Mail className="size-16 mb-4 opacity-20" />
        <p className="text-sm">Seleziona un'email per leggerla</p>
      </div>
    );
  }

  return (
    <motion.div
      key={email.id}
      initial={{ opacity: 0, x: 16 }}
      animate={{ opacity: 1, x: 0 }}
      transition={{ duration: 0.25, ease: "easeOut" }}
      className="flex flex-col h-full"
    >
      <div className="p-4 pb-3 flex items-center gap-2">
        {showBack && (
          <Button variant="ghost" size="icon-sm" onClick={onBack}>
            <ArrowLeft className="size-4" />
          </Button>
        )}
        <div className="flex-1" />
        <Button variant="ghost" size="icon-sm">
          <Star
            className={
              email.starred
                ? "size-4 fill-amber-400 text-amber-400"
                : "size-4"
            }
          />
        </Button>
        <Button variant="ghost" size="icon-sm">
          <MoreHorizontal className="size-4" />
        </Button>
      </div>

      <ScrollArea className="flex-1 px-4">
        <div className="space-y-4 pb-6">
          <div>
            <h2 className="text-xl font-semibold leading-tight">
              {email.subject}
            </h2>
            <div className="flex flex-wrap gap-1.5 mt-2">
              {email.labels.map((label) => (
                <Badge key={label} variant="secondary" className="text-[10px]">
                  {label}
                </Badge>
              ))}
            </div>
          </div>

          <Separator className="bg-white/5" />

          <div className="flex items-start gap-3">
            <div className="size-10 rounded-full bg-primary/20 text-primary flex items-center justify-center text-sm font-medium shrink-0">
              {email.from
                .split(" ")
                .map((w) => w[0])
                .join("")
                .toUpperCase()
                .slice(0, 2)}
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between gap-2">
                <div>
                  <p className="text-sm font-medium">{email.from}</p>
                  <p className="text-xs text-muted-foreground">
                    {email.fromEmail}
                  </p>
                </div>
                <p className="text-xs text-muted-foreground shrink-0">
                  {format(new Date(email.date), "d MMM yyyy, HH:mm", {
                    locale: it,
                  })}
                </p>
              </div>
              <p className="text-xs text-muted-foreground mt-1">
                A: {email.to} &lt;{email.toEmail}&gt;
              </p>
            </div>
          </div>

          <Separator className="bg-white/5" />

          <div className="text-sm leading-relaxed whitespace-pre-wrap text-foreground/90">
            {email.body}
          </div>
        </div>
      </ScrollArea>

      <Separator className="bg-white/5" />

      <div className="p-4 flex items-center gap-2">
        <Button variant="outline" size="sm" className="gap-1.5">
          <Reply className="size-3.5" />
          Rispondi
        </Button>
        <Button variant="outline" size="sm" className="gap-1.5">
          <Forward className="size-3.5" />
          Inoltra
        </Button>
      </div>
    </motion.div>
  );
}
