CREATE TABLE IF NOT EXISTS ai_catalog_state (name TEXT PRIMARY KEY, revision TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS ai_documents (
  revision TEXT NOT NULL, id TEXT NOT NULL, server TEXT NOT NULL, kind TEXT NOT NULL,
  title TEXT NOT NULL, body TEXT NOT NULL, url TEXT NOT NULL, code TEXT NOT NULL,
  number TEXT NOT NULL, category TEXT NOT NULL,
  UNIQUE(revision,id)
);
CREATE INDEX IF NOT EXISTS ai_documents_scope ON ai_documents(revision,server,kind);
CREATE VIRTUAL TABLE IF NOT EXISTS ai_docs_fts USING fts5(title,body,content='ai_documents',content_rowid='rowid',tokenize='unicode61');
CREATE TRIGGER IF NOT EXISTS ai_documents_insert AFTER INSERT ON ai_documents BEGIN
  INSERT INTO ai_docs_fts(rowid,title,body) VALUES(new.rowid,new.title,new.body);
END;
CREATE TRIGGER IF NOT EXISTS ai_documents_delete AFTER DELETE ON ai_documents BEGIN
  INSERT INTO ai_docs_fts(ai_docs_fts,rowid,title,body) VALUES('delete',old.rowid,old.title,old.body);
END;
CREATE TABLE IF NOT EXISTS ai_daily_usage (
  account_id TEXT NOT NULL REFERENCES accounts(id), day TEXT NOT NULL,
  used INTEGER NOT NULL DEFAULT 0 CHECK(used BETWEEN 0 AND 5), PRIMARY KEY(account_id,day)
);
CREATE TABLE IF NOT EXISTS ai_global_usage (day TEXT PRIMARY KEY, attempts INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS ai_answer_cache (
  account_id TEXT NOT NULL REFERENCES accounts(id), cache_key TEXT NOT NULL,
  owner TEXT NOT NULL, status TEXT NOT NULL, lease_until INTEGER NOT NULL,
  reserved INTEGER NOT NULL DEFAULT 0, reservation_day TEXT,
  answer_json TEXT, expires_at INTEGER NOT NULL, PRIMARY KEY(account_id,cache_key)
);
CREATE INDEX IF NOT EXISTS ai_cache_expiry ON ai_answer_cache(expires_at);
