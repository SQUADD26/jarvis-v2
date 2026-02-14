import { useState } from "react";
import { motion, type Variants } from "framer-motion";
import { Mail, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import InboxList from "@/components/email/InboxList";
import EmailDetail from "@/components/email/EmailDetail";
import ComposeDialog from "@/components/email/ComposeDialog";
import { useInbox, type Email } from "@/hooks/use-emails";
import { useIsMobile } from "@/hooks/use-mobile";

const fadeIn: Variants = {
  hidden: { opacity: 0 },
  show: { opacity: 1, transition: { duration: 0.35, ease: "easeOut" } },
};

export default function EmailPage() {
  const [selectedEmail, setSelectedEmail] = useState<Email | null>(null);
  const [composeOpen, setComposeOpen] = useState(false);
  const [mobileDetailOpen, setMobileDetailOpen] = useState(false);
  const isMobile = useIsMobile();

  const { data: emails = [], isLoading } = useInbox();

  const unreadCount = emails.filter((e) => !e.read).length;

  const handleSelectEmail = (email: Email) => {
    setSelectedEmail(email);
    if (isMobile) {
      setMobileDetailOpen(true);
    }
  };

  const handleBack = () => {
    setMobileDetailOpen(false);
    setTimeout(() => setSelectedEmail(null), 300);
  };

  return (
    <motion.div
      variants={fadeIn}
      initial="hidden"
      animate="show"
      className="h-full flex flex-col"
    >
      <div className="flex items-center justify-between px-1 pb-4">
        <div className="flex items-center gap-3">
          <div className="size-10 rounded-lg bg-primary/10 text-primary flex items-center justify-center">
            <Mail className="size-5" />
          </div>
          <div>
            <h1 className="text-xl font-heading font-semibold">Email</h1>
            <p className="text-xs text-muted-foreground">
              {unreadCount > 0
                ? `${unreadCount} non lett${unreadCount === 1 ? "a" : "e"}`
                : "Tutte lette"}
            </p>
          </div>
        </div>
        <Button
          size="sm"
          className="gap-1.5"
          onClick={() => setComposeOpen(true)}
        >
          <Plus className="size-4" />
          Scrivi
        </Button>
      </div>

      <div className="flex-1 min-h-0 glass rounded-2xl overflow-hidden">
        <div className="flex h-full">
          <div
            className={
              isMobile
                ? "w-full"
                : "w-[380px] xl:w-[420px] shrink-0 border-r border-white/5"
            }
          >
            <InboxList
              emails={emails}
              selectedId={selectedEmail?.id ?? null}
              onSelect={handleSelectEmail}
              isLoading={isLoading}
            />
          </div>

          {!isMobile && (
            <div className="flex-1 min-w-0">
              <EmailDetail email={selectedEmail} />
            </div>
          )}
        </div>
      </div>

      {isMobile && (
        <Sheet open={mobileDetailOpen} onOpenChange={setMobileDetailOpen}>
          <SheetContent side="right" className="w-full sm:max-w-full p-0">
            <SheetHeader className="sr-only">
              <SheetTitle>Dettaglio email</SheetTitle>
            </SheetHeader>
            <EmailDetail
              email={selectedEmail}
              onBack={handleBack}
              showBack
            />
          </SheetContent>
        </Sheet>
      )}

      <ComposeDialog open={composeOpen} onOpenChange={setComposeOpen} />
    </motion.div>
  );
}
