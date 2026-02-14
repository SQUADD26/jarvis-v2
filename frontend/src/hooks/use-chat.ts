import { useState, useCallback } from "react";
import type { ChatMessage } from "@/components/chat/MessageBubble";

const API_URL = import.meta.env.VITE_API_URL || "";

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamingText, setStreamingText] = useState("");
  const [conversationId, setConversationId] = useState<string | undefined>();

  const sendMessage = useCallback(
    async (text: string) => {
      const userMessage: ChatMessage = {
        role: "user",
        content: text,
        timestamp: new Date().toLocaleTimeString("it-IT", {
          hour: "2-digit",
          minute: "2-digit",
        }),
      };

      setMessages((prev) => [...prev, userMessage]);
      setIsStreaming(true);
      setStreamingText("");

      try {
        const res = await fetch(`${API_URL}/api/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: text,
            conversation_id: conversationId,
          }),
        });

        if (!res.ok) {
          throw new Error(`API ${res.status}`);
        }

        const reader = res.body?.getReader();
        if (!reader) throw new Error("No response stream");

        const decoder = new TextDecoder();
        let fullText = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          const chunk = decoder.decode(value, { stream: true });
          fullText += chunk;
          setStreamingText(fullText);
        }

        // Extract conversation ID from response headers if available
        const newConvId = res.headers.get("x-conversation-id");
        if (newConvId) {
          setConversationId(newConvId);
        }

        const assistantMessage: ChatMessage = {
          role: "assistant",
          content: fullText,
          timestamp: new Date().toLocaleTimeString("it-IT", {
            hour: "2-digit",
            minute: "2-digit",
          }),
        };

        setMessages((prev) => [...prev, assistantMessage]);
      } catch (error) {
        const errorMessage: ChatMessage = {
          role: "assistant",
          content:
            "Mi dispiace, si è verificato un errore. Riprova tra qualche istante.",
          timestamp: new Date().toLocaleTimeString("it-IT", {
            hour: "2-digit",
            minute: "2-digit",
          }),
        };
        setMessages((prev) => [...prev, errorMessage]);
        console.error("Chat stream error:", error);
      } finally {
        setIsStreaming(false);
        setStreamingText("");
      }
    },
    [conversationId]
  );

  const clearHistory = useCallback(() => {
    setMessages([]);
    setConversationId(undefined);
    setStreamingText("");
  }, []);

  return { messages, sendMessage, clearHistory, isStreaming, streamingText };
}
