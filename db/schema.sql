-- Shared contract between the Python scanner (writer) and the web app (reader + votes).
CREATE TABLE IF NOT EXISTS sales (
  id INTEGER PRIMARY KEY,            -- estatesales.net sale id
  name TEXT, org TEXT, city TEXT, state TEXT, address TEXT,
  url TEXT, type_name TEXT,          -- e.g. 'Traditional', 'OnlineOnlyAuctions'
  start_date TEXT, end_date TEXT,    -- ISO
  dates_json TEXT,                   -- [{date, hours}] when known
  score REAL,                        -- high-end sale score
  standout INTEGER DEFAULT 0,        -- 1 if score >= threshold
  why TEXT,                          -- human-readable reason
  top_json TEXT,                     -- [{pic_id, thumb, url, p}] top luxe photos
  first_seen TEXT, updated_at TEXT,
  emailed_at TEXT                    -- set when announced as a standout
);
CREATE TABLE IF NOT EXISTS hits (
  pic_id TEXT NOT NULL,
  category TEXT NOT NULL,            -- mirror | cabinet | buddhist | art_deco
  sale_id INTEGER NOT NULL,
  score REAL, model_score REAL,      -- final score (incl. boosts / learned) and raw model score
  caption TEXT, thumb TEXT, url TEXT, why TEXT,
  first_seen TEXT,
  hidden INTEGER DEFAULT 0,          -- 1 if suppressed by the learned taste model
  emailed_at TEXT,
  PRIMARY KEY (pic_id, category)
);
CREATE INDEX IF NOT EXISTS hits_sale ON hits(sale_id);
CREATE INDEX IF NOT EXISTS hits_seen ON hits(first_seen);
CREATE TABLE IF NOT EXISTS embeddings (
  pic_id TEXT PRIMARY KEY,
  emb BLOB                           -- float16 little-endian, L2-normalized SigLIP image embedding
);
CREATE TABLE IF NOT EXISTS votes (
  target_type TEXT NOT NULL,         -- 'hit' | 'sale'
  target_id TEXT NOT NULL,           -- pic_id or sale id
  category TEXT NOT NULL DEFAULT '', -- hit category; '' for sales
  vote INTEGER,                      -- +1 / -1 / NULL (cleared)
  saved INTEGER DEFAULT 0,           -- bookmarked "want to go see"
  note TEXT,
  updated_at TEXT,
  PRIMARY KEY (target_type, target_id, category)
);
