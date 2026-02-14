import { format } from "date-fns";
import { it } from "date-fns/locale";
import { Calendar, CheckCircle2, Circle, Clock, Loader2 } from "lucide-react";
import { motion } from "framer-motion";
import GlassCard from "@/components/custom/GlassCard";
import { Badge } from "@/components/ui/badge";
import type { Task, TaskStatus, TaskPriority } from "@/hooks/use-tasks";
import { useUpdateTask } from "@/hooks/use-tasks";
import { cn } from "@/lib/utils";

const statusConfig: Record<
  TaskStatus,
  { label: string; className: string; icon: typeof Circle }
> = {
  da_fare: {
    label: "Da fare",
    className: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
    icon: Circle,
  },
  in_corso: {
    label: "In corso",
    className: "bg-blue-500/15 text-blue-400 border-blue-500/30",
    icon: Loader2,
  },
  completato: {
    label: "Completato",
    className: "bg-green-500/15 text-green-400 border-green-500/30",
    icon: CheckCircle2,
  },
};

const priorityConfig: Record<TaskPriority, { label: string; className: string }> = {
  alta: { label: "Alta", className: "bg-red-500/15 text-red-400 border-red-500/30" },
  media: {
    label: "Media",
    className: "bg-yellow-500/15 text-yellow-400 border-yellow-500/30",
  },
  bassa: {
    label: "Bassa",
    className: "bg-white/5 text-muted-foreground border-white/10",
  },
};

type TaskCardProps = {
  task: Task;
};

export default function TaskCard({ task }: TaskCardProps) {
  const { mutate: updateTask, isPending } = useUpdateTask();

  const status = statusConfig[task.status];
  const priority = priorityConfig[task.priority];
  const StatusIcon = status.icon;

  const isOverdue =
    task.due_date &&
    task.status !== "completato" &&
    new Date(task.due_date) < new Date();

  function handleToggleComplete() {
    const nextStatus: TaskStatus =
      task.status === "completato" ? "da_fare" : "completato";
    updateTask({ taskId: task.id, updates: { status: nextStatus } });
  }

  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -8 }}
      transition={{ duration: 0.2 }}
    >
      <GlassCard
        variant="interactive"
        className={cn(
          "group relative",
          task.status === "completato" && "opacity-60"
        )}
        onClick={handleToggleComplete}
      >
        <div className="flex items-start gap-3">
          <button
            type="button"
            disabled={isPending}
            className={cn(
              "mt-0.5 shrink-0 rounded-full p-0.5 transition-colors",
              task.status === "completato"
                ? "text-green-400"
                : "text-muted-foreground hover:text-primary"
            )}
            onClick={(e) => {
              e.stopPropagation();
              handleToggleComplete();
            }}
          >
            <StatusIcon
              className={cn(
                "size-5",
                task.status === "in_corso" && "animate-spin"
              )}
            />
          </button>

          <div className="min-w-0 flex-1 space-y-1.5">
            <div className="flex items-start justify-between gap-2">
              <h3
                className={cn(
                  "text-sm font-medium leading-tight",
                  task.status === "completato" && "line-through text-muted-foreground"
                )}
              >
                {task.title}
              </h3>
              <Badge className={cn("shrink-0", priority.className)}>
                {priority.label}
              </Badge>
            </div>

            <p className="text-xs text-muted-foreground line-clamp-2">
              {task.description}
            </p>

            <div className="flex items-center gap-3 pt-1">
              <Badge className={cn(status.className)}>{status.label}</Badge>

              {task.due_date && (
                <span
                  className={cn(
                    "flex items-center gap-1 text-xs",
                    isOverdue ? "text-red-400" : "text-muted-foreground"
                  )}
                >
                  {isOverdue ? (
                    <Clock className="size-3" />
                  ) : (
                    <Calendar className="size-3" />
                  )}
                  {format(new Date(task.due_date), "d MMM", { locale: it })}
                </span>
              )}
            </div>
          </div>
        </div>
      </GlassCard>
    </motion.div>
  );
}
