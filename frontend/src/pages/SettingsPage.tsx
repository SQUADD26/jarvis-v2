import { motion, type Variants } from "framer-motion";
import { Settings, User, Link2, Brain } from "lucide-react";
import PageHeader from "@/components/custom/PageHeader";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import ProfileForm from "@/components/settings/ProfileForm";
import IntegrationStatus from "@/components/settings/IntegrationStatus";
import MemoryManager from "@/components/settings/MemoryManager";

const container: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.05 },
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

export default function SettingsPage() {
  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      <motion.div variants={item}>
        <PageHeader
          title="Impostazioni"
          description="Gestisci il tuo profilo, le integrazioni e la memoria AI"
          icon={Settings}
        />
      </motion.div>

      <motion.div variants={item}>
        <Tabs defaultValue="profilo">
          <TabsList variant="line" className="mb-6">
            <TabsTrigger value="profilo">
              <User className="size-4" />
              Profilo
            </TabsTrigger>
            <TabsTrigger value="integrazioni">
              <Link2 className="size-4" />
              Integrazioni
            </TabsTrigger>
            <TabsTrigger value="memoria">
              <Brain className="size-4" />
              Memoria
            </TabsTrigger>
          </TabsList>

          <TabsContent value="profilo">
            <ProfileForm />
          </TabsContent>

          <TabsContent value="integrazioni">
            <IntegrationStatus />
          </TabsContent>

          <TabsContent value="memoria">
            <MemoryManager />
          </TabsContent>
        </Tabs>
      </motion.div>
    </motion.div>
  );
}
