AUTOMATION_SCHEMA = '''
CREATE TABLE IF NOT EXISTS automation_accounts (
    user_id INTEGER PRIMARY KEY REFERENCES users(id),
    token_hash TEXT NOT NULL,
    token_prefix TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    can_import INTEGER NOT NULL DEFAULT 0 CHECK (can_import IN (0, 1)),
    allowed_seasons_json TEXT NOT NULL DEFAULT '[]',
    created_by INTEGER NOT NULL REFERENCES users(id),
    last_used_at TEXT,
    deleted_at TEXT
);
CREATE TABLE IF NOT EXISTS automation_imports (
    user_id INTEGER NOT NULL REFERENCES automation_accounts(user_id),
    request_key TEXT NOT NULL,
    payload_hash TEXT NOT NULL,
    result_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, request_key)
);
'''
