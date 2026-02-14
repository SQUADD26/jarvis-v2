import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/hooks/use-auth";

export type UserProfileData = {
  full_name: string;
  email: string;
  timezone: string;
  language: string;
};

const mockProfile: UserProfileData = {
  full_name: "Roberto Bondici",
  email: "roberto@example.com",
  timezone: "Europe/Rome",
  language: "it",
};

export function useProfile() {
  const { user } = useAuth();

  const { data, isLoading, error } = useQuery({
    queryKey: ["user-profile", user?.id],
    queryFn: async () => {
      // TODO: fetch from Supabase user_preferences + profile
      await new Promise((r) => setTimeout(r, 200));
      return {
        ...mockProfile,
        email: user?.email ?? mockProfile.email,
      };
    },
    staleTime: 10 * 60 * 1000,
    enabled: !!user,
  });

  return {
    profile: data ?? null,
    isLoading,
    error: error as Error | null,
  };
}

export function useUpdateProfile() {
  const queryClient = useQueryClient();
  const { user } = useAuth();

  return useMutation({
    mutationFn: async (data: Partial<UserProfileData>) => {
      // TODO: update Supabase user_preferences
      await new Promise((r) => setTimeout(r, 800));
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["user-profile", user?.id] });
    },
  });
}
