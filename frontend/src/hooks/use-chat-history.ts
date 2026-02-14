import { useQuery } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase";

interface ChatHistoryEntry {
  id: string;
  user_message: string;
  assistant_message: string;
  conversation_id: string;
  created_at: string;
}

async function fetchChatHistory(): Promise<ChatHistoryEntry[]> {
  const { data, error } = await supabase
    .from("chat_history")
    .select("id, user_message, assistant_message, conversation_id, created_at")
    .order("created_at", { ascending: false })
    .limit(50);

  if (error) throw error;
  return (data ?? []) as ChatHistoryEntry[];
}

export function useChatHistory() {
  return useQuery({
    queryKey: ["chat-history"],
    queryFn: fetchChatHistory,
    staleTime: 5 * 60 * 1000,
  });
}

export type { ChatHistoryEntry };
