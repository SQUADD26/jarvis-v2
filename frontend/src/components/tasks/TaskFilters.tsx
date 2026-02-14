import { Badge } from "@/components/ui/badge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { Task, TaskStatus } from "@/hooks/use-tasks";
import { cn } from "@/lib/utils";

type FilterValue = "tutti" | TaskStatus;

type TaskFiltersProps = {
  value: FilterValue;
  onChange: (value: FilterValue) => void;
  tasks: Task[];
};

const filters: { value: FilterValue; label: string }[] = [
  { value: "tutti", label: "Tutti" },
  { value: "da_fare", label: "Da fare" },
  { value: "in_corso", label: "In corso" },
  { value: "completato", label: "Completati" },
];

export default function TaskFilters({ value, onChange, tasks }: TaskFiltersProps) {
  function getCount(filter: FilterValue): number {
    if (filter === "tutti") return tasks.length;
    return tasks.filter((t) => t.status === filter).length;
  }

  return (
    <Tabs value={value} onValueChange={(v) => onChange(v as FilterValue)}>
      <TabsList className="bg-white/5">
        {filters.map((f) => {
          const count = getCount(f.value);
          return (
            <TabsTrigger key={f.value} value={f.value} className="gap-1.5">
              {f.label}
              <Badge
                className={cn(
                  "h-5 min-w-5 px-1.5 text-[10px]",
                  value === f.value
                    ? "bg-primary/20 text-primary"
                    : "bg-white/5 text-muted-foreground"
                )}
              >
                {count}
              </Badge>
            </TabsTrigger>
          );
        })}
      </TabsList>
    </Tabs>
  );
}

export type { FilterValue };
