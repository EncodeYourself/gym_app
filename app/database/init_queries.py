
TABLE_STUDENTS = '''
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    last_name TEXT NOT NULL,
    first_name TEXT NOT NULL, 
    date_of_birth DATE, 
    phone TEXT,
    telegram_handle TEXT UNIQUE,  -- Added UNIQUE to prevent duplicate bot users
    address TEXT, 
    emergency_contact_phone TEXT, 
    emergency_contact_name TEXT,
    group_type TEXT CHECK (group_type IN ('adult', 'child')),  -- Renamed 'group' to avoid SQL keyword
    comment TEXT, 
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended')),
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))

);
'''

TABLE_TRAINERS  = '''
CREATE TABLE IF NOT EXISTS trainers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    phone TEXT NOT NULL,
    telegram_handle TEXT,
    role TEXT NOT NULL DEFAULT 'coach'
        CHECK (role IN ('coach', 'assistant', 'cutman', 'admin', 'other')),
    specialties TEXT,               -- free text: "youth, women, pads"
    pay_type TEXT
        CHECK (pay_type IN ('hourly', 'per_class', 'per_session', 'salary', 'volunteer', 'other')),
    pay_rate INTEGER,               -- in whatever currency unit; NULL if volunteer
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'inactive')),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
'''

TABLE_CLASSES = '''
CREATE TABLE IF NOT EXISTS classes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    instructor TEXT NOT NULL,
    schedule_day TEXT NOT NULL CHECK (schedule_day IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')),
    start_time TEXT NOT NULL CHECK (start_time GLOB '[0-2][0-9]:[0-5][0-9]' AND start_time <= '23:59'),   
    duration_minutes INTEGER DEFAULT 90,
    description TEXT,
    is_active INTEGER DEFAULT 1 NOT NULL CHECK (is_active IN (0,1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);'''


TABLE_PAYMENTS = '''
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    plan_id INTEGER NOT NULL,
    amount_paid INTEGER NOT NULL CHECK (amount_paid >= 0),
    payment_date TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    method TEXT NOT NULL CHECK (method IN ('cash', 'card', 'bank_transfer', 'other')),
    receipt_number TEXT UNIQUE,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'paid' CHECK (status IN ('paid', 'refunded', 'voided')),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE RESTRICT,
    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE RESTRICT
);
'''


TABLE_NOTES = '''
CREATE TABLE IF NOT EXISTS notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    author TEXT DEFAULT 'Owner',
    note_type TEXT CHECK (note_type IN ('injury', 'referral', 'feedback', 'complaint', 'general')),
    content TEXT NOT NULL,
    timestamp TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);
'''

TABLE_PLANS = '''
CREATE TABLE IF NOT EXISTS plans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    price INTEGER NOT NULL CHECK (price >= 0),
    duration_weeks INTEGER,
    max_trainings INTEGER,
    is_unlimited INTEGER NOT NULL DEFAULT 0 CHECK (is_unlimited IN (0,1)),
    is_single INTEGER NOT NULL DEFAULT 0 CHECK (is_single IN (0,1)),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    -- Single training must not have duration or be unlimited
    CHECK (
        is_single = 0 OR (
            duration_weeks IS NULL AND
            max_trainings = 1 AND
            is_unlimited = 0
        )
    ),
    -- Unlimited plan must not have max_trainings
    CHECK (
        is_unlimited = 0 OR max_trainings IS NULL
    ),
    -- Monthly plans must have duration weeks
    CHECK (
        is_single = 1 OR duration_weeks IS NOT NULL
    )
);
'''

TABLE_MEMBERSHIP = '''
CREATE TABLE IF NOT EXISTS memberships (
    membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL UNIQUE,
    plan_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,          -- YYYY-MM-DD
    expiry_date TEXT NOT NULL,         
    used_trainings INTEGER NOT NULL DEFAULT 0 CHECK (used_trainings >= 0),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'on_hold', 'expired', 'completed', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (student_id) REFERENCES students (id),
    FOREIGN KEY (plan_id) REFERENCES plans (id)
);'''

