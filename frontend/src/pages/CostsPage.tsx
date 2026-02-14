import { motion, type Variants } from "framer-motion";
import { Coins } from "lucide-react";
import PageHeader from "@/components/custom/PageHeader";
import CostOverview from "@/components/costs/CostOverview";
import CostTrendChart from "@/components/costs/CostTrendChart";
import DailyStatsTable from "@/components/costs/DailyStatsTable";

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

export default function CostsPage() {
  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      <motion.div variants={item}>
        <PageHeader
          title="Costi LLM"
          description="Monitora le spese e l'utilizzo dei modelli AI"
          icon={Coins}
        />
      </motion.div>

      <motion.div variants={item}>
        <CostOverview />
      </motion.div>

      <motion.div variants={item}>
        <CostTrendChart />
      </motion.div>

      <motion.div variants={item}>
        <DailyStatsTable />
      </motion.div>
    </motion.div>
  );
}
