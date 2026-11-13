CREATE TABLE IF NOT EXISTS account_credentials (
  account_id TEXT PRIMARY KEY REFERENCES accounts(id),
  username TEXT NOT NULL UNIQUE,
  password_digest TEXT NOT NULL,
  updated_at INTEGER NOT NULL,
  registration_id TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS credential_intents (
  login_id TEXT PRIMARY KEY REFERENCES login_attempts(id) ON DELETE CASCADE,
  mode TEXT NOT NULL CHECK(mode IN ('register','recover')),
  username TEXT NOT NULL,
  password_digest TEXT NOT NULL,
  account_id TEXT REFERENCES accounts(id)
);
