
from contextlib import contextmanager
import sqlite3
from pathlib import Path
import polars as pl
import app.database.init_queries as all_queries
DB_PATH = Path(__file__).parent.parent / 'data' / 'business.db'



@contextmanager
def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 10000")
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()



def init_db(queries):
    """
    Create all tables, indexes, and triggers.

    Idempotent: safe to run on every startup. Tables and indexes use
    IF NOT EXISTS and are skipped if they exist. Triggers use
    DROP + CREATE, so stale definitions from earlier schema versions
    are replaced with the current ones.

    Uses executescript so a single entry can contain more than one
    statement (the trigger pairs need this).
    """
    with get_connection() as conn:
        # Drop any trigger this app has ever created. Any not
        # re-created by the TRIGGERS list below are now gone.
        for row in conn.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='trigger' AND name LIKE 'trg_%_updated_at'"
        ):
            conn.execute(f"DROP TRIGGER IF EXISTS {row[0]}")
        # … then run the tables and triggers list as before
        
    with get_connection() as conn:
        for query in queries:
            try:
                conn.executescript(query)
            except Exception as e:
                # Print the offending statement so the traceback is
                # actually usable, then re-raise with the original
                # traceback intact.
                print("FAILED STATEMENT:")
                print(query)
                print("ERROR:", e)
                raise
        # conn.commit() is handled by the context manager on exit.
    print("✅ Database initialized with all tables, indexes, and triggers!")


def reset_db():
    """
    WARNING: Drops all tables. Development only.
    Order matters — drop children before parents so FKs don't block
    the drops (though SQLite's default NO ACTION for FKs is deferred
    to commit, so reordering is belt-and-braces rather than strictly
    required).
    """
    tables = [
        # Leaf tables first (children of everything)
        'credit_entries',
        'membership_holds',
        'substitutions',
        'attendance',
        'payments',
        'memberships',
        'notes',
        'expenses',
        'recurring_expenses',
        'payees',
        'classes',
        'plans',
        'trainers',
        'students',
    ]
    with get_connection() as conn:
        for table in tables:
            conn.execute(f"DROP TABLE IF EXISTS {table};")
    print("⚠️  All tables dropped!")


def make_updated_at_trigger(table: str, pk_column: str) -> str:
    """
    Return SQL that keeps `updated_at` current on UPDATE for a table.

    Uses DROP + CREATE rather than CREATE IF NOT EXISTS, so re-running
    init_db replaces any stale trigger from an earlier schema version.
    `CREATE TRIGGER IF NOT EXISTS` silently leaves broken triggers in
    place forever — see the memberships DELETE bug where an old trigger
    referenced columns that no longer existed.

    Args:
        table: Table name (e.g. 'students').
        pk_column: Primary key column name (e.g. 'id').
    """
    trigger_name = f"trg_{table}_updated_at"
    return f"""
        DROP TRIGGER IF EXISTS {trigger_name};
        CREATE TRIGGER {trigger_name}
        AFTER UPDATE ON {table}
        FOR EACH ROW
        WHEN OLD.updated_at IS NEW.updated_at
        BEGIN
            UPDATE {table}
            SET updated_at = datetime('now', 'localtime')
            WHERE {pk_column} = NEW.{pk_column};
        END;
    """

# main.py

# Only pull the constants, not the imports/dunders.
QUERY_PREFIXES = ("TABLE_", "INDEX_")

tables = [
    v for k, v in vars(all_queries).items()
    if k.startswith(QUERY_PREFIXES) and isinstance(v, str)
]

# Triggers are built by a helper because each one differs only by
# table name and PK column. Drop + create so re-running init
# replaces stale definitions from earlier schema versions.
TRIGGERS = [
    make_updated_at_trigger("students",   "id"),
    make_updated_at_trigger("trainers",   "id"),
    make_updated_at_trigger("plans",      "id"),
    make_updated_at_trigger("payments",   "id"),
    make_updated_at_trigger("memberships", "id"),
    # NOTE: attendance and substitutions have no `updated_at` column.
    # Adding a trigger for them would fail at fire time with
    # "no such column: OLD.updated_at". If tracking is ever needed on
    # those tables, add the column to the schema first, then add the
    # trigger here.
]

#init_db(tables + TRIGGERS)
#init_db(TRIGGERS)