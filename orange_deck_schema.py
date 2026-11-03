"""SQLite mirror of DB migration 0025: the Orange Fortune deck library.

Decks are not lineups: they have their own rows, favorites and ranking so they never
enter ordinary lineup counts, scores or live comps.
"""

ORANGE_DECK_SCHEMA = """
CREATE TABLE IF NOT EXISTS orange_decks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    card_id_1 TEXT,
    card_id_2 TEXT,
    card_id_3 TEXT,
    portal_id TEXT NOT NULL CHECK (portal_id IN ('stable', 'volatile', 'unknown')),
    energy INTEGER NOT NULL DEFAULT 0,
    note TEXT NOT NULL DEFAULT '',
    key_rounds TEXT NOT NULL DEFAULT '',
    alternatives TEXT NOT NULL DEFAULT '',
    formation_json TEXT,
    formation_season_id TEXT,
    formation_version_id TEXT,
    card_version TEXT NOT NULL,
    card_snapshot_json TEXT NOT NULL DEFAULT '[]',
    status TEXT NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'hidden', 'deleted')),
    hidden_reason TEXT NOT NULL DEFAULT '',
    featured INTEGER NOT NULL DEFAULT 0 CHECK (featured IN (0, 1)),
    featured_at TEXT,
    forked_from_id INTEGER REFERENCES orange_decks(id) ON DELETE SET NULL,
    version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    published_at TEXT,
    CONSTRAINT orange_decks_public_cards CHECK (
        status IN ('draft', 'deleted')
        OR (card_id_1 IS NOT NULL AND card_id_2 IS NOT NULL AND card_id_3 IS NOT NULL)
    ),
    CONSTRAINT orange_decks_distinct_cards CHECK (
        (card_id_1 IS NULL OR card_id_2 IS NULL OR card_id_1 <> card_id_2)
        AND (card_id_1 IS NULL OR card_id_3 IS NULL OR card_id_1 <> card_id_3)
        AND (card_id_2 IS NULL OR card_id_3 IS NULL OR card_id_2 <> card_id_3)
    ),
    CONSTRAINT orange_decks_formation_season CHECK (formation_json IS NULL OR formation_season_id IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_orange_decks_status_published ON orange_decks (status, published_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_orange_decks_user_updated ON orange_decks (user_id, updated_at DESC, id DESC);
CREATE INDEX IF NOT EXISTS idx_orange_decks_featured ON orange_decks (featured, featured_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS orange_deck_favorites (
    user_id INTEGER NOT NULL REFERENCES users(id),
    deck_id INTEGER NOT NULL REFERENCES orange_decks(id),
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, deck_id)
);

CREATE INDEX IF NOT EXISTS idx_orange_deck_favorites_deck ON orange_deck_favorites (deck_id);
"""
