SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS characters (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    aliases     TEXT DEFAULT '[]',
    description TEXT DEFAULT '',
    first_seen  INTEGER NOT NULL,
    last_seen   INTEGER DEFAULT 0,
    status      TEXT DEFAULT 'active',
    merged_into TEXT DEFAULT NULL,
    confidence  REAL DEFAULT 1.0,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS character_states (
    id           TEXT PRIMARY KEY,
    character_id TEXT NOT NULL REFERENCES characters(id),
    episode_num  INTEGER NOT NULL,
    emotion      TEXT DEFAULT '',
    goal         TEXT DEFAULT '',
    identity     TEXT DEFAULT '',
    appearance   TEXT DEFAULT '',
    notes        TEXT DEFAULT '',
    created_at   TEXT NOT NULL,
    UNIQUE(character_id, episode_num)
);

CREATE TABLE IF NOT EXISTS relationships (
    id           TEXT PRIMARY KEY,
    character_a  TEXT NOT NULL REFERENCES characters(id),
    character_b  TEXT NOT NULL REFERENCES characters(id),
    relation     TEXT NOT NULL,
    direction    TEXT DEFAULT 'bidirectional',
    established  INTEGER NOT NULL,
    ended        INTEGER DEFAULT NULL,
    confidence   REAL DEFAULT 1.0,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plot_events (
    id           TEXT PRIMARY KEY,
    episode_num  INTEGER NOT NULL,
    start_time   TEXT DEFAULT '',
    end_time     TEXT DEFAULT '',
    event_type   TEXT NOT NULL,
    description  TEXT NOT NULL,
    characters   TEXT DEFAULT '[]',
    importance   REAL DEFAULT 0.5,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS plot_threads (
    id           TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    description  TEXT NOT NULL,
    thread_type  TEXT DEFAULT 'foreshadow',
    status       TEXT DEFAULT 'open',
    opened_at    INTEGER NOT NULL,
    resolved_at  INTEGER DEFAULT NULL,
    resolution   TEXT DEFAULT '',
    characters   TEXT DEFAULT '[]',
    confidence   REAL DEFAULT 1.0,
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS episode_summaries (
    episode_num  INTEGER PRIMARY KEY,
    summary      TEXT NOT NULL,
    key_events   TEXT DEFAULT '[]',
    mood         TEXT DEFAULT '',
    cliffhanger  TEXT DEFAULT '',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS series_state (
    id                  INTEGER PRIMARY KEY DEFAULT 1,
    current_episode     INTEGER DEFAULT 0,
    total_episodes      INTEGER DEFAULT 0,
    main_plot_summary   TEXT DEFAULT '',
    genre               TEXT DEFAULT '',
    setting             TEXT DEFAULT '',
    tone                TEXT DEFAULT '',
    updated_at          TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS character_assets (
    id           TEXT PRIMARY KEY,
    character_id TEXT NOT NULL REFERENCES characters(id),
    asset_type   TEXT NOT NULL,
    file_path    TEXT NOT NULL,
    episode_num  INTEGER NOT NULL,
    timestamp    TEXT DEFAULT '',
    description  TEXT DEFAULT '',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence_assets (
    id           TEXT PRIMARY KEY,
    episode_num  INTEGER NOT NULL,
    asset_type   TEXT NOT NULL,
    file_path    TEXT NOT NULL,
    description  TEXT NOT NULL,
    related_thread TEXT DEFAULT NULL,
    timestamp    TEXT DEFAULT '',
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS state_patches (
    id           TEXT PRIMARY KEY,
    episode_num  INTEGER NOT NULL,
    patch_data   TEXT NOT NULL,
    status       TEXT DEFAULT 'committed',
    confidence   REAL DEFAULT 1.0,
    created_at   TEXT NOT NULL,
    committed_at TEXT DEFAULT NULL
);

CREATE TABLE IF NOT EXISTS operation_logs (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_num  INTEGER NOT NULL,
    action_type  TEXT NOT NULL,
    action_data  TEXT DEFAULT '{}',
    result       TEXT DEFAULT '',
    created_at   TEXT NOT NULL
);
"""
