from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import sqlite3
import os
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.secret_key = 'your_super_secret_key_here'

DB_PATH = r'C:\\temp_flask_db\\attendance.db'

if not os.path.exists(os.path.dirname(DB_PATH)):
    os.makedirs(os.path.dirname(DB_PATH))

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id_text TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            department TEXT,
            job_title TEXT
        );
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            time_in TEXT NOT NULL,
            time_out TEXT,
            location TEXT,
            FOREIGN KEY (employee_id) REFERENCES employees(id)
        );
    """)

    conn.commit()
    conn.close()

init_db()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'admin' not in session:
            flash("Please log in as admin to access this page.", "warning")
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Add this helper function to format time
def format_time_12hr(time_str):
    """Convert 24-hour time string (HH:MM:SS or HH:MM) to 12-hour format."""
    if not time_str:
        return 'N/A'
    try:
        # Try parsing with seconds first
        return datetime.strptime(time_str, "%H:%M:%S").strftime("%I:%M:%S %p")
    except ValueError:
        try:
            # If that fails, try parsing without seconds
            return datetime.strptime(time_str, "%H:%M").strftime("%I:%M %p")
        except ValueError:
            return time_str # Return as is if parsing fails, or handle error as needed

@app.before_request
def require_login():
    allowed_routes = ['login', 'static', 'mark_in', 'mark_out', 'index', 'get_attendance_status']
    if request.endpoint not in allowed_routes and not session.get('admin'):
        if request.endpoint != 'login':
            return redirect(url_for('login'))

@app.route('/get_attendance_status/<int:employee_id>')
def get_attendance_status(employee_id):
    conn = get_db_connection()
    current_date = datetime.now().strftime('%Y-%m-%d')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id FROM attendance WHERE employee_id = ? AND date = ? AND time_out IS NULL",
        (employee_id, current_date)
    )
    open_in_record = cursor.fetchone()
    if open_in_record:
        conn.close()
        return jsonify({'status': 'IN'})
    cursor.execute(
        "SELECT id FROM attendance WHERE employee_id = ? AND date = ? AND time_out IS NOT NULL",
        (employee_id, current_date)
    )
    completed_record = cursor.fetchone()
    if completed_record:
        conn.close()
        return jsonify({'status': 'OUT'})
    conn.close()
    return jsonify({'status': 'NONE'})

@app.route('/')
def index():
    conn = get_db_connection()
    employees = conn.execute('SELECT id, name FROM employees ORDER BY name ASC').fetchall()
    today_date = datetime.now().strftime('%Y-%m-%d')
    marked_in_today = conn.execute(f"""
        SELECT E.id, E.name
        FROM employees E
        JOIN attendance A ON E.id = A.employee_id
        WHERE A.date = '{today_date}' AND (A.time_out IS NULL OR A.time_out = '')
    """).fetchall()
    marked_in_ids = {emp['id'] for emp in marked_in_today}
    conn.close()
    return render_template('index.html', employees=employees, marked_in_ids=marked_in_ids)

@app.route('/mark_in', methods=['POST'])
def mark_in():
    employee_id = request.form['employee_id']
    location = request.form.get('location', 'Onsite')
    date = datetime.now().strftime('%Y-%m-%d')
    time_in = datetime.now().strftime('%H:%M:%S')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT * FROM attendance
        WHERE employee_id = ? AND date = ? AND (time_out IS NULL OR time_out = '')
    """, (employee_id, date))
    existing_record = cursor.fetchone()
    if existing_record:
        flash("Employee has already marked in today and not yet marked out.", "error")
    else:
        conn.execute("INSERT INTO attendance (employee_id, date, time_in, location) VALUES (?, ?, ?, ?)",
                     (employee_id, date, time_in, location))
        conn.commit()
        flash("Employee marked in successfully!", "success")
    conn.close()
    return redirect(url_for('index'))

