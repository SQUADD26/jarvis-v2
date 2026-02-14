import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from "react";
import { createElement } from "react";
import type { User, Session } from "@supabase/supabase-js";
import { supabase } from "@/lib/supabase";

interface UserProfile {
  id: string;
  full_name: string | null;
  email: string;
  status: string;
  avatar_url: string | null;
  created_at: string;
}

interface OrgMembership {
  id: string;
  org_id: string;
  role: string;
  org_name: string | null;
}

interface AuthState {
  user: User | null;
  session: Session | null;
  loading: boolean;
  profile: UserProfile | null;
  currentOrg: OrgMembership | null;
}

const AuthContext = createContext<AuthState>({
  user: null,
  session: null,
  loading: true,
  profile: null,
  currentOrg: null,
});

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [session, setSession] = useState<Session | null>(null);
  const [loading, setLoading] = useState(true);
  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [currentOrg, setCurrentOrg] = useState<OrgMembership | null>(null);

  const fetchProfile = useCallback(async (userId: string) => {
    const { data } = await supabase
      .from("user_profiles")
      .select("*")
      .eq("id", userId)
      .single();

    if (data) {
      setProfile(data as UserProfile);
    }
  }, []);

  const fetchCurrentOrg = useCallback(async (userId: string) => {
    const { data } = await supabase
      .from("org_memberships")
      .select("*")
      .eq("user_id", userId)
      .limit(1)
      .single();

    if (data) {
      setCurrentOrg(data as OrgMembership);
    }
  }, []);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session: currentSession } }) => {
      setSession(currentSession);
      setUser(currentSession?.user ?? null);

      if (currentSession?.user) {
        fetchProfile(currentSession.user.id);
        fetchCurrentOrg(currentSession.user.id);
      }

      setLoading(false);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, newSession) => {
      setSession(newSession);
      setUser(newSession?.user ?? null);

      if (newSession?.user) {
        fetchProfile(newSession.user.id);
        fetchCurrentOrg(newSession.user.id);
      } else {
        setProfile(null);
        setCurrentOrg(null);
      }

      setLoading(false);
    });

    return () => {
      subscription.unsubscribe();
    };
  }, [fetchProfile, fetchCurrentOrg]);

  return createElement(
    AuthContext.Provider,
    { value: { user, session, loading, profile, currentOrg } },
    children
  );
}

export { AuthContext };
export type { UserProfile, OrgMembership };
