ALTER TABLE automod_config
    ADD COLUMN IF NOT EXISTS invite_links_enabled    BOOLEAN DEFAULT TRUE,
    ADD COLUMN IF NOT EXISTS duplicate_window_seconds INTEGER DEFAULT 30;
