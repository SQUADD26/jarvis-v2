import { motion } from "framer-motion";
import { cn } from "@/lib/utils";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  timestamp?: string;
}

interface MessageBubbleProps {
  message: ChatMessage;
  index: number;
}

export default function MessageBubble({ message, index }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.35,
        delay: index * 0.05,
        ease: [0.22, 1, 0.36, 1],
      }}
      className={cn("flex w-full", isUser ? "justify-end" : "justify-start")}
    >
      <div className="flex max-w-[80%] flex-col gap-1">
        <div
          className={cn(
            "px-4 py-2.5 text-sm leading-relaxed",
            isUser
              ? "rounded-2xl rounded-br-md bg-primary text-primary-foreground"
              : "glass-elevated rounded-2xl rounded-bl-md text-foreground"
          )}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div
              className="prose prose-invert prose-sm max-w-none [&_p]:my-1 [&_ul]:my-1 [&_ol]:my-1"
              dangerouslySetInnerHTML={{ __html: message.content }}
            />
          )}
        </div>
        {message.timestamp && (
          <span
            className={cn(
              "text-xs text-muted-foreground px-1",
              isUser ? "text-right" : "text-left"
            )}
          >
            {message.timestamp}
          </span>
        )}
      </div>
    </motion.div>
  );
}
