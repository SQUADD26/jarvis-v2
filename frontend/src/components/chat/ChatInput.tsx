import { useRef, useCallback, type KeyboardEvent, type ChangeEvent } from "react";
import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { ArrowUp, Mic } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatInputProps {
  onSend: (message: string) => void;
  isStreaming: boolean;
}

export default function ChatInput({ onSend, isStreaming }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    const maxHeight = 5 * 24; // 5 rows approx
    el.style.height = `${Math.min(el.scrollHeight, maxHeight)}px`;
  }, []);

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>) => {
    setValue(e.target.value);
    adjustHeight();
  };

  const handleSend = useCallback(() => {
    const trimmed = value.trim();
    if (!trimmed || isStreaming) return;
    onSend(trimmed);
    setValue("");
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto";
    }
  }, [value, isStreaming, onSend]);

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const hasText = value.trim().length > 0;

  return (
    <div className="shrink-0 px-4 pb-4 pt-2">
      <div className="glass-elevated mx-auto flex max-w-2xl items-end gap-2 rounded-2xl px-3 py-2">
        <button
          type="button"
          className="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground"
          aria-label="Registra vocale"
        >
          <Mic className="h-5 w-5" />
        </button>

        <textarea
          ref={textareaRef}
          value={value}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          disabled={isStreaming}
          placeholder="Scrivi un messaggio..."
          rows={1}
          className={cn(
            "flex-1 resize-none bg-transparent py-2 text-sm leading-6 text-foreground",
            "placeholder:text-muted-foreground",
            "outline-none disabled:cursor-not-allowed disabled:opacity-50"
          )}
        />

        <AnimatePresence>
          {hasText && (
            <motion.button
              initial={{ scale: 0, opacity: 0 }}
              animate={{ scale: 1, opacity: 1 }}
              exit={{ scale: 0, opacity: 0 }}
              transition={{ duration: 0.15, ease: [0.22, 1, 0.36, 1] }}
              type="button"
              onClick={handleSend}
              disabled={isStreaming}
              className="mb-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
              aria-label="Invia messaggio"
            >
              <ArrowUp className="h-5 w-5" />
            </motion.button>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
}
