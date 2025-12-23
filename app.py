import sqlite3
import re
from flask import Flask, render_template, request, url_for, redirect, session, jsonify
from flask import flash, get_flashed_messages
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import date
import os
from werkzeug.utils import secure_filename
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from dotenv import load_dotenv
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

# Load environment variables from .env file
load_dotenv()

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "campuscare_secret_key_2025_arul_subash_06")

# Configure upload folder
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
MAX_FILE_SIZE = 16 * 1024 * 1024  # 16MB max file size

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Email configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = os.environ.get('MAIL_USERNAME', 'your_email@gmail.com')
app.config['MAIL_PASSWORD'] = os.environ.get('MAIL_PASSWORD', 'your_app_password_here')

# Create upload folder if it doesn't exist
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Database setup
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row  # This enables name-based access to columns
    return conn

# Initialize database
def init_db():
    if not os.path.exists('database.db'):
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute('''
            CREATE TABLE users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE,
                password TEXT NOT NULL,
                role TEXT NOT NULL,
                department TEXT,
                status TEXT DEFAULT 'Available'
            )
        ''')
        
        # Create requests table
        cursor.execute('''
            CREATE TABLE requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                studentID INTEGER NOT NULL,
                title TEXT NOT NULL,
                location TEXT NOT NULL,
                status TEXT NOT NULL,
                priority TEXT NOT NULL,
                description TEXT NOT NULL,
                date TEXT NOT NULL,
                workerID INTEGER,
                notes TEXT,
                worker_notes TEXT,
                image_path TEXT,
                worker_image_path TEXT,
                department TEXT,
                FOREIGN KEY (studentID) REFERENCES users (id),
                FOREIGN KEY (workerID) REFERENCES users (id)
            )
        ''')
        
        # Create lost_items table
        cursor.execute('''
            CREATE TABLE lost_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                studentID INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                description TEXT NOT NULL,
                location_found TEXT NOT NULL,
                date_found TEXT NOT NULL,
                image_path TEXT,
                status TEXT DEFAULT 'Unclaimed',
                claimed_by INTEGER,
                date_claimed TEXT,
                contact_info TEXT,
                FOREIGN KEY (studentID) REFERENCES users (id),
                FOREIGN KEY (claimed_by) REFERENCES users (id)
            )
        ''')
        
        # Create email_notifications table
        cursor.execute('''
            CREATE TABLE email_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER,
                recipient_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                sent_date TEXT NOT NULL,
                status TEXT DEFAULT 'Sent',
                FOREIGN KEY (request_id) REFERENCES requests (id),
                FOREIGN KEY (recipient_id) REFERENCES users (id)
            )
        ''')
        
        # Create default admin account with properly hashed password
        hashed_password = generate_password_hash('admin123')
        cursor.execute(
            "INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?)",
            ('Admin', 'admin@campuscare.com', hashed_password, 'Admin')
        )
        
        conn.commit()
        conn.close()

