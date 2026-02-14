import { useChat } from "@/hooks/use-chat";
import RainBackground from "@/components/chat/RainBackground";
import MessageList from "@/components/chat/MessageList";
import ChatInput from "@/components/chat/ChatInput";
import SuggestionChips from "@/components/chat/SuggestionChips";

export default function ChatPage() {
  const { messages, sendMessage, isStreaming, streamingText } = useChat();

  const isEmpty = messages.length === 0;

  return (
    <div className="relative flex h-full flex-col animate-fade-in">
      <RainBackground visible={isEmpty} />

      {isEmpty ? (
        <div className="flex flex-1 flex-col items-center justify-center gap-8 px-4">
          <h1 className="font-heading text-3xl text-foreground">
            Ciao, come posso aiutarti?
          </h1>
          <SuggestionChips onSelect={sendMessage} />
        </div>
      ) : (
        <MessageList
          messages={messages}
          isStreaming={isStreaming}
          streamingText={streamingText}
        />
      )}

      <ChatInput onSend={sendMessage} isStreaming={isStreaming} />
    </div>
  );
}