TABLE_ATTENDANCE = '''
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    class_id INTEGER NOT NULL,
    attendance_date DATE NOT NULL,
    attendance_type TEXT NOT NULL DEFAULT 'membership' CHECK (attendance_type IN ('membership', 'single', 'debt', 'trial')),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE RESTRICT,
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE RESTRICT,
    UNIQUE(student_id, class_id, attendance_date)
);'''

TABLE_EXPENSES = '''
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    expense_date TEXT NOT NULL,              -- YYYY-MM-DD
    category TEXT NOT NULL
        CHECK (category IN (
            'rent',
            'utilities',
            'cleaning',
            'salary',
            'equipment',
            'repairs',
            'marketing',
            'taxes',
            'other'
        )),
    amount INTEGER NOT NULL CHECK (amount >= 0),
    is_recurring INTEGER NOT NULL DEFAULT 0
        CHECK (is_recurring IN (0,1)),
    recurring_expense_id INTEGER,            -- NULL for manual/non-recurring expenses
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (recurring_expense_id) REFERENCES recurring_expenses(id) ON DELETE SET NULL
);'''

TABLE_REC_EXPENSES = '''
CREATE TABLE IF NOT EXISTS recurring_expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    category TEXT NOT NULL
        CHECK (category IN (
            'rent',
            'utilities',
            'cleaning',
            'salary',
            'equipment',
            'repairs',
            'marketing',
            'taxes',
            'other'
        )),
    amount INTEGER NOT NULL CHECK (amount >= 0),
    frequency TEXT NOT NULL DEFAULT 'monthly'
        CHECK (frequency IN ('weekly', 'monthly', 'quarterly', 'yearly')),
    day_of_month INTEGER CHECK (
        day_of_month IS NULL OR
        (day_of_month >= 1 AND day_of_month <= 31)
    ),
    day_of_week INTEGER CHECK (
        day_of_week IS NULL OR
        (day_of_week >= 0 AND day_of_week <= 6)  -- 0=Monday, 6=Sunday
    ),
    is_active INTEGER NOT NULL DEFAULT 1
        CHECK (is_active IN (0,1)),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);'''

TABLE_SUBSTITUTIONS = '''
CREATE TABLE IF NOT EXISTS substitutions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    class_id INTEGER NOT NULL,
    original_trainer_id INTEGER NOT NULL,      -- who was supposed to teach
    substitute_trainer_id INTEGER NOT NULL,    -- who actually taught
    date TEXT NOT NULL,                        -- YYYY-MM-DD
    reason TEXT,                               -- free text, optional
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE CASCADE,
    FOREIGN KEY (original_trainer_id) REFERENCES trainers(id) ON DELETE RESTRICT,
    FOREIGN KEY (substitute_trainer_id) REFERENCES trainers(id) ON DELETE RESTRICT
);
'''

# VIEW_CASHFLOW = '''
# CREATE VIEW cashflow AS
# SELECT
#     'income' AS type,
#     payment_date AS date,
#     amount_paid AS amount,
#     method AS method,
#     notes
# FROM payments

# UNION ALL

# SELECT
#     'expense' AS type,
#     expense_date AS date,
#     amount,
#     NULL AS method,
#     notes
# FROM expenses;
# '''

#NOT_SURE = '''
#SELECT
#    strftime('%Y-%m', date) AS month,
#    SUM(CASE WHEN type = 'income' THEN amount ELSE 0 END) AS income,
#    SUM(CASE WHEN type = 'expense' THEN amount ELSE 0 END) AS expenses,
#    SUM(CASE WHEN type = 'income' THEN amount ELSE -amount END) AS net
#FROM cashflow
#GROUP BY month
#ORDER BY month;
#'''
TABLE_HOLDS = '''
CREATE TABLE IF NOT EXISTS membership_holds (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    membership_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,                 -- YYYY-MM-DD
    end_date TEXT,                            -- NULL while hold is active
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'ended', 'cancelled')),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (membership_id) REFERENCES memberships(membership_id) ON DELETE CASCADE
);'''
