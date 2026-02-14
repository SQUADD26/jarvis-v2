-- ============================================================
-- OAuth integration accounts per provider
-- Da eseguire DOPO 20260214092654_auth_and_orgs.sql
-- ============================================================

-- ── Gmail Accounts ────────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS gmail_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  access_token TEXT NOT NULL,
  refresh_token TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  scopes TEXT[],
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, email)
);

ALTER TABLE gmail_accounts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own gmail_accounts"
  ON gmail_accounts FOR SELECT
  USING (user_id = auth.uid());

CREATE POLICY "Users can insert own gmail_accounts"
  ON gmail_accounts FOR INSERT
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update own gmail_accounts"
  ON gmail_accounts FOR UPDATE
  USING (user_id = auth.uid());

CREATE POLICY "Users can delete own gmail_accounts"
  ON gmail_accounts FOR DELETE
  USING (user_id = auth.uid());

CREATE POLICY "service_role_all on gmail_accounts"
  ON gmail_accounts FOR ALL TO service_role
  USING (true) WITH CHECK (true);


-- ── Google Calendar Accounts ──────────────────────────────────────

CREATE TABLE IF NOT EXISTS google_calendar_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
  email TEXT NOT NULL,
  access_token TEXT NOT NULL,
  refresh_token TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  scopes TEXT[],
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, email)
);

ALTER TABLE google_calendar_accounts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own google_calendar_accounts"
  ON google_calendar_accounts FOR SELECT
  USING (user_id = auth.uid());

CREATE POLICY "Users can insert own google_calendar_accounts"
  ON google_calendar_accounts FOR INSERT
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update own google_calendar_accounts"
  ON google_calendar_accounts FOR UPDATE
  USING (user_id = auth.uid());

CREATE POLICY "Users can delete own google_calendar_accounts"
  ON google_calendar_accounts FOR DELETE
  USING (user_id = auth.uid());

CREATE POLICY "service_role_all on google_calendar_accounts"
  ON google_calendar_accounts FOR ALL TO service_role
  USING (true) WITH CHECK (true);


-- ── Notion Accounts ───────────────────────────────────────────────

CREATE TABLE IF NOT EXISTS notion_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
  workspace_name TEXT,
  workspace_id TEXT,
  access_token TEXT NOT NULL,
  bot_id TEXT,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id, workspace_id)
);

ALTER TABLE notion_accounts ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own notion_accounts"
  ON notion_accounts FOR SELECT
  USING (user_id = auth.uid());

CREATE POLICY "Users can insert own notion_accounts"
  ON notion_accounts FOR INSERT
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update own notion_accounts"
  ON notion_accounts FOR UPDATE
  USING (user_id = auth.uid());

CREATE POLICY "Users can delete own notion_accounts"
  ON notion_accounts FOR DELETE
  USING (user_id = auth.uid());

CREATE POLICY "service_role_all on notion_accounts"
  ON notion_accounts FOR ALL TO service_role
  USING (true) WITH CHECK (true);


-- ── Fathom OAuth Tokens ───────────────────────────────────────────

CREATE TABLE IF NOT EXISTS fathom_oauth_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  org_id UUID REFERENCES organizations(id) ON DELETE CASCADE,
  access_token TEXT NOT NULL,
  refresh_token TEXT NOT NULL,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT now(),
  updated_at TIMESTAMPTZ DEFAULT now(),
  UNIQUE(user_id)
);

ALTER TABLE fathom_oauth_tokens ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own fathom_oauth_tokens"
  ON fathom_oauth_tokens FOR SELECT
  USING (user_id = auth.uid());

CREATE POLICY "Users can insert own fathom_oauth_tokens"
  ON fathom_oauth_tokens FOR INSERT
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "Users can update own fathom_oauth_tokens"
  ON fathom_oauth_tokens FOR UPDATE
  USING (user_id = auth.uid());

CREATE POLICY "Users can delete own fathom_oauth_tokens"
  ON fathom_oauth_tokens FOR DELETE
  USING (user_id = auth.uid());

CREATE POLICY "service_role_all on fathom_oauth_tokens"
  ON fathom_oauth_tokens FOR ALL TO service_role
  USING (true) WITH CHECK (true);


-- ── Indexes ───────────────────────────────────────────────────────

CREATE INDEX IF NOT EXISTS idx_gmail_accounts_user_id ON gmail_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_gmail_accounts_org_id ON gmail_accounts(org_id);
CREATE INDEX IF NOT EXISTS idx_google_calendar_accounts_user_id ON google_calendar_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_google_calendar_accounts_org_id ON google_calendar_accounts(org_id);
CREATE INDEX IF NOT EXISTS idx_notion_accounts_user_id ON notion_accounts(user_id);
CREATE INDEX IF NOT EXISTS idx_notion_accounts_org_id ON notion_accounts(org_id);
CREATE INDEX IF NOT EXISTS idx_fathom_oauth_tokens_user_id ON fathom_oauth_tokens(user_id);
CREATE INDEX IF NOT EXISTS idx_fathom_oauth_tokens_org_id ON fathom_oauth_tokens(org_id);