@app.route('/mark_out', methods=['POST'])
def mark_out():
    employee_id = request.form['employee_id']
    date = datetime.now().strftime('%Y-%m-%d')
    time_out = datetime.now().strftime('%H:%M:%S')
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT id, time_in FROM attendance
        WHERE employee_id = ? AND date = ? AND (time_out IS NULL OR time_out = '')
        ORDER BY time_in DESC
        LIMIT 1
    """, (employee_id, date))
    record = cursor.fetchone()
    if record:
        conn.execute("UPDATE attendance SET time_out = ? WHERE id = ?", (time_out, record['id']))
        conn.commit()
        flash("Employee marked out successfully!", "success")
    else:
        flash("No active 'mark in' record found for this employee today.", "error")
    conn.close()
    return redirect(url_for('index'))

@app.route('/records')
@admin_required
def records():
    conn = get_db_connection()
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    employee_name_filter = request.args.get('employee_name_filter')

    query = """
        SELECT A.id, E.name, E.employee_id_text, A.date, A.time_in, A.time_out, A.location,
               STRFTIME('%s', A.time_out) - STRFTIME('%s', A.time_in) AS duration_seconds
        FROM attendance A
        JOIN employees E ON A.employee_id = E.id
        WHERE 1=1
    """
    params = []

    if start_date:
        query += " AND A.date >= ?"
        params.append(start_date)
    if end_date:
        query += " AND A.date <= ?"
        params.append(end_date)
    if employee_name_filter:
        query += " AND E.name LIKE ?"
        params.append('%' + employee_name_filter + '%')

    query += " ORDER BY A.date DESC, A.time_in DESC"

    attendance_records_raw = conn.execute(query, params).fetchall()
    
    # Format time_in and time_out for display
    attendance_records_formatted = []
    for record in attendance_records_raw:
        record_dict = dict(record) # Convert Row object to dict for modification
        record_dict['time_in_formatted'] = format_time_12hr(record['time_in'])
        record_dict['time_out_formatted'] = format_time_12hr(record['time_out'])
        attendance_records_formatted.append(record_dict)

    conn.close()
    return render_template('records.html',
                           attendance_records=attendance_records_formatted, # Pass the formatted records
                           start_date=start_date,
                           end_date=end_date,
                           employee_name_filter=employee_name_filter)

@app.route('/admin_dashboard')
@admin_required
def admin_dashboard():
    conn = get_db_connection()
    employees = conn.execute("SELECT id, employee_id_text, name, department, job_title FROM employees ORDER BY name ASC").fetchall()
    conn.close()
    return render_template('admin_dashboard.html', employees=employees)

# The original format_time_12hr function was placed incorrectly.
# It should be defined once, preferably at the top level or within a class,
# and then called where needed. I've moved it to the top.

@app.route('/dashboard')
@admin_required
def dashboard():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        today_date = datetime.now().strftime('%Y-%m-%d')
        cursor.execute("SELECT COUNT(*) FROM employees")
        total_employees = cursor.fetchone()[0] or 0
        cursor.execute("""
            SELECT COUNT(DISTINCT E.id)
            FROM employees E
            JOIN attendance A ON E.id = A.employee_id
            WHERE A.date = ? AND (A.time_out IS NULL OR A.time_out = '')
        """, (today_date,))
        employees_in_today = cursor.fetchone()[0] or 0
        cursor.execute("""
            SELECT COUNT(DISTINCT E.id)
            FROM employees E
            JOIN attendance A ON E.id = A.employee_id
            WHERE A.date = ? AND A.time_out IS NOT NULL AND A.time_out != ''
        """, (today_date,))
        employees_out_today = cursor.fetchone()[0] or 0
        employees_not_marked_today = total_employees - (employees_in_today + employees_out_today)
        if employees_not_marked_today < 0:
            employees_not_marked_today = 0
        cursor.execute("SELECT COUNT(*) FROM attendance")
        total_attendance_records = cursor.fetchone()[0] or 0
        cursor.execute("""
            SELECT COUNT(*)
            FROM attendance
            WHERE date = ? AND location = 'Onsite'
        """, (today_date,))
        onsite_count = cursor.fetchone()[0] or 0
        cursor.execute("""
            SELECT COUNT(*)
            FROM attendance
            WHERE date = ? AND location = 'Remote'
        """, (today_date,))
        offsite_count = cursor.fetchone()[0] or 0
        
        cursor.execute("""
            SELECT E.name, A.date, A.time_in, A.time_out, A.location
            FROM attendance A
            JOIN employees E ON A.employee_id = E.id
            ORDER BY A.date DESC, A.time_in DESC
            LIMIT 10
        """)
        recent_activities_raw = cursor.fetchall()
        
        # Format time for recent activities
        recent_activities = []
        for activity in recent_activities_raw:
            activity_dict = dict(activity)
            activity_dict['time_in'] = format_time_12hr(activity['time_in'])
            activity_dict['time_out'] = format_time_12hr(activity['time_out'])
            recent_activities.append(activity_dict)

        return render_template('dashboard.html',
                            current_date=today_date,
                            total_employees=total_employees,
                            employees_in_today=employees_in_today,
                            employees_out_today=employees_out_today,
                            employees_not_marked_today=employees_not_marked_today,
                            total_attendance_records=total_attendance_records,
                            onsite_count=onsite_count,
                            offsite_count=offsite_count,
                            recent_activities=recent_activities)

    except sqlite3.Error as e:
        print(f"SQLite error: {e}")
        flash(f"Database error occurred: {e}", "error")
        return redirect(url_for('admin_dashboard'))
    except Exception as e:
        print(f"General error: {e}")
        flash(f"An error occurred: {e}", "error")
        return redirect(url_for('admin_dashboard'))
    finally:
        if 'conn' in locals():
            conn.close()

@app.route('/add_employee', methods=['GET', 'POST'])
@admin_required
def add_employee():
    conn = get_db_connection()
    if request.method == 'POST':
        employee_id_text = request.form['employee_id_text'].strip()
        name = request.form['name'].strip()
        department = request.form.get('department', '').strip()
        job_title = request.form.get('job_title', '').strip()
        if not employee_id_text or not name:
            flash("Employee ID and Name are required fields.", "error")
            conn.close()
            return redirect(url_for('add_employee'))
        try:
            conn.execute("INSERT INTO employees (employee_id_text, name, department, job_title) VALUES (?, ?, ?, ?)",
                         (employee_id_text, name, department, job_title))
            conn.commit()
            flash(f"Employee '{name}' (ID: {employee_id_text}) added successfully!", "success")
            return redirect(url_for('add_employee'))
        except sqlite3.IntegrityError:
            flash(f"Error: Employee ID '{employee_id_text}' already exists. Please use a unique ID.", "error")
            conn.rollback()
        except Exception as e:
            flash(f"An error occurred: {e}", "error")
            conn.rollback()
    employees = conn.execute("SELECT id, employee_id_text, name, department, job_title FROM employees ORDER BY name ASC").fetchall()
    conn.close()
    return render_template('add_employee.html', employees=employees)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user = request.form['username']
        pw = request.form['password']
        if user == 'admin' and pw == 'admin123':
            session['admin'] = True
            flash("Logged in as Admin!", "success")
            return redirect(url_for('dashboard'))
        else:
            flash("Invalid credentials", "error")
            return render_template('login.html'), 401
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('admin', None)
    flash("Logged out successfully.", "info")
    return redirect(url_for('index'))

@app.route('/export_csv')
@admin_required
def export_csv():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT E.employee_id_text, E.name, A.date, A.time_in, A.time_out, A.location
        FROM attendance A
        JOIN employees E ON A.employee_id = E.id
        ORDER BY A.date DESC, A.time_in DESC
    """)
    records = cursor.fetchall()
    conn.close()

    csv_data = "Employee ID,Employee Name,Date,Time In,Time Out,Location\n"
    for record in records:
        time_in_formatted = format_time_12hr(record['time_in']) # Format for CSV
        time_out_formatted = format_time_12hr(record['time_out']) # Format for CSV
        csv_data += f"{record['employee_id_text']},{record['name']},{record['date']},{time_in_formatted},{time_out_formatted},{record['location']}\n"
    
    response = app.make_response(csv_data)
    response.headers["Content-Disposition"] = "attachment; filename=attendance_records.csv"
    response.headers["Content-type"] = "text/csv"
    return response

