
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
            except:
                print(query)
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

# main.py


# tables = [v for k, v in vars(all_queries).items() 
#           if k.startswith("TABLE_") and isinstance(v, str)]

# init_db(tables)
