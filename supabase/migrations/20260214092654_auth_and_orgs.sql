-- ╔════════════════════════════════════════════════════════════════╗
-- ║  Auth & Multi-tenancy: Organizations, Memberships, Profiles  ║
-- ╚════════════════════════════════════════════════════════════════╝

-- ── Organizations ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS organizations (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  name TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL,
  created_by UUID REFERENCES auth.users(id),
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;

-- ── Organization Memberships ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS org_memberships (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('owner', 'admin', 'member')),
  created_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(org_id, user_id)
);

ALTER TABLE org_memberships ENABLE ROW LEVEL SECURITY;

-- ── User Profiles ─────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS user_profiles (
  id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
  full_name TEXT,
  avatar_url TEXT,
  status TEXT DEFAULT 'waitlist' CHECK (status IN ('waitlist', 'approved', 'suspended')),
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE user_profiles ENABLE ROW LEVEL SECURITY;

-- ── Waitlist ──────────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS waitlist (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  full_name TEXT,
  reason TEXT,
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
  created_at TIMESTAMPTZ DEFAULT now()
);

ALTER TABLE waitlist ENABLE ROW LEVEL SECURITY;

-- ── Add org_id to existing tables ─────────────────────────────────

ALTER TABLE chat_history ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id);
ALTER TABLE memory_facts ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id);
ALTER TABLE task_queue ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id);
ALTER TABLE llm_logs ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id);
ALTER TABLE user_preferences ADD COLUMN IF NOT EXISTS org_id UUID REFERENCES organizations(id);

-- ── Indexes ───────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_org_memberships_user_id ON org_memberships(user_id);
CREATE INDEX IF NOT EXISTS idx_org_memberships_org_id ON org_memberships(org_id);
CREATE INDEX IF NOT EXISTS idx_user_profiles_status ON user_profiles(status);
CREATE INDEX IF NOT EXISTS idx_waitlist_status ON waitlist(status);
CREATE INDEX IF NOT EXISTS idx_chat_history_org_id ON chat_history(org_id);
CREATE INDEX IF NOT EXISTS idx_memory_facts_org_id ON memory_facts(org_id);
CREATE INDEX IF NOT EXISTS idx_task_queue_org_id ON task_queue(org_id);
CREATE INDEX IF NOT EXISTS idx_llm_logs_org_id ON llm_logs(org_id);

-- ── RLS Policies ──────────────────────────────────────────────────

-- Helper: get user's org_ids
CREATE OR REPLACE FUNCTION get_user_org_ids()
RETURNS SETOF UUID
LANGUAGE sql
SECURITY DEFINER
STABLE
AS $$
  SELECT org_id FROM org_memberships WHERE user_id = auth.uid();
$$;

-- Organizations: members can view their orgs
CREATE POLICY "Users can view their organizations"
  ON organizations FOR SELECT
  USING (id IN (SELECT get_user_org_ids()));

CREATE POLICY "Authenticated users can create organizations"
  ON organizations FOR INSERT
  WITH CHECK (auth.uid() IS NOT NULL);

-- Org Memberships: members can view memberships in their orgs
CREATE POLICY "Users can view memberships in their orgs"
  ON org_memberships FOR SELECT
  USING (org_id IN (SELECT get_user_org_ids()));

CREATE POLICY "Owners and admins can manage memberships"
  ON org_memberships FOR ALL
  USING (
    org_id IN (
      SELECT org_id FROM org_memberships
      WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
    )
  );

-- User Profiles: users can view/edit their own profile
CREATE POLICY "Users can view own profile"
  ON user_profiles FOR SELECT
  USING (id = auth.uid());

CREATE POLICY "Users can update own profile"
  ON user_profiles FOR UPDATE
  USING (id = auth.uid());

CREATE POLICY "Users can insert own profile"
  ON user_profiles FOR INSERT
  WITH CHECK (id = auth.uid());

-- Waitlist: only admins/owners can view
CREATE POLICY "Admins can view waitlist"
  ON waitlist FOR SELECT
  USING (
    EXISTS (
      SELECT 1 FROM org_memberships
      WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
    )
  );

CREATE POLICY "Anyone can join waitlist"
  ON waitlist FOR INSERT
  WITH CHECK (true);

CREATE POLICY "Admins can update waitlist"
  ON waitlist FOR UPDATE
  USING (
    EXISTS (
      SELECT 1 FROM org_memberships
      WHERE user_id = auth.uid() AND role IN ('owner', 'admin')
    )
  );

-- Chat History: users see only their org's data
CREATE POLICY "Users can view own org chat_history"
  ON chat_history FOR SELECT
  USING (org_id IN (SELECT get_user_org_ids()));

CREATE POLICY "Users can insert own org chat_history"
  ON chat_history FOR INSERT
  WITH CHECK (org_id IN (SELECT get_user_org_ids()));

-- Memory Facts: users see only their org's data
CREATE POLICY "Users can view own org memory_facts"
  ON memory_facts FOR SELECT
  USING (org_id IN (SELECT get_user_org_ids()));

CREATE POLICY "Users can manage own org memory_facts"
  ON memory_facts FOR ALL
  USING (org_id IN (SELECT get_user_org_ids()));

-- Task Queue: users see only their org's data
CREATE POLICY "Users can view own org task_queue"
  ON task_queue FOR SELECT
  USING (org_id IN (SELECT get_user_org_ids()));

CREATE POLICY "Users can manage own org task_queue"
  ON task_queue FOR ALL
  USING (org_id IN (SELECT get_user_org_ids()));

-- LLM Logs: users see only their org's data
CREATE POLICY "Users can view own org llm_logs"
  ON llm_logs FOR SELECT
  USING (org_id IN (SELECT get_user_org_ids()));

-- ── Auto-create profile on signup ─────────────────────────────────

CREATE OR REPLACE FUNCTION handle_new_user()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  INSERT INTO user_profiles (id, full_name, status)
  VALUES (
    NEW.id,
    COALESCE(NEW.raw_user_meta_data->>'full_name', ''),
    'waitlist'
  );
  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;
CREATE TRIGGER on_auth_user_created
  AFTER INSERT ON auth.users
  FOR EACH ROW EXECUTE FUNCTION handle_new_user();
