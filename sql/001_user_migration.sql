-- ============================================================
-- Migrazione Telegram linking su user_profiles
-- Da eseguire DOPO 20260214092654_auth_and_orgs.sql
-- ============================================================

-- 1. Aggiungere telegram_id a user_profiles (già esistente)
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS telegram_id BIGINT UNIQUE;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS language TEXT DEFAULT 'it';
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS timezone TEXT DEFAULT 'Europe/Rome';
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT now();

CREATE INDEX IF NOT EXISTS idx_user_profiles_telegram_id ON user_profiles(telegram_id);


-- 2. Tabella telegram_link_tokens
CREATE TABLE IF NOT EXISTS telegram_link_tokens (
  token TEXT PRIMARY KEY DEFAULT encode(gen_random_bytes(32), 'hex'),
  user_id UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
  created_at TIMESTAMPTZ DEFAULT now(),
  expires_at TIMESTAMPTZ DEFAULT now() + interval '10 minutes',
  used BOOLEAN DEFAULT false
);

ALTER TABLE telegram_link_tokens ENABLE ROW LEVEL SECURITY;

CREATE POLICY deny_anon ON telegram_link_tokens
  AS RESTRICTIVE FOR ALL TO anon USING (false);

CREATE POLICY service_role_all ON telegram_link_tokens
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE POLICY select_own ON telegram_link_tokens
  FOR SELECT TO authenticated USING ((SELECT auth.uid()) = user_id);

CREATE POLICY insert_own ON telegram_link_tokens
  FOR INSERT TO authenticated WITH CHECK ((SELECT auth.uid()) = user_id);


-- 3. RPC: collega account Telegram via deep link token
CREATE OR REPLACE FUNCTION link_telegram(p_token TEXT, p_telegram_id BIGINT)
RETURNS UUID
LANGUAGE plpgsql SECURITY DEFINER AS $$
DECLARE
  v_user_id UUID;
BEGIN
  SELECT user_id INTO v_user_id
  FROM telegram_link_tokens
  WHERE token = p_token AND NOT used AND expires_at > now();

  IF v_user_id IS NULL THEN
    RAISE EXCEPTION 'Token invalido o scaduto';
  END IF;

  UPDATE user_profiles SET telegram_id = p_telegram_id, updated_at = now()
  WHERE id = v_user_id;

  UPDATE telegram_link_tokens SET used = true WHERE token = p_token;

  RETURN v_user_id;
END;
$$;


-- 4. RPC: risolvi Telegram ID → UUID
CREATE OR REPLACE FUNCTION resolve_telegram_id(p_telegram_id BIGINT)
RETURNS UUID
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  SELECT id FROM user_profiles WHERE telegram_id = p_telegram_id;
$$;
