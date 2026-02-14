import { motion, type Variants } from "framer-motion";
import { format } from "date-fns";
import { it } from "date-fns/locale";
import QuickStatsRow from "@/components/dashboard/QuickStatsRow";
import RecentConversations from "@/components/dashboard/RecentConversations";
import SystemHealth from "@/components/dashboard/SystemHealth";
import CostChart from "@/components/charts/CostChart";
import ModelBreakdownChart from "@/components/charts/ModelBreakdownChart";

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

function getGreeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Buongiorno";
  if (hour < 18) return "Buon pomeriggio";
  return "Buonasera";
}

export default function DashboardPage() {
  const today = format(new Date(), "EEEE d MMMM yyyy", { locale: it });
  const greeting = getGreeting();

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      {/* Greeting header */}
      <motion.div variants={item}>
        <h1 className="text-2xl font-heading font-semibold">
          {greeting}, Roberto
        </h1>
        <p className="text-sm text-muted-foreground capitalize">{today}</p>
      </motion.div>

      {/* Quick stats */}
      <motion.div variants={item}>
        <QuickStatsRow />
      </motion.div>

      {/* Recent conversations */}
      <motion.div variants={item}>
        <RecentConversations />
      </motion.div>

      {/* Charts row */}
      <motion.div variants={item} className="grid gap-6 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <CostChart />
        </div>
        <div className="lg:col-span-2">
          <ModelBreakdownChart />
        </div>
      </motion.div>

      {/* System health */}
      <motion.div variants={item}>
        <SystemHealth />
      </motion.div>
    </motion.div>
  );
}
