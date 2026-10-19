
TABLE_STUDENTS = '''
CREATE TABLE IF NOT EXISTS students (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    last_name TEXT NOT NULL,
    first_name TEXT NOT NULL,
    date_of_birth DATE,
    phone TEXT NOT NULL,
    telegram_handle TEXT UNIQUE,
    address TEXT,
    emergency_contact_phone TEXT,
    emergency_contact_name TEXT,
    group_type TEXT CHECK (group_type IN ('adult', 'child')),
    comment TEXT,
    status TEXT DEFAULT 'active' CHECK (status IN ('active', 'inactive', 'suspended')),
    credit_balance INTEGER NOT NULL DEFAULT 0,
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
    instructor_id INTEGER,
    schedule_day TEXT NOT NULL CHECK (schedule_day IN ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')),
    start_time TEXT NOT NULL CHECK (start_time GLOB '[0-2][0-9]:[0-5][0-9]' AND start_time <= '23:59'),   
    duration_minutes INTEGER DEFAULT 90,
    description TEXT,
    is_active INTEGER DEFAULT 1 NOT NULL CHECK (is_active IN (0,1)),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (instructor_id) REFERENCES trainers(id) ON DELETE RESTRICT
);'''


TABLE_PAYMENTS = '''
CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    amount_paid INTEGER NOT NULL CHECK (amount_paid >= 0),
    plan_id INTEGER,
    membership_id INTEGER, 
    payment_date TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    method TEXT NOT NULL CHECK (method IN ('cash', 'card', 'bank_transfer', 'other')),
    payment_category TEXT NOT NULL DEFAULT 'membership_new'
        CHECK (payment_category IN (
            'membership_new', 'membership_renewal', 'membership_upgrade',
            'drop_in', 'credit_payment', 'refund', 'other'
        )),
    receipt_number TEXT UNIQUE,
    notes TEXT,
    status TEXT NOT NULL DEFAULT 'paid'
        CHECK (status IN ('paid', 'refunded', 'voided')),
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE RESTRICT,
    FOREIGN KEY (plan_id) REFERENCES plans(id) ON DELETE RESTRICT,
    FOREIGN KEY (membership_id) REFERENCES memberships(id) ON DELETE RESTRICT
);'''

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
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    plan_id INTEGER NOT NULL,
    start_date TEXT NOT NULL,
    expiry_date TEXT NOT NULL,
    used_trainings INTEGER NOT NULL DEFAULT 0 CHECK (used_trainings >= 0),
    status TEXT NOT NULL DEFAULT 'active'
        CHECK (status IN ('active', 'on_hold', 'expired',
                          'completed', 'cancelled', 'upgraded')),
    upgraded_from INTEGER
        REFERENCES memberships(id) ON DELETE SET NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (student_id) REFERENCES students (id),
    FOREIGN KEY (plan_id) REFERENCES plans (id),
    CHECK (upgraded_from IS NULL OR upgraded_from != id),
    UNIQUE (upgraded_from)
);
'''

INDEX_MEMBERSHIP = '''
CREATE INDEX IF NOT EXISTS idx_memberships_student
    ON memberships(student_id);
'''

TABLE_ATTENDANCE = '''
CREATE TABLE IF NOT EXISTS attendance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    class_id INTEGER NOT NULL,
    attendance_date DATE NOT NULL,
    attendance_type TEXT NOT NULL DEFAULT 'membership' CHECK (attendance_type IN ('membership', 'single', 'debt', 'trial')),
    membership_id INTEGER, 
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE RESTRICT,
    FOREIGN KEY (class_id) REFERENCES classes(id) ON DELETE RESTRICT,
    FOREIGN KEY (membership_id) REFERENCES memberships(id) ON DELETE SET NULL,
    UNIQUE(student_id, class_id, attendance_date)
);'''

INDEX_ATTENDANCE_1 = '''
    CREATE INDEX idx_attendance_membership ON attendance(membership_id)
'''
INDEX_ATTENDANCE_2 = '''
CREATE INDEX IF NOT EXISTS idx_attendance_class_date
    ON attendance(class_id, attendance_date);
'''
INDEX_ATTENDANCE_3 = '''
CREATE INDEX IF NOT EXISTS idx_attendance_class_date
    ON attendance(class_id, attendance_date);
'''
INDEX_ATTENDANCE_4 = '''
CREATE INDEX IF NOT EXISTS idx_substitutions_class_date
    ON substitutions(class_id, date);
'''
TABLE_EXPENSES = '''
CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    payee_id INTEGER NOT NULL,
    expense_date TEXT NOT NULL,
    category TEXT NOT NULL
        CHECK (category IN (
            'rent', 'utilities', 'cleaning', 'salary', 'equipment',
            'repairs', 'marketing', 'taxes', 'other'
        )),
    amount INTEGER NOT NULL CHECK (amount >= 0),
    recurring_expense_id INTEGER,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (payee_id) REFERENCES payees(id) ON DELETE RESTRICT,
    FOREIGN KEY (recurring_expense_id) REFERENCES recurring_expenses(id) ON DELETE RESTRICT
);'''

INDEX_EXPENSES_DATE  = '''
CREATE INDEX IF NOT EXISTS idx_expenses_date
    ON expenses(expense_date);
'''
INDEX_EXPENSES_PAYEE = '''
CREATE INDEX IF NOT EXISTS idx_expenses_payee
    ON expenses(payee_id);
'''

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
        CHECK (frequency IN ('weekly', 'monthly', 'quarterly', 'yearly')
    ),
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

TABLE_PAYEES = '''CREATE TABLE IF NOT EXISTS payees (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,                    -- always filled, even for trainer-linked rows
    linked_trainer_id INTEGER,                    -- NULL for external vendors
    preferred_category TEXT
        CHECK (preferred_category IS NULL OR preferred_category IN (
            'rent', 'utilities', 'cleaning', 'salary', 'equipment',
            'repairs', 'marketing', 'taxes', 'other'
        )),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (linked_trainer_id) REFERENCES trainers(id) ON DELETE RESTRICT
);'''

INDEX_PAYEES = '''
CREATE UNIQUE INDEX IF NOT EXISTS idx_payees_trainer
    ON payees(linked_trainer_id) WHERE linked_trainer_id IS NOT NULL;
'''

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
);'''


TABLE_CREDIT = '''
CREATE TABLE IF NOT EXISTS credit_entries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL,
    amount INTEGER NOT NULL,          
    entry_type TEXT NOT NULL
        CHECK (entry_type IN (
            'overpayment',
            'underpayment',
            'credit_applied',
            'debt_settled',
            'refund',
            'manual_adjustment',
            'reversal'
        )),
    payment_id INTEGER,               
    membership_id INTEGER,            
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE RESTRICT,
    FOREIGN KEY (payment_id) REFERENCES payments(id) ON DELETE SET NULL,
    FOREIGN KEY (membership_id) REFERENCES memberships(id) ON DELETE SET NULL
);'''

INDEX_CREDIT = '''
CREATE INDEX IF NOT EXISTS idx_credit_entries_student
    ON credit_entries(student_id);
'''

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
    FOREIGN KEY (membership_id) REFERENCES memberships(id) ON DELETE CASCADE
);'''
