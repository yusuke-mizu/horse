-- D1 schema for horse-sim Worker
CREATE TABLE IF NOT EXISTS horses (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  name TEXT UNIQUE NOT NULL,
  sex TEXT,
  birth_year INTEGER
);

CREATE TABLE IF NOT EXISTS races (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  date TEXT NOT NULL,
  course TEXT NOT NULL,
  surface TEXT NOT NULL,
  distance INTEGER NOT NULL,
  track_condition TEXT,
  race_name TEXT,
  race_number INTEGER,
  winning_time REAL,
  pace_label TEXT
);

CREATE TABLE IF NOT EXISTS race_entries (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  race_id INTEGER NOT NULL,
  horse_id INTEGER NOT NULL,
  gate INTEGER,
  weight REAL,
  odds REAL,
  popularity INTEGER,
  running_style TEXT
);

CREATE TABLE IF NOT EXISTS horse_performances (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  horse_id INTEGER NOT NULL,
  race_id INTEGER NOT NULL,
  date TEXT NOT NULL,
  course TEXT NOT NULL,
  surface TEXT NOT NULL,
  distance INTEGER NOT NULL,
  track_condition TEXT,
  gate INTEGER,
  running_style TEXT,
  pace TEXT,
  finish_position INTEGER,
  finish_time REAL,
  last_3f REAL,
  margin REAL,
  raw_performance REAL,
  adjusted_performance REAL,
  estimated_ability REAL
);

CREATE INDEX IF NOT EXISTS idx_perf_horse_date ON horse_performances(horse_id, date);
CREATE INDEX IF NOT EXISTS idx_races_date ON races(date);
CREATE INDEX IF NOT EXISTS idx_entries_race ON race_entries(race_id);
