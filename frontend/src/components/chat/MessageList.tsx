import { useRef, useEffect } from "react";
import { AnimatePresence } from "framer-motion";
import { ScrollArea } from "@/components/ui/scroll-area";
import MessageBubble from "@/components/chat/MessageBubble";
import TypingIndicator from "@/components/chat/TypingIndicator";
import type { ChatMessage } from "@/components/chat/MessageBubble";

interface MessageListProps {
  messages: ChatMessage[];
  isStreaming: boolean;
  streamingText: string;
}

export default function MessageList({
  messages,
  isStreaming,
  streamingText,
}: MessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingText]);

  return (
    <ScrollArea className="flex-1 overflow-y-auto">
      <div className="mx-auto flex w-full max-w-2xl flex-col gap-4 px-4 py-6">
        {messages.map((msg, i) => (
          <MessageBubble key={i} message={msg} index={i} />
        ))}

        {isStreaming && streamingText && (
          <MessageBubble
            message={{ role: "assistant", content: streamingText }}
            index={messages.length}
          />
        )}

        <AnimatePresence>
          {isStreaming && !streamingText && <TypingIndicator />}
        </AnimatePresence>

        <div ref={bottomRef} />
      </div>
    </ScrollArea>
  );
}
