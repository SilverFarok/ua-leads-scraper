CREATE TABLE IF NOT EXISTS business_leads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query_niche TEXT NOT NULL,
    query_city TEXT NOT NULL,
    company_name TEXT NOT NULL,
    city TEXT NOT NULL,
    website TEXT NULL,
    google_maps_url TEXT NULL,
    phone_raw TEXT NULL,
    phone_normalized TEXT NULL,
    phone_type TEXT NOT NULL DEFAULT 'unknown',
    source TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_business_leads_phone_normalized
    ON business_leads (phone_normalized);
