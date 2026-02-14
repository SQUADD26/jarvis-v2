import { useState, useMemo } from "react";
import { motion, AnimatePresence, type Variants } from "framer-motion";
import { CheckSquare, ListTodo } from "lucide-react";
import PageHeader from "@/components/custom/PageHeader";
import SectionHeader from "@/components/custom/SectionHeader";
import TaskCard from "@/components/tasks/TaskCard";
import TaskFilters, { type FilterValue } from "@/components/tasks/TaskFilters";
import EmptyState from "@/components/feedback/EmptyState";
import SkeletonCard from "@/components/feedback/SkeletonCard";
import { useTasks } from "@/hooks/use-tasks";

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

export default function TasksPage() {
  const [filter, setFilter] = useState<FilterValue>("tutti");
  const { data: allTasks, isLoading } = useTasks("tutti");
  const tasks = allTasks ?? [];

  const filteredTasks = useMemo(() => {
    if (filter === "tutti") return tasks;
    return tasks.filter((t) => t.status === filter);
  }, [tasks, filter]);

  const grouped = useMemo(() => {
    const groups: Record<string, typeof filteredTasks> = {};
    for (const task of filteredTasks) {
      if (!groups[task.project]) {
        groups[task.project] = [];
      }
      groups[task.project].push(task);
    }
    return Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  }, [filteredTasks]);

  return (
    <motion.div
      variants={container}
      initial="hidden"
      animate="show"
      className="space-y-6"
    >
      <motion.div variants={item}>
        <PageHeader
          title="I miei Task"
          description={`${tasks.length} task totali`}
          icon={CheckSquare}
        />
      </motion.div>

      <motion.div variants={item}>
        <TaskFilters value={filter} onChange={setFilter} tasks={tasks} />
      </motion.div>

      {isLoading && (
        <motion.div variants={item} className="space-y-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} lines={2} />
          ))}
        </motion.div>
      )}

      {!isLoading && filteredTasks.length === 0 && (
        <motion.div variants={item}>
          <EmptyState
            icon={ListTodo}
            title="Nessun task trovato"
            description={
              filter === "tutti"
                ? "Non hai ancora nessun task. Verranno creati automaticamente da Jarvis."
                : `Nessun task con stato "${filter.replace("_", " ")}".`
            }
          />
        </motion.div>
      )}

      <AnimatePresence mode="popLayout">
        {grouped.map(([project, projectTasks]) => (
          <motion.div
            key={project}
            variants={item}
            layout
            className="space-y-3"
          >
            <SectionHeader
              title={project}
              action={
                <span className="text-xs text-muted-foreground">
                  {projectTasks.length} task
                </span>
              }
            />
            <div className="space-y-2">
              <AnimatePresence mode="popLayout">
                {projectTasks.map((task) => (
                  <TaskCard key={task.id} task={task} />
                ))}
              </AnimatePresence>
            </div>
          </motion.div>
        ))}
      </AnimatePresence>
    </motion.div>
  );
}
