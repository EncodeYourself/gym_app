
import sqlite3
from pathlib import Path
import polars as pl
import app.database.init_queries as all_queries
DB_PATH = Path(__file__).parent.parent / 'data' / 'business.db'

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")   # ← is this here?
    return conn

def load_table_data(db_path, table_name):
    conn = sqlite3.connect(db_path)
    query = f'SELECT * FROM {table_name}'
    df = pl.read_database(query, conn)
    conn.close()
    return df

# --- MASTER INIT FUNCTION ---
def init_db(queries):
    """Create all tables if they don't exist"""
    
    with get_connection() as conn:
        
        for query in queries:
            try:
                conn.execute(query)
            except Exception as e:
                print(query, e)
                raise NameError
    
        conn.commit()
        print("✅ Database initialized with all tables and indexes!")
        
            

# --- OPTIONAL: DROP ALL TABLES (for testing) ---
def reset_db():
    """WARNING: Deletes all data - only for development!"""
    tables = ['notes', 'membership_holds', 'payments', 'check_ins', 
              'class_schedule', 'memberships', 'students']
    
    with get_connection() as conn:
        for table in tables:
            conn.execute(f"DROP TABLE IF EXISTS {table};")
        conn.commit()
        print("⚠️  All tables dropped!")

def make_updated_at_trigger(table: str, pk_column: str) -> str:
    """
    Return the CREATE TRIGGER statement that keeps `updated_at`
    current on UPDATE for a table.

    Args:
        table: Table name (e.g. 'students').
        pk_column: Primary key column name (e.g. 'id',
            or 'membership_id' for memberships).
    """
    trigger_name = f"trg_{table}_updated_at"
    return f"""
        CREATE TRIGGER IF NOT EXISTS {trigger_name}
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


#Only pull the constants, not the imports/dunders
QUERY_PREFIXES = ("TABLE_", "INDEX_")

tables = [
    v for k, v in vars(all_queries).items()
    if k.startswith(QUERY_PREFIXES) and isinstance(v, str)
]
TRIGGERS = [
    make_updated_at_trigger("students", "id"),
    make_updated_at_trigger("trainers", "id"),
    make_updated_at_trigger("plans", "id"),
    make_updated_at_trigger("payments", "id"),
    make_updated_at_trigger("substitutions", "id"),
    make_updated_at_trigger("attendance", "id"),
    make_updated_at_trigger("memberships", "id"),
]
#init_db(tables)
#init_db(TRIGGERS)
