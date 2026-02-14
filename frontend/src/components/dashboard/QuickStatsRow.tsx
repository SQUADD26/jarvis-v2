import { Coins, CheckSquare, Mail, Calendar } from "lucide-react";
import StatCard from "@/components/dashboard/StatCard";
import { useLlmStats } from "@/hooks/use-llm-stats";
import { useTaskQueue } from "@/hooks/use-task-queue";

export default function QuickStatsRow() {
  const { totalCostToday } = useLlmStats();
  const { pendingCount } = useTaskQueue();

  // TODO: fetch from real data
  const unreadEmails = 12;
  const todayEvents = 3;

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      <StatCard
        icon={Coins}
        label="Costo LLM oggi"
        value={`€${totalCostToday.toFixed(2)}`}
        trend={{ value: -8, label: "vs ieri" }}
        iconClassName="bg-primary/10 text-primary"
      />
      <StatCard
        icon={CheckSquare}
        label="Task pendenti"
        value={pendingCount}
        iconClassName="bg-yellow-500/10 text-yellow-400"
      />
      <StatCard
        icon={Mail}
        label="Email non lette"
        value={unreadEmails}
        trend={{ value: 4, label: "ultime 24h" }}
        iconClassName="bg-blue-500/10 text-blue-400"
      />
      <StatCard
        icon={Calendar}
        label="Eventi oggi"
        value={todayEvents}
        iconClassName="bg-purple-500/10 text-purple-400"
      />
    </div>
  );
}
