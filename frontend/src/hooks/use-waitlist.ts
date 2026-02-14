import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { supabase } from "@/lib/supabase";

interface WaitlistEntry {
  id: string;
  user_id: string;
  email: string;
  full_name: string | null;
  reason: string | null;
  status: string;
  created_at: string;
}

export function useWaitlist() {
  return useQuery<WaitlistEntry[]>({
    queryKey: ["waitlist", "pending"],
    queryFn: async () => {
      const { data, error } = await supabase
        .from("waitlist")
        .select("*")
        .eq("status", "pending")
        .order("created_at", { ascending: true });

      if (error) throw error;
      return data as WaitlistEntry[];
    },
  });
}

export function useApproveUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (entry: WaitlistEntry) => {
      const { error: waitlistError } = await supabase
        .from("waitlist")
        .update({ status: "approved" })
        .eq("id", entry.id);

      if (waitlistError) throw waitlistError;

      const { error: profileError } = await supabase
        .from("user_profiles")
        .update({ status: "approved" })
        .eq("id", entry.user_id);

      if (profileError) throw profileError;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["waitlist"] });
    },
  });
}

export function useRejectUser() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async (entry: WaitlistEntry) => {
      const { error } = await supabase
        .from("waitlist")
        .update({ status: "rejected" })
        .eq("id", entry.id);

      if (error) throw error;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["waitlist"] });
    },
  });
}
