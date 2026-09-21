from database_ctl import get_connection

def test_insert():
    #init_db()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO students (last_name, first_name, phone, group_type) VALUES (?, ?, ?, ?)",
            ("Fury", "Tyson", "+123456789", "adult")
        )
        conn.commit()
        print("✅ Test student inserted!")

if __name__ == "__main__":
    test_insert()