-- Existing account/session field names match the original Python service.
CREATE TABLE IF NOT EXISTS accounts (
  id TEXT PRIMARY KEY,
  discord_id TEXT UNIQUE NOT NULL,
  display_name TEXT NOT NULL,
  created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
  key_hash TEXT PRIMARY KEY,
  account_id TEXT NOT NULL REFERENCES accounts(id),
  install_id TEXT NOT NULL,
  release_id TEXT NOT NULL,
  created_at INTEGER NOT NULL,
  last_seen INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS sessions_account_install ON sessions(account_id, install_id);
CREATE TABLE IF NOT EXISTS login_attempts (
  id TEXT PRIMARY KEY,
  secret_hash TEXT NOT NULL,
  state_hash TEXT UNIQUE,
  pkce_verifier TEXT,
  install_id TEXT NOT NULL,
  release_id TEXT NOT NULL,
  status TEXT NOT NULL CHECK(status IN ('pending','checking','ready','denied','consumed')),
  created_at INTEGER NOT NULL,
  expires_at INTEGER NOT NULL,
  last_poll INTEGER NOT NULL DEFAULT 0,
  discord_id TEXT,
  display_name TEXT,
  error_status INTEGER,
  message TEXT,
  claim_id TEXT
);
CREATE INDEX IF NOT EXISTS login_attempts_expiry ON login_attempts(expires_at);
CREATE TABLE IF NOT EXISTS login_rate_limits (
  ip_hash TEXT NOT NULL,
  bucket INTEGER NOT NULL,
  count INTEGER NOT NULL,
  PRIMARY KEY(ip_hash, bucket)
);
CREATE INDEX IF NOT EXISTS login_rate_limits_bucket ON login_rate_limits(bucket);
