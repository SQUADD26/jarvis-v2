import { useState } from "react";
import { motion, type Variants } from "framer-motion";
import { Brain, Plus } from "lucide-react";
import PageHeader from "@/components/custom/PageHeader";
import SectionHeader from "@/components/custom/SectionHeader";
import { Button } from "@/components/ui/button";
import KnowledgeStats from "@/components/knowledge/KnowledgeStats";
import SourceList from "@/components/knowledge/SourceList";
import ImportDialog from "@/components/knowledge/ImportDialog";
import SkeletonCard from "@/components/feedback/SkeletonCard";
import { useRagSources, useRagStats } from "@/hooks/use-rag-sources";

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

export default function KnowledgePage() {
  const [importOpen, setImportOpen] = useState(false);
  const { data: sources, isLoading: sourcesLoading } = useRagSources();
  const { data: stats, isLoading: statsLoading } = useRagStats();

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      <motion.div variants={item}>
        <PageHeader
          title="Knowledge Base"
          description="Gestisci i documenti e le fonti di conoscenza di Jarvis"
          icon={Brain}
          actions={
            <Button size="sm" onClick={() => setImportOpen(true)}>
              <Plus className="size-4" />
              Importa
            </Button>
          }
        />
      </motion.div>

      <motion.div variants={item}>
        <KnowledgeStats stats={stats} isLoading={statsLoading} />
      </motion.div>

      <motion.div variants={item}>
        <SectionHeader title="Fonti" />
      </motion.div>

      {sourcesLoading ? (
        <motion.div variants={item} className="space-y-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} lines={2} />
          ))}
        </motion.div>
      ) : (
        <motion.div variants={item}>
          <SourceList sources={sources ?? []} />
        </motion.div>
      )}

      <ImportDialog open={importOpen} onOpenChange={setImportOpen} />
    </motion.div>
  );
}