# Database migration for existing databases
def migrate_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Check if columns already exist
    cursor.execute("PRAGMA table_info(users)")
    users_columns = [col[1] for col in cursor.fetchall()]
    
    cursor.execute("PRAGMA table_info(requests)")
    requests_columns = [col[1] for col in cursor.fetchall()]
    
    cursor.execute("PRAGMA table_info(lost_items)")
    lost_items_columns = [col[1] for col in cursor.fetchall()]
    
    # Add department column to users table if it doesn't exist
    if 'department' not in users_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN department TEXT")
    
    # Add status column to users table if it doesn't exist
    if 'status' not in users_columns:
        cursor.execute("ALTER TABLE users ADD COLUMN status TEXT DEFAULT 'Available'")
    
    # Add image_path and department columns to requests table if they don't exist
    if 'image_path' not in requests_columns:
        cursor.execute("ALTER TABLE requests ADD COLUMN image_path TEXT")
    
    if 'worker_image_path' not in requests_columns:
        cursor.execute("ALTER TABLE requests ADD COLUMN worker_image_path TEXT")
    
    if 'department' not in requests_columns:
        cursor.execute("ALTER TABLE requests ADD COLUMN department TEXT")
    
    # Add contact_info column to lost_items table if it doesn't exist
    if 'contact_info' not in lost_items_columns:
        cursor.execute("ALTER TABLE lost_items ADD COLUMN contact_info TEXT")
    
    # Create lost_items table if it doesn't exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='lost_items';")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE lost_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                studentID INTEGER NOT NULL,
                item_name TEXT NOT NULL,
                description TEXT NOT NULL,
                location_found TEXT NOT NULL,
                date_found TEXT NOT NULL,
                image_path TEXT,
                status TEXT DEFAULT 'Unclaimed',
                claimed_by INTEGER,
                date_claimed TEXT,
                contact_info TEXT,
                FOREIGN KEY (studentID) REFERENCES users (id),
                FOREIGN KEY (claimed_by) REFERENCES users (id)
            )
        ''')
    
    # Create email_notifications table if it doesn't exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='email_notifications';")
    if not cursor.fetchone():
        cursor.execute('''
            CREATE TABLE email_notifications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id INTEGER,
                recipient_id INTEGER NOT NULL,
                subject TEXT NOT NULL,
                message TEXT NOT NULL,
                sent_date TEXT NOT NULL,
                status TEXT DEFAULT 'Sent',
                FOREIGN KEY (request_id) REFERENCES requests (id),
                FOREIGN KEY (recipient_id) REFERENCES users (id)
            )
        ''')
    
    conn.commit()
    conn.close()

# Helper function to execute queries
def execute_query(query, params=(), fetch=False, fetchall=False):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, params)
    
    if fetch:
        result = cursor.fetchone()
    elif fetchall:
        result = cursor.fetchall()
    else:
        result = None
    
    conn.commit()
    conn.close()
    
    return result

# Convert Row objects to dictionaries for JSON serialization
def row_to_dict(row):
    if row is None:
        return None
    return dict(row)

def rows_to_dict(rows):
    if rows is None:
        return None
    return [dict(row) for row in rows]

# Check database schema
def check_db_schema():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Check users table structure
    cursor.execute("PRAGMA table_info(users)")
    users_columns = cursor.fetchall()
    print("Users table columns:")
    for col in users_columns:
        print(f"  {col['name']} - {col['type']}")
    
    # Check requests table structure
    cursor.execute("PRAGMA table_info(requests)")
    requests_columns = cursor.fetchall()
    print("Requests table columns:")
    for col in requests_columns:
        print(f"  {col['name']} - {col['type']}")
    
    conn.close()

# Simple password check for legacy passwords
def check_legacy_password(hashed_password, plain_password):
    """Check if plain password matches legacy hashed password"""
    return hashed_password == plain_password

# Email function
def send_email(to_email, subject, message, attachment_path=None):
    """Send email notification with optional attachment"""
    try:
        # Check if email credentials are configured
        if app.config['MAIL_USERNAME'] == 'your_email@gmail.com' or app.config['MAIL_PASSWORD'] == 'your_app_password_here':
            print("⚠️ Email credentials not configured. Using default values.")
            print("ℹ️ Please set MAIL_USERNAME and MAIL_PASSWORD environment variables")
            return False
            
        print(f"📧 Attempting to send email to: {to_email}")
        print(f"📋 Subject: {subject}")
        
        msg = MIMEMultipart()
        msg['From'] = app.config['MAIL_USERNAME']
        msg['To'] = to_email
        msg['Subject'] = subject
        
        msg.attach(MIMEText(message, 'html'))
        
        # Add attachment if provided
        if attachment_path and os.path.exists(attachment_path):
            with open(attachment_path, 'rb') as f:
                attachment = MIMEApplication(f.read(), _subtype='octet-stream')
                attachment.add_header('Content-Disposition', 'attachment', 
                                     filename=os.path.basename(attachment_path))
                msg.attach(attachment)
            print(f"📎 Attachment added: {attachment_path}")
        
        server = smtplib.SMTP(app.config['MAIL_SERVER'], app.config['MAIL_PORT'])
        server.ehlo()  # Identify yourself to the server
        server.starttls()  # Secure the connection
        server.ehlo()  # Re-identify yourself after TLS
        server.login(app.config['MAIL_USERNAME'], app.config['MAIL_PASSWORD'])
        server.send_message(msg)
        server.quit()
        
        print(f" Email sent successfully to {to_email}")
        return True
    except Exception as e:
        print(f" Error sending email: {e}")
        import traceback
        traceback.print_exc()
        return False

def send_status_update_email(request_id, status, worker_notes=None, worker_image_path=None):
    """Send status update email for a specific request to student and worker"""
    # Get request details with student and worker information
    request_data = execute_query("""
        SELECT requests.*, 
               students.username as student_name, students.email as student_email,
               workers.username as worker_name, workers.email as worker_email
        FROM requests 
        LEFT JOIN users as students ON requests.studentID = students.id 
        LEFT JOIN users as workers ON requests.workerID = workers.id 
        WHERE requests.id = ?;
    """, [request_id], fetch=True)
    
    if not request_data:
        print(f"Request {request_id} not found")
        return False
    
    # Prepare email content based on status
    if status == "In Progress":
        subject = f"Request Update: {request_data['title']} - In Progress"
        email_content = f"""
        <h3>Your Service Request is Now In Progress</h3>
        <p>Your campus service request has been assigned and is now being worked on:</p>
        <p><strong>Request ID:</strong> {request_data['id']}</p>
        <p><strong>Title:</strong> {request_data['title']}</p>
        <p><strong>Priority:</strong> {request_data['priority'].capitalize()}</p>
        <p><strong>Location:</strong> {request_data['location']}</p>
        <p><strong>Assigned Worker:</strong> {request_data['worker_name'] or 'Not assigned yet'}</p>
        """
        
        if worker_notes:
            email_content += f"<p><strong>Worker Notes:</strong> {worker_notes}</p>"
            
        email_content += """
        <br>
        <p>We'll keep you updated on the progress. Thank you for your patience.</p>
        <p>Login to CampusCare for more details: <a href="/">CampusCare Portal</a></p>
        """
        
    elif status == "Completed":
        subject = f"Request Completed: {request_data['title']}"
        email_content = f"""
        <h3>Your Service Request Has Been Completed</h3>
        <p>We're pleased to inform you that your campus service request has been completed:</p>
        <p><strong>Request ID:</strong> {request_data['id']}</p>
        <p><strong>Title:</strong> {request_data['title']}</p>
        <p><strong>Priority:</strong> {request_data['priority'].capitalize()}</p>
        <p><strong>Location:</strong> {request_data['location']}</p>
        <p><strong>Completed by:</strong> {request_data['worker_name']}</p>
        """
        
        if worker_notes:
            email_content += f"<p><strong>Completion Notes:</strong> {worker_notes}</p>"
        
        if worker_image_path:
            email_content += f"<p><strong>Work Evidence:</strong> An image has been attached showing the completed work.</p>"
            
        email_content += """
        <br>
        <p>If you have any concerns about the work performed, please contact campus maintenance.</p>
        <p>Login to CampusCare for more details: <a href="/">CampusCare Portal</a></p>
        """
        
    else:
        # For other status changes (like back to Pending)
        subject = f"Request Status Update: {request_data['title']}"
        email_content = f"""
        <h3>Request Status Update</h3>
        <p>The status of your service request has been updated:</p>
        <p><strong>Request ID:</strong> {request_data['id']}</p>
        <p><strong>Title:</strong> {request_data['title']}</p>
        <p><strong>New Status:</strong> {status}</p>
        <p><strong>Priority:</strong> {request_data['priority'].capitalize()}</p>
        <p><strong>Location:</strong> {request_data['location']}</p>
        """
        
        if worker_notes:
            email_content += f"<p><strong>Notes:</strong> {worker_notes}</p>"
            
        email_content += """
        <br>
        <p>Login to CampusCare for more details: <a href="/">CampusCare Portal</a></p>
        """
    
    # Store notification in database
    today = date.today()
    execute_query(
        "INSERT INTO email_notifications (request_id, recipient_id, subject, message, sent_date) VALUES (?, ?, ?, ?, ?);",
        [request_id, request_data['studentID'], subject, email_content, today.strftime("%Y-%m-%d")]
    )
    
    # Send email to student with optional attachment
    attachment_path = None
    if worker_image_path:
        attachment_path = os.path.join(app.config['UPLOAD_FOLDER'], worker_image_path)
    
    student_email_sent = send_email(request_data['student_email'], subject, email_content, attachment_path)
    
    # Send notification to worker if assigned
    worker_email_sent = False
    if request_data['workerID'] and request_data['worker_email']:
        worker_subject = f"Task Assignment: {request_data['title']}"
        
        if status == "In Progress":
            worker_message = f"""
            <h3>New Task Assigned To You</h3>
            <p>You have been assigned a new service request:</p>
            <p><strong>Request ID:</strong> {request_data['id']}</p>
            <p><strong>Title:</strong> {request_data['title']}</p>
            <p><strong>Student:</strong> {request_data['student_name']}</p>
            <p><strong>Location:</strong> {request_data['location']}</p>
            <p><strong>Priority:</strong> {request_data['priority'].capitalize()}</p>
            <p><strong>Description:</strong> {request_data['description']}</p>
            """
            
            if request_data['notes']:
                worker_message += f"<p><strong>Admin Notes:</strong> {request_data['notes']}</p>"
                
            worker_message += """
            <br>
            <p>Please login to CampusCare to start working on this request.</p>
            <p><a href="/worker">Access Worker Dashboard</a></p>
            """
            
        elif status == "Completed":
            worker_message = f"""
            <h3>Task Completed Successfully</h3>
            <p>You have successfully completed the following service request:</p>
            <p><strong>Request ID:</strong> {request_data['id']}</p>
            <p><strong>Title:</strong> {request_data['title']}</p>
            <p><strong>Student:</strong> {request_data['student_name']}</p>
            <p><strong>Location:</strong> {request_data['location']}</p>
            """
            
            if worker_notes:
                worker_message += f"<p><strong>Your Notes:</strong> {worker_notes}</p>"
            
            if worker_image_path:
                worker_message += f"<p><strong>Work Evidence:</strong> You attached an image as evidence of completed work.</p>"
                
            worker_message += """
            <br>
            <p>The student has been notified of the completion.</p>
            <p>Thank you for your service!</p>
            """
            
        else:
            worker_message = f"""
            <h3>Task Status Updated</h3>
            <p>The status of your assigned task has been updated:</p>
            <p><strong>Request ID:</strong> {request_data['id']}</p>
            <p><strong>Title:</strong> {request_data['title']}</p>
            <p><strong>Student:</strong> {request_data['student_name']}</p>
            <p><strong>New Status:</strong> {status}</p>
            """
            
            if worker_notes:
                worker_message += f"<p><strong>Notes:</strong> {worker_notes}</p>"
                
            worker_message += """
            <br>
            <p><a href="/worker">View Task Details</a></p>
            """
        
        # Store worker notification in database
        execute_query(
            "INSERT INTO email_notifications (request_id, recipient_id, subject, message, sent_date) VALUES (?, ?, ?, ?, ?);",
            [request_id, request_data['workerID'], worker_subject, worker_message, today.strftime("%Y-%m-%d")]
        )
        
        # Send email to worker
        worker_email_sent = send_email(request_data['worker_email'], worker_subject, worker_message)
    
    # Also log to console for debugging
    print(f"\n📧 EMAIL NOTIFICATIONS")
    print(f"To Student: {request_data['student_email']} ({'SENT' if student_email_sent else 'FAILED'})")
    if request_data['workerID']:
        print(f"To Worker: {request_data['worker_email']} ({'SENT' if worker_email_sent else 'FAILED'})")
    print(f"Subject: {subject}")
    print(f"Request: {request_data['title']} (ID: {request_data['id']})")
    print(f"Status: {status}")
    if worker_image_path:
        print(f"Attachment: {worker_image_path}")
    print("---\n")
    
    return student_email_sent

def check_for_pending_requests():
    """
    Checks the database for pending requests and sends an email to the admin.
    """
    with app.app_context():
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Get the admin's username and email from the database
        cursor.execute("SELECT username, email FROM users WHERE role = 'Admin' LIMIT 1;")
        admin_data = cursor.fetchone()
        
        # Count the number of pending requests
        cursor.execute("SELECT COUNT(*) FROM requests WHERE status = 'Pending';")
        pending_count = cursor.fetchone()[0]
        
        conn.close()

        if pending_count > 0 and admin_data:
            admin_name = admin_data['username']
            admin_email = admin_data['email']
            
            # Use HTML formatting for a better-looking email
            subject = f"Action Required: {pending_count} New Pending Requests"
            html_message = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{
                        font-family: Arial, sans-serif;
                        color: #333;
                        line-height: 1.6;
                    }}
                    .container {{
                        max-width: 600px;
                        margin: 20px auto;
                        padding: 20px;
                        border: 1px solid #ddd;
                        border-radius: 8px;
                        background-color: #f9f9f9;
                    }}
                    .header {{
                        color: #1a237e;
                        font-size: 24px;
                        border-bottom: 2px solid #1a237e;
                        padding-bottom: 10px;
                        margin-bottom: 20px;
                    }}
                    .highlight {{
                        font-size: 20px;
                        color: #e65100;
                        font-weight: bold;
                    }}
                    .link-btn {{
                        display: inline-block;
                        padding: 10px 20px;
                        margin-top: 20px;
                        background-color: #1a237e;
                        color: #ffffff;
                        text-decoration: none;
                        border-radius: 5px;
                    }}
                </style>
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        Action Required: New Pending Service Requests
                    </div>
                    <p>Hello {admin_name},</p>
                    <p>There are currently <span class="highlight">{pending_count}</span> service requests with a 'Pending' status that require your attention.</p>
                    <p>Please log in to the CampusCare Admin Dashboard to review and assign these tasks to a worker.</p>
                    <a href="http://localhost:5000/admin" class="link-btn">Login to CampusCare Portal</a>
                </div>
            </body>
            </html>
            """
            
            # Send the email with HTML content
            print(f"Found {pending_count} pending requests. Sending email to admin.")
            send_email(admin_email, subject, html_message)
        else:
            print("No pending requests found. No email sent.")

# login
@app.route("/", methods=["GET","POST"])
def login():
    if request.method == "POST":
        studentID = request.form.get("studentID")
        studentPass = request.form.get("studentPass")
        username = request.form.get("username")
        mailID = request.form.get("mailID")
        Pass = request.form.get("pass")
        conform = request.form.get("conformPass")
        adminID = request.form.get("adminID")
        adminPass = request.form.get("adminPass")
        workerID = request.form.get("workerID")
        workerPass = request.form.get("workerPass")

        # Admin login
        if adminID and adminPass:
            user = execute_query("SELECT * FROM users WHERE email = ? AND role = 'Admin';", [adminID], fetch=True)
            if user:
                try:
                    if check_password_hash(user["password"], adminPass):
                        session["username"] = user["username"]
                        session["user_id"] = user["id"]
                        session["role"] = user["role"]
                        return redirect("/admin", )
                    else:
                        flash("Incorrect Password!", "danger")
                except ValueError:
                    # Handle legacy password format
                    if check_legacy_password(user["password"], adminPass):
                        # Rehash with current method
                        hashed = generate_password_hash(adminPass)
                        execute_query("UPDATE users SET password = ? WHERE id = ?;", [hashed, user["id"]])
                        session["username"] = user["username"]
                        session["user_id"] = user["id"]
                        session["role"] = user["role"]
                        return redirect("/admin")
                    else:
                        flash("Incorrect Password!", "danger")
            else:
                flash("Admin Account Not Found!", "danger")
            return render_template("index.html")

        # student login
        if studentID and studentPass:
            user = execute_query("SELECT * FROM users WHERE email = ? AND role = 'Student';", [studentID], fetch=True)
            if user:
                try:
                    if check_password_hash(user["password"], studentPass):
                        session["username"] = user["username"]
                        session["user_id"] = user["id"]
                        session["role"] = user["role"]
                        return redirect("/student")
                    else:
                        flash("Incorrect Password!", "danger")
                except ValueError:
                    # Handle legacy password format
                    if check_legacy_password(user["password"], studentPass):
                        # Rehash with current method
                        hashed = generate_password_hash(studentPass)
                        execute_query("UPDATE users SET password = ? WHERE id = ?;", [hashed, user["id"]])
                        session["username"] = user["username"]
                        session["user_id"] = user["id"]
                        session["role"] = user["role"]
                        return redirect("/student")
                    else:
                        flash("Incorrect Password!", "danger")
            else:
                flash("Student Account Not Found!", "danger")
            return render_template("index.html")

        # student registration
        if username and mailID and Pass and conform:
            uservalidation = execute_query("SELECT email FROM users WHERE email = ?;", [mailID], fetch=True)
            if uservalidation:
                flash("Student Already Exist!", "danger")
                return render_template("index.html")
            elif Pass != conform:
                flash("Conform Password Doesn't Match!", "danger")
                return render_template("index.html")
            else:
                hashPass = generate_password_hash(Pass)
                execute_query(
                    "INSERT INTO users (username, email, password, role) VALUES (?, ?, ?, ?);", 
                    [username, mailID, hashPass, "Student"]
                )
                flash("Registration successful! Please login.", "success")
                return render_template("index.html")
                
        # worker login
        if workerID and workerPass:
            user = execute_query("SELECT * FROM users WHERE email = ? AND role = 'Worker';", [workerID], fetch=True)
            if user:
                try:
                    if check_password_hash(user["password"], workerPass):
                        session["username"] = user["username"]
                        session["user_id"] = user["id"]
                        session["role"] = user["role"]
                        return redirect("/worker")
                    else:
                        flash("Incorrect Password!", "danger")
                except ValueError:
                    # Handle legacy password format
                    if check_legacy_password(user["password"], workerPass):
                        # Rehash with current method
                        hashed = generate_password_hash(workerPass)
                        execute_query("UPDATE users SET password = ? WHERE id = ?;", [hashed, user["id"]])
                        session["username"] = user["username"]
                        session["user_id"] = user["id"]
                        session["role"] = user["role"]
                        return redirect("/worker")
                    else:
                        flash("Incorrect Password!", "danger")
            else:
                flash("Worker Account Not Found!", "danger")
            return render_template("index.html")

    return render_template("index.html")

# Student forgot password route
@app.route("/forgot-password/student", methods=["POST"])
def forgot_password_student():
    return handle_forgot_password(request, "Student")

# Admin forgot password route
@app.route("/forgot-password/admin", methods=["POST"])
def forgot_password_admin():
    return handle_forgot_password(request, "Admin")

# Worker forgot password route
@app.route("/forgot-password/worker", methods=["POST"])
def forgot_password_worker():
    return handle_forgot_password(request, "Worker")

# Helper function for forgot password
def handle_forgot_password(request, role):
    email = request.form.get("email")
    new_password = request.form.get("new_password")
    confirm_password = request.form.get("confirm_password")
    
    if not email or not new_password or not confirm_password:
        flash("Please fill in all fields.", "danger")
        return redirect("/")
    
    if new_password != confirm_password:
        flash("Passwords do not match.", "danger")
        return redirect("/")
    
    # Check if email exists for the specific role
    user = execute_query("SELECT * FROM users WHERE email = ? AND role = ?;", [email, role], fetch=True)
    
    if user:
        # Update password directly in users table
        hashed_password = generate_password_hash(new_password)
        execute_query(
            "UPDATE users SET password = ? WHERE email = ? AND role = ?;",
            [hashed_password, email, role]
        )
        
        flash(f"Password reset successfully for {role} account. You can now login with your new password.", "success")
    else:
        flash(f"No {role.lower()} account found with that email address.", "danger")
    
    return redirect("/")

# student page
@app.route("/student", methods=["GET", "POST"])
def student():
    if 'user_id' not in session or session.get('role') != 'Student':
        flash("Access denied. Please login as a student.", "danger")
        return redirect("/")
    
    if request.method == "POST":
        title = request.form.get("title")
        location = request.form.get("location")
        priority = request.form.get("priority")
        description = request.form.get("description")
        studentID = session["user_id"]
        today = date.today()
        
        # Handle file upload - FIXED: Check if file exists and is valid
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            # Check if file is selected and has a filename
            if file and file.filename != '':
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Create unique filename to avoid conflicts
                    unique_filename = f"{studentID}_{int(time.time())}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                    image_path = unique_filename
                else:
                    flash("Invalid file type. Please upload PNG, JPG, JPEG, or GIF images.", "danger")
                    return redirect("/student")

        if title and location and priority and description:
            execute_query(
                "INSERT INTO requests (studentID, title, location, status, priority, description, date, image_path) VALUES (?, ?, ?, ?, ?, ?, ?, ?);", 
                [studentID, title, location, "Pending", priority, description, today.strftime("%Y-%m-%d"), image_path]
            )
            flash("Request submitted successfully!", "success")
    
    studentID = session["user_id"]
    # Updated query to show new requests first
    datas = execute_query("SELECT * FROM requests WHERE studentID = ? ORDER BY date DESC;", [studentID], fetchall=True)
    
    # Convert Row objects to dictionaries for JSON serialization
    datas_dict = rows_to_dict(datas)
    total_requests = len(datas_dict)
    pending_count = sum(1 for r in datas_dict if r["status"] == "Pending")
    in_progress_count = sum(1 for r in datas_dict if r["status"] == "In Progress")
    resolved_count = sum(1 for r in datas_dict if r["status"] == "Completed")
    
    return render_template("student.html", 
                           name=session["username"], 
                           requests=datas_dict, 
                           total_requests=total_requests, 
                           pending_count=pending_count,
                           in_progress_count=in_progress_count,
                           resolved_count=resolved_count)

# Lost & Found page
@app.route("/lost-found", methods=["GET", "POST"])
def lost_found():
    if 'user_id' not in session or session.get('role') != 'Student':
        flash("Access denied. Please login as a student.", "danger")
        return redirect("/")
    
    if request.method == "POST":
        item_name = request.form.get("item_name")
        description = request.form.get("description")
        location_found = request.form.get("location_found")
        contact_info = request.form.get("contact_info")
        studentID = session["user_id"]
        today = date.today()
        
        # Handle file upload
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename != '':
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    unique_filename = f"lost_found_{studentID}_{int(time.time())}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                    image_path = unique_filename
                else:
                    flash("Invalid file type. Please upload PNG, JPG, JPEG, or GIF images.", "danger")
                    return redirect("/lost-found")

        if item_name and description and location_found and contact_info:
            execute_query(
                "INSERT INTO lost_items (studentID, item_name, description, location_found, date_found, image_path, contact_info) VALUES (?, ?, ?, ?, ?, ?, ?);", 
                [studentID, item_name, description, location_found, today.strftime("%Y-%m-%d"), image_path, contact_info]
            )
            
            # Send notification to all students
            students = execute_query("SELECT email FROM users WHERE role = 'Student';", fetchall=True)
            if students:
                for student in students:
                    email_content = f"""
                    <h3>New Lost Item Reported</h3>
                    <p>A new lost item has been reported on CampusCare:</p>
                    <p><strong>Item:</strong> {item_name}</p>
                    <p><strong>Description:</strong> {description}</p>
                    <p><strong>Found at:</strong> {location_found}</p>
                    <p><strong>Date Found:</strong> {today.strftime('%Y-%m-%d')}</p>
                    <p><strong>Contact Reporter:</strong> {contact_info}</p>
                    <br>
                    <p>If this is your item, please contact the reporter using the provided contact information to claim it.</p>
                    <p>Login to CampusCare for more details: <a href="/lost-found">Lost & Found</a></p>
                    """
                    
                    # Store notification in database
                    student_info = execute_query("SELECT id FROM users WHERE email = ?;", [student['email']], fetch=True)
                    if student_info:
                        execute_query(
                            "INSERT INTO email_notifications (recipient_id, subject, message, sent_date) VALUES (?, ?, ?, ?);",
                            [student_info['id'], f"CampusCare: New Lost Item - {item_name}", email_content, today.strftime("%Y-%m-%d")]
                        )
                    
                    # Send actual email
                    send_email(student['email'], f"CampusCare: New Lost Item - {item_name}", email_content)
            
            flash("Lost item reported successfully! All students have been notified.", "success")
            return redirect("/lost-found")
        else:
            flash("Please fill in all required fields.", "danger")
            return redirect("/lost-found")
    
    # Get all lost items with reporter information
    lost_items = execute_query("""
        SELECT lost_items.*, 
               reporter.username as reported_by, 
               reporter.email as reporter_email
        FROM lost_items 
        LEFT JOIN users as reporter ON lost_items.studentID = reporter.id
        ORDER BY lost_items.date_found DESC;
    """, fetchall=True)
    
    lost_items_dict = rows_to_dict(lost_items) if lost_items else []
    
    return render_template("lost_found.html", 
                           name=session["username"], 
                           user_id=session["user_id"],
                           lost_items=lost_items_dict)

# The /claim-item route is now obsolete. The claiming process is handled offline.
@app.route("/claim-item/<int:item_id>", methods=["POST"])
def claim_item_obsolete(item_id):
    flash("Item claiming is now handled by contacting the reporter directly.", "info")
    return redirect("/lost-found")

# Mark as collected route (ONLY for the reporter after handing over the item)
@app.route("/mark-collected/<int:item_id>", methods=["POST"])
def mark_collected(item_id):
    if 'user_id' not in session or session.get('role') != 'Student':
        flash("Access denied. Please login as a student.", "danger")
        return redirect("/")
    
    # Verify that the current user is the one who reported the item
    item = execute_query("SELECT * FROM lost_items WHERE id = ? AND studentID = ?;", [item_id, session["user_id"]], fetch=True)
    
    if not item:
        flash("You can only mark items as collected that you reported.", "danger")
        return redirect("/lost-found")
    
    if item['status'] == 'Collected':
        flash("This item is already marked as collected.", "danger")
        return redirect("/lost-found")
    
    # Update item status to collected
    execute_query(
        "UPDATE lost_items SET status = 'Collected' WHERE id = ?;", 
        [item_id]
    )
    
    flash("Item marked as collected successfully!", "success")
    return redirect("/lost-found")

# Delete lost item route (ONLY for the reporter)
@app.route("/delete-lost-item/<int:item_id>", methods=["POST"])
def delete_lost_item(item_id):
    if 'user_id' not in session or session.get('role') != 'Student':
        flash("Access denied. Please login as a student.", "danger")
        return redirect("/")
    
    # Verify that the current user is the one who reported the item
    item = execute_query("SELECT * FROM lost_items WHERE id = ? AND studentID = ?;", [item_id, session["user_id"]], fetch=True)
    
    if not item:
        flash("You can only delete items that you reported.", "danger")
        return redirect("/lost-found")
    
    if item['status'] == 'Collected':
        flash("Cannot delete items that have been collected.", "danger")
        return redirect("/lost-found")
    
    # Delete the item
    execute_query("DELETE FROM lost_items WHERE id = ?;", [item_id])
    
    flash("Lost item deleted successfully!", "success")
    return redirect("/lost-found")

# Email notifications page
@app.route("/email-notifications")
def email_notifications():
    if 'user_id' not in session or session.get('role') != 'Admin':
        flash("Access denied. Please login as an administrator.", "danger")
        return redirect("/")
    
    # Get all email notifications with recipient names
    notifications = execute_query("""
        SELECT en.*, u.username as recipient_name, r.title as request_title
        FROM email_notifications en
        LEFT JOIN users u ON en.recipient_id = u.id
        LEFT JOIN requests r ON en.request_id = r.id
        ORDER BY en.sent_date DESC, en.id DESC;
    """, fetchall=True)
    
    notifications_dict = rows_to_dict(notifications) if notifications else []
    
    return render_template("email_notifications.html", 
                           name=session["username"], 
                           notifications=notifications_dict)

# admin page
@app.route("/admin", methods=["GET","POST"])
def admin():
    if 'user_id' not in session or session.get('role') != 'Admin':
        flash("Access denied. Please login as an administrator.", "danger")
        return redirect("/")
    
    # Get all requests with student names, ordered by date
    all_requests = execute_query("""
        SELECT requests.*, users.username as student_name 
        FROM requests 
        LEFT JOIN users ON requests.studentID = users.id 
        ORDER BY requests.date DESC;
    """, fetchall=True)
    
    # Convert Row objects to dictionaries
    all_requests_dict = rows_to_dict(all_requests) if all_requests else []
    
    # Get all workers with their assigned request count
    workers = execute_query("""
        SELECT u.*, COUNT(r.id) as assigned_requests 
        FROM users u 
        LEFT JOIN requests r ON u.id = r.workerID AND r.status != 'Completed'
        WHERE u.role = 'Worker' 
        GROUP BY u.id;
    """, fetchall=True)
    
    workers_dict = rows_to_dict(workers) if workers else []
    
    # Get all departments for filter
    departments = execute_query("SELECT DISTINCT department FROM users WHERE department IS NOT NULL;", fetchall=True)
    departments_dict = [d['department'] for d in rows_to_dict(departments)] if departments else []
    
    # Calculate statistics
    total_requests = len(all_requests_dict)
    pending_count = sum(1 for r in all_requests_dict if r["status"] == "Pending")
    in_progress_count = sum(1 for r in all_requests_dict if r["status"] == "In Progress")
    resolved_count = sum(1 for r in all_requests_dict if r["status"] == "Completed")
    
    return render_template("admin.html", 
                           name=session["username"], 
                           all_requests=all_requests_dict,
                           workers=workers_dict,
                           departments=departments_dict,
                           total_requests=total_requests,
                           pending_count=pending_count,
                           in_progress_count=in_progress_count,
                           resolved_count=resolved_count)

# Get workers by department
@app.route("/get-workers-by-department/<department>")
def get_workers_by_department(department):
    workers = execute_query("""
        SELECT u.*, COUNT(r.id) as assigned_requests 
        FROM users u 
        LEFT JOIN requests r ON u.id = r.workerID AND r.status != 'Completed'
        WHERE u.role = 'Worker' AND u.department = ?
        GROUP BY u.id;
    """, [department], fetchall=True)
    
    workers_dict = rows_to_dict(workers) if workers else []
    return jsonify({"workers": workers_dict})

# Add a new route for assigning requests
@app.route("/assign-request", methods=["POST"])
def assign_request():
    if 'user_id' not in session or session.get('role') != 'Admin':
        flash("Access denied. Please login as an administrator.", "danger")
        return redirect("/")
    
    if request.method == "POST":
        request_id = request.form.get("request_id")
        worker_id = request.form.get("worker_id")
        department = request.form.get("department")
        status = request.form.get("status")
        notes = request.form.get("notes")
        
        # Get current status before update
        current_request = execute_query("SELECT status FROM requests WHERE id = ?;", [request_id], fetch=True)
        current_status = current_request["status"] if current_request else None
        
        # Update the request with department and worker
        execute_query(
            "UPDATE requests SET workerID = ?, department = ?, status = ?, notes = ? WHERE id = ?;", 
            [worker_id, department, status, notes, request_id]
        )
        
        # If status changed and it's not the same as before, send email
        if current_status and current_status != status:
            send_status_update_email(request_id, status, notes)
        
        # Update worker status to "Assigned"
        if worker_id and worker_id != "null":
            execute_query(
                "UPDATE users SET status = 'Assigned' WHERE id = ?;", 
                [worker_id]
            )
        
        flash("Request assigned successfully!", "success")
        return redirect("/admin")

# worker page
@app.route("/worker", methods=["GET","POST"])
def worker():
    if 'user_id' not in session or session.get('role') != 'Worker':
        flash("Access denied. Please login as a worker.", "danger")
        return redirect("/")
    
    # Get the current worker's ID
    worker_id = session["user_id"]
    # Get requests assigned to this worker with student names
    assigned_requests = execute_query("""
        SELECT requests.*, users.username as student_name 
        FROM requests 
        LEFT JOIN users ON requests.studentID = users.id 
        WHERE requests.workerID = ? 
        ORDER BY requests.date DESC;
    """, [worker_id], fetchall=True)
    
    # Convert Row objects to dictionaries
    assigned_requests_dict = rows_to_dict(assigned_requests) if assigned_requests else []
    
    return render_template("worker.html", 
                           name=session["username"], 
                           assigned_requests=assigned_requests_dict)

# Add a new route for updating requests with image upload
@app.route("/update-request", methods=["POST"])
def update_request():
    if 'user_id' not in session or session.get('role') != 'Worker':
        flash("Access denied. Please login as a worker.", "danger")
        return redirect("/")
    
    if request.method == "POST":
        request_id = request.form.get("request_id")
        status = request.form.get("status")
        worker_notes = request.form.get("worker_notes")
        
        # Handle worker image upload - FIXED: Check if file exists and is valid
        worker_image_path = None
        if 'worker_image' in request.files:
            file = request.files['worker_image']
            # Check if file is selected and has a filename
            if file and file.filename != '':
                if allowed_file(file.filename):
                    filename = secure_filename(file.filename)
                    # Create unique filename to avoid conflicts
                    unique_filename = f"worker_{request_id}_{int(time.time())}_{filename}"
                    file.save(os.path.join(app.config['UPLOAD_FOLDER'], unique_filename))
                    worker_image_path = unique_filename
                else:
                    flash("Invalid file type. Please upload PNG, JPG, JPEG, or GIF images.", "danger")
                    return redirect("/worker")
        
        # Get current status before update
        current_request = execute_query("SELECT status FROM requests WHERE id = ?;", [request_id], fetch=True)
        current_status = current_request["status"] if current_request else None
        
        # Update the request in the database with worker image
        if worker_image_path:
            execute_query(
                "UPDATE requests SET status = ?, worker_notes = ?, worker_image_path = ? WHERE id = ?;", 
                [status, worker_notes, worker_image_path, request_id]
            )
        else:
            execute_query(
                "UPDATE requests SET status = ?, worker_notes = ? WHERE id = ?;", 
                [status, worker_notes, request_id]
            )
        
        # If status changed and it's not the same as before, send email
        if current_status and current_status != status:
            send_status_update_email(request_id, status, worker_notes, worker_image_path)
        
        # If request is completed, set worker status back to Available
        if status == "Completed":
            worker_id = execute_query("SELECT workerID FROM requests WHERE id = ?;", [request_id], fetch=True)
            if worker_id and worker_id["workerID"]:
                execute_query(
                    "UPDATE users SET status = 'Available' WHERE id = ?;", 
                    [worker_id["workerID"]]
                )
        
        flash("Request updated successfully!", "success")
        return redirect("/worker")

# Add worker route
@app.route("/add-worker", methods=["POST"])
def add_worker():
    if 'user_id' not in session or session.get('role') != 'Admin':
        flash("Access denied. Please login as an administrator.", "danger")
        return redirect("/")
    
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        password = request.form.get("password")
        department = request.form.get("department")
        
        print(f"DEBUG: Received form data - username: {username}, email: {email}, department: {department}")
        
        # Validate inputs
        if not username or not email or not password or not department:
            flash("All fields are required!", "danger")
            return redirect("/admin")
        
        # Check if email already exists
        existing_user = execute_query("SELECT id FROM users WHERE email = ?;", [email], fetch=True)
        if existing_user:
            flash("Email already exists!", "danger")
            return redirect("/admin")
        
        try:
            # Hash password and create worker account
            hashed_password = generate_password_hash(password)
            execute_query(
                "INSERT INTO users (username, email, password, role, department, status) VALUES (?, ?, ?, ?, ?, ?);", 
                [username, email, hashed_password, "Worker", department, "Available"]
            )
            
            flash("Worker account created successfully!", "success")
            print(f"DEBUG: Worker {username} created successfully")
            
        except Exception as e:
            print(f"ERROR: Error creating worker: {e}")
            flash(f"Error creating worker account: {str(e)}", "danger")
        
        return redirect("/admin")

# Delete worker route
@app.route("/delete-worker/<int:worker_id>", methods=["POST"])
def delete_worker(worker_id):
    if 'user_id' not in session or session.get('role') != 'Admin':
        flash("Access denied. Please login as an administrator.", "danger")
        return redirect("/")
    
    # First, unassign any requests from this worker
    execute_query("UPDATE requests SET workerID = NULL WHERE workerID = ?;", [worker_id])
    
    # Then delete the worker account
    execute_query("DELETE FROM users WHERE id = ? AND role = 'Worker';", [worker_id])
    
    flash("Worker account deleted successfully!", "success")
    return redirect("/admin")

# logout
@app.route('/logout')
def logout():
    session.clear()
    flash("You have been logged out successfully.", "info")
    return redirect("/")

# password reset from profile
@app.route('/reset-password', methods=['POST'])
def reset_password():
    if 'user_id' not in session:
        flash("Access denied. Please login.", "danger")
        return redirect("/")
    
    if request.method == "POST":
        new_password = request.form['new_password']
        hashed_pw = generate_password_hash(new_password)
        execute_query(
            "UPDATE users set password = ? WHERE username= ?;", 
            [hashed_pw, session["username"]]
        )
        flash('Password reset successfully.', 'success')
        return redirect(request.referrer or "/")

# Start the scheduler
scheduler = BackgroundScheduler()
scheduler.add_job(func=check_for_pending_requests, trigger="interval", minutes=15)
scheduler.start()

# Shut down the scheduler when the app exits
atexit.register(lambda: scheduler.shutdown())

if __name__ == "__main__":
    init_db()
    migrate_db() 
    check_db_schema()  
    app.run(debug=True)