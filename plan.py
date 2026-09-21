TABLE_PLANS = '''
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price INTEGER NOT NULL CHECK (price >= 0),
    duration_weeks INTEGER,  -- NULL for single training
    max_trainings INTEGER,    -- NULL for unlimited
    is_unlimited INTEGER DEFAULT 0 NOT NULL CHECK (is_unlimited IN (0,1)),
    is_single INTEGER DEFAULT 0 NOT NULL CHECK (is_single IN (0,1)),
    is_active INTEGER DEFAULT 1 NOT NULL CHECK (is_active IN (0,1))
);
'''