@app.route('/employee_report/<int:employee_id>')
@admin_required
def employee_report(employee_id):
    conn = get_db_connection()
    employee = conn.execute("SELECT id, employee_id_text, name, department, job_title FROM employees WHERE id = ?", (employee_id,)).fetchone()
    if not employee:
        flash("Employee not found.", "error")
        conn.close()
        return redirect(url_for('dashboard'))

    attendance_records = []
    cursor = conn.cursor()
    cursor.execute(f"""
        SELECT date, time_in, time_out, location
        FROM attendance
        WHERE employee_id = ?
        ORDER BY date DESC, time_in DESC
    """, (employee_id,))
    
    raw_records = cursor.fetchall()

    for record in raw_records:
        duration_minutes = None
        if record['time_in'] and record['time_out']:
            try:
                time_in_dt = datetime.strptime(record['time_in'], '%H:%M:%S')
                time_out_dt = datetime.strptime(record['time_out'], '%H:%M:%S')
                if time_out_dt < time_in_dt:
                    time_out_dt += timedelta(days=1)
                duration = time_out_dt - time_in_dt
                duration_minutes = round(duration.total_seconds() / 60)
            except ValueError:
                duration_minutes = None
        
        # Append record with formatted time
        attendance_records.append({
            'date': record['date'],
            'time_in': format_time_12hr(record['time_in']), # Format here
            'time_out': format_time_12hr(record['time_out']), # Format here
            'location': record['location'],
            'duration_minutes': duration_minutes
        })

    conn.close()
    return render_template('employee_report.html', employee=employee, attendance_records=attendance_records)

if __name__ == '__main__':
    app.run(debug=True)