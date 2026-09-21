import sqlite3
from pathlib import Path

from app.database.database_ctl import init_db, reset_db
DB_PATH = Path(__file__).parent.parent / 'data' / 'business.db'

def get_all_tables():
    """Get all table names from the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Query sqlite_master for all tables
    cursor.execute("""
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
    """)
    
    tables = [row[0] for row in cursor.fetchall()]
    conn.close()
    return tables

def command(query=None):
    """Get all table names from the database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if not query:    
        cursor.execute('''
        SELECT * FROM classes
        ''')
    else: 
        cursor.execute(query)
    output = cursor.fetchall()
    conn.close()
    return output

x = get_all_tables()
print(x)
st.markdown("""
    <style>
        /* Remove Streamlit's default max-width constraints */
        .main .block-container {
            max-width: 100% !important;
            padding-left: 1rem !important;
            padding-right: 1rem !important;
        }
        
        /* Target the specific Streamlit app container */
        section[data-testid="stSidebar"] + div,
        section[data-testid="stSidebar"] + div > div,
        section[data-testid="stSidebar"] + div > div > div {
            max-width: 100% !important;
        }
        
        /* Make dataframe container full width */
        [data-testid="stDataFrame"] {
            width: 100% !important;
            max-width: 100% !important;
        }
        
        /* Make the dataframe's internal container full width */
        [data-testid="stDataFrame"] > div {
            width: 100% !important;
            max-width: 100% !important;
        }
        
        /* Target the table wrapper */
        .stDataFrame div[data-testid="stDataFrameResizable"] {
            width: 100% !important;
            max-width: 100% !important;
        }
        
        /* Make the table itself full width */
        .stDataFrame table {
            width: 100% !important;
            table-layout: auto !important;
        }
        
        /* Cell styling */
        .stDataFrame td {
            white-space: pre-wrap !important;
            word-break: break-word !important;
            line-height: 1.8 !important;
            padding: 10px 8px !important;
            vertical-align: top !important;
        }
        
        .stDataFrame td div {
            white-space: pre-wrap !important;
            line-height: 1.8 !important;
        }
        
        .stDataFrame td:first-child {
            font-weight: bold !important;
            text-align: center !important;
            width: 80px !important;
        }
        
        /* Force all parent containers to full width */
        .stApp {
            max-width: 100% !important;
        }
        
        .stApp > div {
            max-width: 100% !important;
        }
        
        .stApp > div > div {
            max-width: 100% !important;
        }
    </style>
""", unsafe_allow_html=True)