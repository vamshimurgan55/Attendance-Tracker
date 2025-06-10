import sqlite3
import os
from datetime import datetime, timedelta

# --- Configuration ---
# IMPORTANT: This path must match the DB_PATH in your app.py
DB_PATH = r'C:\temp_flask_db\attendance.db'

# --- Ensure database directory exists ---
# This will create the directory if it doesn't exist
db_directory = os.path.dirname(DB_PATH)
if db_directory and not os.path.exists(db_directory):
    os.makedirs(db_directory)

# --- Database Helper Functions ---
def get_db_connection():
    """Establishes a connection to the SQLite database."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Allows accessing columns by name
    return conn

def init_db():
    """Creates the employees and attendance tables if they don't exist."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id_text TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            department TEXT,
            job_title TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time_in TEXT NOT NULL,
            time_out TEXT,
            location TEXT NOT NULL,
            duration_minutes INTEGER,
            FOREIGN KEY (employee_id) REFERENCES employees (id)
        )
    ''')
    conn.commit()
    conn.close()

# --- Main Script to Insert Data ---
if __name__ == "__main__":
    print(f"Attempting to connect to database at: {DB_PATH}")
    init_db() # Ensure tables are created

    conn = get_db_connection()
    cursor = conn.cursor()

    # Clear existing data for a clean simulation
    print("Clearing existing data from employees and attendance tables...")
    cursor.execute("DELETE FROM attendance")
    cursor.execute("DELETE FROM employees")
    conn.commit()
    print("Existing data cleared.")

    # --- Sample Employee Data ---
    sample_employees = [
        ('E001', 'Alice Smith', 'Engineering', 'Java Developer'),
        ('E002', 'Bob Johnson', 'IT', 'Python Engineer'),
        ('E003', 'Carol White', 'HR', 'HR Manager'),
        ('E004', 'David Green', 'Engineering', 'Full Stack Developer'),
        ('E005', 'Eve Brown', 'Marketing', None)
    ]

    employee_ids_map = {} # To store internal DB ID for attendance records

    print("Inserting sample employee data...")
    for emp_id_text, name, dept, job_title in sample_employees:
        try:
            cursor.execute("INSERT INTO employees (employee_id_text, name, department, job_title) VALUES (?, ?, ?, ?)",
                           (emp_id_text, name, dept, job_title))
            employee_ids_map[emp_id_text] = cursor.lastrowid
            print(f"  Inserted employee: {name} (ID: {emp_id_text})")
        except sqlite3.IntegrityError:
            print(f"  Employee ID '{emp_id_text}' already exists (skipped insertion).")
            cursor.execute("SELECT id FROM employees WHERE employee_id_text = ?", (emp_id_text,))
            employee_ids_map[emp_id_text] = cursor.fetchone()[0]
    conn.commit()
    print("Employee data inserted.")

    # --- Sample Attendance Data for a specific date (e.g., June 4, 2025) ---
    # Using a fixed date for reproducible results
    today_date = datetime.now().strftime('%Y-%m-%d')
    yesterday_date_str = (datetime(2025, 6, 4) - timedelta(days=1)).strftime('%Y-%m-%d')

    sample_attendance = [
        # Alice Smith (E001): Marked IN at 09:00, Onsite (Still IN)
        (employee_ids_map['E001'], today_date, '09:00', None, 'Onsite', None),
        # Bob Johnson (E002): Marked IN at 08:30, Marked OUT at 17:00, Offsite (OUT for today)
        (employee_ids_map['E002'], today_date, '08:30', '17:00', 'Offsite', 8*60+30),
        # Carol White (E003): Marked IN at 09:15, Marked OUT at 17:30, Onsite (OUT for today)
        (employee_ids_map['E003'], today_date, '09:15', '17:30', 'Onsite', 8*60+15),
        # David Green (E004): Marked IN at 09:05, Offsite (Still IN)
        (employee_ids_map['E004'], today_date, '09:05', None, 'Offsite', None),
        # Alice Smith (E001): A record for a previous day (should not affect today's summary)
        (employee_ids_map['E001'], yesterday_date_str, '08:00', '16:00', 'Onsite', 8*60),
    ]

    print(f"Inserting sample attendance data for {today_date} and {yesterday_date_str}...")
    for emp_id, date, time_in, time_out, location, duration in sample_attendance:
        cursor.execute("INSERT INTO attendance (employee_id, date, time_in, time_out, location, duration_minutes) VALUES (?, ?, ?, ?, ?, ?)",
                       (emp_id, date, time_in, time_out, location, duration))
    conn.commit()
    print("Attendance data inserted.")

    conn.close()
    print("Database connection closed. Sample data insertion complete.")

    print("\nNow, if you run your Flask application, your admin dashboard should reflect this data!")   