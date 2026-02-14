import { motion } from "framer-motion";
import { Calendar, Mail, CheckSquare, Globe } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface Suggestion {
  label: string;
  icon: LucideIcon;
}

const suggestions: Suggestion[] = [
  { label: "Agenda di oggi", icon: Calendar },
  { label: "Email non lette", icon: Mail },
  { label: "Le mie task", icon: CheckSquare },
  { label: "Cerca sul web", icon: Globe },
];

interface SuggestionChipsProps {
  onSelect: (suggestion: string) => void;
}

export default function SuggestionChips({ onSelect }: SuggestionChipsProps) {
  return (
    <div className="flex flex-wrap gap-2 justify-center">
      {suggestions.map((suggestion, i) => {
        const Icon = suggestion.icon;
        return (
          <motion.button
            key={suggestion.label}
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{
              duration: 0.35,
              delay: 0.2 + i * 0.06,
              ease: [0.22, 1, 0.36, 1],
            }}
            onClick={() => onSelect(suggestion.label)}
            className="glass rounded-full px-4 py-2 flex items-center gap-2 text-sm text-muted-foreground cursor-pointer transition-all duration-200 hover:glass-selected hover:text-foreground"
          >
            <Icon className="h-4 w-4" />
            <span>{suggestion.label}</span>
          </motion.button>
        );
      })}
    </div>
  );
}
