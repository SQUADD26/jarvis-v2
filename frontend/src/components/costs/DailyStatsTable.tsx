import { useState, useMemo } from "react";
import { format } from "date-fns";
import { it } from "date-fns/locale";
import { ArrowUpDown } from "lucide-react";
import GlassPanel from "@/components/custom/GlassPanel";
import SectionHeader from "@/components/custom/SectionHeader";
import { Button } from "@/components/ui/button";
import { useDailyStats, type DailyStatRow } from "@/hooks/use-costs";

type SortField = "date" | "model" | "call_count" | "input_tokens" | "output_tokens" | "total_cost";
type SortDir = "asc" | "desc";

const columns: { key: SortField; label: string; align?: "right" }[] = [
  { key: "date", label: "Data" },
  { key: "model", label: "Modello" },
  { key: "call_count", label: "Chiamate", align: "right" },
  { key: "input_tokens", label: "Token Input", align: "right" },
  { key: "output_tokens", label: "Token Output", align: "right" },
  { key: "total_cost", label: "Costo", align: "right" },
];

function formatTokens(n: number): string {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
  return n.toLocaleString("it-IT");
}

export default function DailyStatsTable() {
  const { dailyStats } = useDailyStats(30);
  const [sortField, setSortField] = useState<SortField>("date");
  const [sortDir, setSortDir] = useState<SortDir>("desc");

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((prev) => (prev === "asc" ? "desc" : "asc"));
    } else {
      setSortField(field);
      setSortDir("desc");
    }
  };

  const sortedStats = useMemo(() => {
    const copy = [...dailyStats];
    copy.sort((a, b) => {
      const aVal = a[sortField];
      const bVal = b[sortField];
      if (typeof aVal === "string" && typeof bVal === "string") {
        return sortDir === "asc" ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
      }
      const aNum = aVal as number;
      const bNum = bVal as number;
      return sortDir === "asc" ? aNum - bNum : bNum - aNum;
    });
    return copy;
  }, [dailyStats, sortField, sortDir]);

  return (
    <GlassPanel>
      <SectionHeader title="Dettaglio giornaliero" className="mb-4" />
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-white/10">
              {columns.map((col) => (
                <th
                  key={col.key}
                  className={`pb-3 font-medium text-muted-foreground ${col.align === "right" ? "text-right" : "text-left"}`}
                >
                  <Button
                    variant="ghost"
                    size="sm"
                    className={`-ml-2 h-auto gap-1 px-2 py-1 text-xs font-medium text-muted-foreground hover:text-foreground ${col.align === "right" ? "ml-auto" : ""}`}
                    onClick={() => handleSort(col.key)}
                  >
                    {col.label}
                    <ArrowUpDown className="size-3" />
                  </Button>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {sortedStats.map((row: DailyStatRow, idx: number) => (
              <tr
                key={`${row.date}-${row.model}-${idx}`}
                className="border-b border-white/5 transition-colors hover:bg-white/[0.02]"
              >
                <td className="py-3 text-foreground">
                  {format(new Date(row.date), "d MMM yyyy", { locale: it })}
                </td>
                <td className="py-3">
                  <span className="rounded-md bg-white/5 px-2 py-0.5 text-xs font-medium text-muted-foreground">
                    {row.model.replace("gemini-", "")}
                  </span>
                </td>
                <td className="py-3 text-right tabular-nums text-foreground">
                  {row.call_count}
                </td>
                <td className="py-3 text-right tabular-nums text-muted-foreground">
                  {formatTokens(row.input_tokens)}
                </td>
                <td className="py-3 text-right tabular-nums text-muted-foreground">
                  {formatTokens(row.output_tokens)}
                </td>
                <td className="py-3 text-right tabular-nums font-medium text-primary">
                  €{row.total_cost.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </GlassPanel>
  );
}
