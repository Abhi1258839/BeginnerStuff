import os
import sqlite3
from datetime import datetime
from flask import Flask, render_template, request, redirect, session, url_for

app = Flask(__name__)
app.secret_key = 'change_this_secret_key'
DB_PATH = os.path.join(app.root_path, 'users.db')


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        'CREATE TABLE IF NOT EXISTS users ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'full_name TEXT NOT NULL, '
        'email TEXT NOT NULL UNIQUE, '
        'password TEXT NOT NULL, '
        'company TEXT NOT NULL DEFAULT "Unemployed", '
        'role TEXT NOT NULL DEFAULT "Professional"'
        ')'
    )
    existing_columns = [row['name'] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
    if 'company' not in existing_columns:
        conn.execute("ALTER TABLE users ADD COLUMN company TEXT NOT NULL DEFAULT 'Unemployed'")
    if 'role' not in existing_columns:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'Professional'")

    conn.execute(
        'CREATE TABLE IF NOT EXISTS companies ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'name TEXT NOT NULL UNIQUE, '
        'description TEXT NOT NULL, '
        'created_by TEXT NOT NULL'
        ')'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS company_roles ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'company_id INTEGER NOT NULL, '
        'title TEXT NOT NULL, '
        'level TEXT NOT NULL, '
        'description TEXT NOT NULL, '
        'FOREIGN KEY(company_id) REFERENCES companies(id)'
        ')'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS role_assignments ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'company_id INTEGER NOT NULL, '
        'user_email TEXT NOT NULL, '
        'role_id INTEGER NOT NULL, '
        'assigned_at TEXT NOT NULL, '
        'FOREIGN KEY(company_id) REFERENCES companies(id), '
        'FOREIGN KEY(role_id) REFERENCES company_roles(id)'
        ')'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS hiring_requests ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'from_email TEXT NOT NULL, '
        'to_email TEXT NOT NULL, '
        'company_id INTEGER NOT NULL, '
        'role_title TEXT NOT NULL, '
        'level TEXT NOT NULL, '
        'status TEXT NOT NULL, '
        'created_at TEXT NOT NULL, '
        'FOREIGN KEY(company_id) REFERENCES companies(id)'
        ')'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS job_promotions ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'company_id INTEGER NOT NULL, '
        'role_id INTEGER NOT NULL, '
        'description TEXT NOT NULL, '
        'is_open INTEGER NOT NULL DEFAULT 1, '
        'created_at TEXT NOT NULL, '
        'FOREIGN KEY(company_id) REFERENCES companies(id), '
        'FOREIGN KEY(role_id) REFERENCES company_roles(id)'
        ')'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS job_applications ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'promotion_id INTEGER NOT NULL, '
        'applicant_email TEXT NOT NULL, '
        'status TEXT NOT NULL, '
        'created_at TEXT NOT NULL, '
        'updated_at TEXT NOT NULL, '
        'FOREIGN KEY(promotion_id) REFERENCES job_promotions(id)'
        ')'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS connections ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'requestor_email TEXT NOT NULL, '
        'target_email TEXT NOT NULL, '
        'status TEXT NOT NULL, '
        'created_at TEXT NOT NULL'
        ')'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS chat_messages ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'sender_email TEXT NOT NULL, '
        'recipient_email TEXT NOT NULL, '
        'message TEXT NOT NULL, '
        'created_at TEXT NOT NULL'
        ')'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS notifications ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'user_email TEXT NOT NULL, '
        'message TEXT NOT NULL, '
        'link TEXT NOT NULL, '
        'is_read INTEGER NOT NULL DEFAULT 0'
        ')'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS experiences ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'user_email TEXT NOT NULL, '
        'company_name TEXT NOT NULL, '
        'role TEXT NOT NULL, '
        'level TEXT NOT NULL, '
        'description TEXT NOT NULL, '
        'start_date TEXT NOT NULL, '
        'end_date TEXT NOT NULL'
        ')'
    )

    conn.commit()
    conn.close()


init_db()


def current_user():
    if 'user' not in session:
        return None
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE email = ?', (session['user']['email'],)).fetchone()
    conn.close()
    if user:
        session['user'] = {
            'full_name': user['full_name'],
            'email': user['email'],
            'company': user['company'],
            'role': user['role'],
        }
    return user


def login_user(user_row):
    session['user'] = {
        'full_name': user_row['full_name'],
        'email': user_row['email'],
        'company': user_row['company'],
        'role': user_row['role'],
    }


def add_experience(user_email, company_name, role, level):
    if not company_name or company_name == 'Unemployed':
        return
    conn = get_db()
    conn.execute(
        'INSERT INTO experiences (user_email, company_name, role, level, description, start_date, end_date) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (user_email, company_name, role, level, 'Past experience recorded automatically.', datetime.utcnow().strftime('%Y-%m-%d'), 'Present'),
    )
    conn.commit()
    conn.close()


def add_notification(user_email, message, link='/dashboard'):
    conn = get_db()
    conn.execute(
        'INSERT INTO notifications (user_email, message, link) VALUES (?, ?, ?)',
        (user_email, message, link),
    )
    conn.commit()
    conn.close()


@app.route('/', methods=['GET', 'POST'])
def login():
    error = ''
    full_name = ''
    email = ''
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()

        if not full_name or not email or not password:
            error = 'Please enter your full name, email, and password.'
        else:
            conn = get_db()
            user = conn.execute(
                'SELECT * FROM users WHERE full_name = ? AND email = ? AND password = ?',
                (full_name, email, password),
            ).fetchone()
            conn.close()
            if user:
                login_user(user)
                return redirect(url_for('dashboard'))
            error = 'Invalid login details. Please check your full name, email, and password.'

    return render_template('login.html', error=error, full_name=full_name, email=email)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    error = ''
    full_name = ''
    email = ''
    company = ''
    employed = 'yes'
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        employed = request.form.get('employed', 'yes')
        company = request.form.get('company', '').strip()

        if employed == 'no' or not company:
            company = 'Unemployed'
            role = 'Job Seeker'
        else:
            role = 'Professional'

        if not full_name or not email or not password:
            error = 'Please fill in your name, email, and password.'
        else:
            conn = get_db()
            existing = conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone()
            if existing:
                error = 'An account with that email already exists.'
            else:
                conn.execute(
                    'INSERT INTO users (full_name, email, password, company, role) VALUES (?, ?, ?, ?, ?)',
                    (full_name, email, password, company, role),
                )
                conn.commit()
                user = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
                conn.close()
                login_user(user)
                return redirect(url_for('dashboard'))
            conn.close()

    return render_template(
        'signup.html',
        error=error,
        full_name=full_name,
        email=email,
        company=company,
        employed=employed,
    )


@app.route('/dashboard')
def dashboard():
    user = current_user()
    if not user:
        return redirect('/')

    query = request.args.get('q', '').strip()
    message = request.args.get('message', '')
    conn = get_db()
    if query:
        query_param = f'%{query}%'
        matched_users = conn.execute(
            'SELECT u.full_name, u.email, u.company, u.role, c.id AS company_id FROM users u LEFT JOIN companies c ON u.company = c.name WHERE u.full_name LIKE ? OR u.email LIKE ? OR u.company LIKE ? ORDER BY u.full_name ASC',
            (query_param, query_param, query_param),
        ).fetchall()
        matched_companies = conn.execute(
            'SELECT id, name, description, created_by FROM companies WHERE name LIKE ? OR description LIKE ? ORDER BY name ASC',
            (query_param, query_param),
        ).fetchall()
    else:
        matched_users = []
        matched_companies = conn.execute(
            'SELECT id, name, description, created_by FROM companies ORDER BY id DESC LIMIT 5'
        ).fetchall()

    total_users = conn.execute('SELECT COUNT(1) FROM users').fetchone()[0]
    total_companies = conn.execute('SELECT COUNT(1) FROM companies').fetchone()[0]
    notifications = conn.execute(
        'SELECT * FROM notifications WHERE user_email = ? AND is_read = 0 ORDER BY id DESC',
        (user['email'],),
    ).fetchall()
    pending_requests = conn.execute(
        'SELECT hr.id, hr.from_email, hr.role_title, hr.level, c.name AS company_name FROM hiring_requests hr JOIN companies c ON hr.company_id = c.id WHERE hr.to_email = ? AND hr.status = "pending" ORDER BY hr.created_at DESC',
        (user['email'],),
    ).fetchall()
    connections = conn.execute(
        'SELECT requestor_email, target_email FROM connections WHERE requestor_email = ? OR target_email = ?',
        (user['email'], user['email']),
    ).fetchall()
    connected_emails = set()
    for row in connections:
        connected_emails.add(row['requestor_email'])
        connected_emails.add(row['target_email'])
    connected_emails.discard(user['email'])

    recommended_users = conn.execute(
        'SELECT u.full_name, u.email, u.company, u.role, c.id AS company_id FROM users u LEFT JOIN companies c ON u.company = c.name WHERE u.email != ? AND u.company != ? ORDER BY u.role ASC, u.full_name ASC LIMIT 5',
        (user['email'], user['company']),
    ).fetchall()

    promotions = conn.execute(
        'SELECT p.id, p.description, p.is_open, p.created_at, c.name AS company_name, c.id AS company_id, c.created_by, r.title AS role_title, r.level AS role_level FROM job_promotions p JOIN companies c ON p.company_id = c.id JOIN company_roles r ON p.role_id = r.id WHERE p.is_open = 1 ORDER BY p.created_at DESC'
    ).fetchall()

    founder_applications = []
    if user['role'] == 'Founder' and user['company'] != 'Unemployed':
        company_info = conn.execute('SELECT id FROM companies WHERE name = ?', (user['company'],)).fetchone()
        if company_info:
            founder_applications = conn.execute(
                'SELECT ja.id, ja.status, ja.applicant_email, ja.created_at, ja.updated_at, u.full_name AS applicant_name, r.title AS role_title, r.level AS role_level, jp.id AS promotion_id, jp.description FROM job_applications ja JOIN job_promotions jp ON ja.promotion_id = jp.id JOIN company_roles r ON jp.role_id = r.id JOIN users u ON ja.applicant_email = u.email WHERE jp.company_id = ? AND ja.status IN ("pending", "interviewing") ORDER BY ja.created_at DESC',
                (company_info['id'],),
            ).fetchall()

    conn.close()

    return render_template(
        'dashboard.html',
        user=user,
        query=query,
        message=message,
        users=matched_users,
        companies=matched_companies,
        total_users=total_users,
        total_companies=total_companies,
        notifications=notifications,
        pending_requests=pending_requests,
        connected_emails=connected_emails,
        recommended_users=recommended_users,
        promotions=promotions,
        founder_applications=founder_applications,
    )


@app.route('/profile')
def profile():
    user = current_user()
    if not user:
        return redirect('/')

    email = request.args.get('email', user['email']).strip().lower()
    conn = get_db()
    user_row = conn.execute('SELECT * FROM users WHERE email = ?', (email,)).fetchone()
    if not user_row:
        conn.close()
        return redirect('/')

    experiences = conn.execute(
        'SELECT * FROM experiences WHERE user_email = ? ORDER BY id DESC',
        (email,),
    ).fetchall()
    if user_row['company'] and user_row['company'] != 'Unemployed':
        team_count = conn.execute(
            'SELECT COUNT(1) FROM users WHERE company = ? AND email != ?',
            (user_row['company'], user_row['email']),
        ).fetchone()[0]
    else:
        team_count = 0
    conn.close()

    return render_template('profile.html', user=user_row, team_count=team_count, experiences=experiences, is_self=(email == user['email']))


@app.route('/company/<int:company_id>', methods=['GET', 'POST'])
def company_page(company_id):
    user = current_user()
    if not user:
        return redirect('/')

    message = request.args.get('message', '')
    conn = get_db()
    company = conn.execute('SELECT * FROM companies WHERE id = ?', (company_id,)).fetchone()
    if not company:
        conn.close()
        return redirect(url_for('dashboard'))

    roles = conn.execute('SELECT * FROM company_roles WHERE company_id = ? ORDER BY id ASC', (company_id,)).fetchall()
    assignments = conn.execute(
        'SELECT ra.id, ra.assigned_at, u.full_name, u.email, r.title, r.level FROM role_assignments ra JOIN users u ON ra.user_email = u.email JOIN company_roles r ON ra.role_id = r.id WHERE ra.company_id = ? ORDER BY r.level ASC, u.full_name ASC',
        (company_id,),
    ).fetchall()
    team = {}
    for item in assignments:
        team.setdefault(item['title'] + ' • ' + item['level'], []).append(item)

    promotions = conn.execute(
        'SELECT p.id, p.description, p.is_open, p.created_at, r.title AS role_title, r.level AS role_level FROM job_promotions p JOIN company_roles r ON p.role_id = r.id WHERE p.company_id = ? ORDER BY p.created_at DESC',
        (company_id,),
    ).fetchall()

    applications = []
    is_founder = user['email'] == company['created_by']
    if is_founder:
        applications = conn.execute(
            'SELECT ja.id, ja.status, ja.applicant_email, ja.created_at, ja.updated_at, u.full_name AS applicant_name, r.title AS role_title, r.level AS role_level, jp.description AS promotion_description, jp.id AS promotion_id FROM job_applications ja JOIN job_promotions jp ON ja.promotion_id = jp.id JOIN company_roles r ON jp.role_id = r.id JOIN users u ON ja.applicant_email = u.email WHERE jp.company_id = ? ORDER BY ja.created_at DESC',
            (company_id,),
        ).fetchall()

    conn.close()

    return render_template('company.html', user=user, company=company, roles=roles, team=team, is_founder=is_founder, promotions=promotions, applications=applications, message=message)


@app.route('/company/<int:company_id>/add-role', methods=['POST'])
def add_company_role(company_id):
    user = current_user()
    if not user:
        return redirect('/')

    conn = get_db()
    company = conn.execute('SELECT * FROM companies WHERE id = ?', (company_id,)).fetchone()
    if not company or company['created_by'] != user['email']:
        conn.close()
        return redirect(url_for('company_page', company_id=company_id))

    title = request.form.get('title', '').strip()
    level = request.form.get('level', '').strip()
    description = request.form.get('description', '').strip()
    if title and level:
        conn.execute(
            'INSERT INTO company_roles (company_id, title, level, description) VALUES (?, ?, ?, ?)',
            (company_id, title, level, description or 'Role added by the company founder.'),
        )
        conn.commit()
    conn.close()
    return redirect(url_for('company_page', company_id=company_id))


@app.route('/company/<int:company_id>/assign-role', methods=['POST'])
def assign_role(company_id):
    user = current_user()
    if not user:
        return redirect('/')

    conn = get_db()
    company = conn.execute('SELECT * FROM companies WHERE id = ?', (company_id,)).fetchone()
    if not company or company['created_by'] != user['email']:
        conn.close()
        return redirect(url_for('company_page', company_id=company_id))

    role_id = request.form.get('role_id', type=int)
    employee_email = request.form.get('employee_email', '').strip().lower()
    role = conn.execute('SELECT * FROM company_roles WHERE id = ? AND company_id = ?', (role_id, company_id)).fetchone()
    employee = conn.execute('SELECT * FROM users WHERE email = ?', (employee_email,)).fetchone()

    if role and employee and employee_email != user['email']:
        conn.execute(
            'INSERT INTO role_assignments (company_id, user_email, role_id, assigned_at) VALUES (?, ?, ?, ?)',
            (company_id, employee_email, role_id, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')),
        )
        conn.execute(
            'UPDATE users SET company = ?, role = ? WHERE email = ?',
            (company['name'], role['title'], employee_email),
        )
        conn.commit()
        add_notification(employee_email, f'You were assigned as {role["title"]} ({role["level"]}) at {company["name"]}.', url_for('profile'))
    conn.close()
    return redirect(url_for('company_page', company_id=company_id))


@app.route('/send-request', methods=['POST'])
def send_request():
    user = current_user()
    if not user:
        return redirect('/')

    to_email = request.form.get('to_email', '').strip().lower()
    company_id = request.form.get('company_id', type=int)
    role_title = request.form.get('role_title', '').strip()
    level = request.form.get('level', '').strip()
    message = request.form.get('message', '').strip()
    if not message:
        if user['role'] == 'Founder':
            message = f'{user["company"]} is hiring for {role_title or "an open role"} ({level or "Senior"}).'
        else:
            message = f'{user["full_name"]} is interested in joining your company.'

    conn = get_db()
    company = None
    if company_id:
        company = conn.execute('SELECT * FROM companies WHERE id = ?', (company_id,)).fetchone()
    elif user['role'] == 'Founder':
        company = conn.execute('SELECT * FROM companies WHERE name = ?', (user['company'],)).fetchone()

    if not company:
        conn.close()
        return redirect(url_for('dashboard', message='The selected company could not be found.'))

    target = conn.execute('SELECT * FROM users WHERE email = ?', (to_email,)).fetchone()
    if not target or target['email'] == user['email']:
        conn.close()
        return redirect(url_for('dashboard', message='Cannot send request to that user.'))

    if user['role'] == 'Founder':
        # Founder is sending a hiring request to a candidate.
        if user['company'] == 'Unemployed':
            conn.close()
            return redirect(url_for('dashboard', message='Only founders can send hiring requests.'))
        if target['email'] == user['email']:
            conn.close()
            return redirect(url_for('dashboard', message='Cannot send request to yourself.'))
        if target['company'] == user['company']:
            conn.close()
            return redirect(url_for('dashboard', message='Cannot send a hiring request to someone already at your company.'))
    else:
        # Candidate is sending a job request to a founder.
        if target['role'] != 'Founder':
            conn.close()
            return redirect(url_for('dashboard', message='Job requests can only be sent to founders.'))
        if company['id'] != company_id and not company_id:
            company = conn.execute('SELECT * FROM companies WHERE name = ?', (target['company'],)).fetchone()

    existing = conn.execute(
        'SELECT id FROM hiring_requests WHERE from_email = ? AND to_email = ? AND company_id = ? AND status = "pending"',
        (user['email'], to_email, company['id']),
    ).fetchone()
    if existing:
        conn.close()
        return redirect(url_for('dashboard', message='You already have a pending request for this user or company.'))

    conn.execute(
        'INSERT INTO hiring_requests (from_email, to_email, company_id, role_title, level, status, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)',
        (user['email'], to_email, company['id'], role_title or 'Open role', level or 'Senior', 'pending', datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')),
    )
    conn.commit()
    conn.close()
    add_notification(to_email, f'{user["full_name"]} sent you a request to join {company["name"]}.', url_for('dashboard'))
    return redirect(url_for('dashboard', message='Request sent.'))


@app.route('/respond-request', methods=['POST'])
def respond_request():
    user = current_user()
    if not user:
        return redirect('/')

    request_id = request.form.get('request_id', type=int)
    action = request.form.get('action', '').strip().lower()
    conn = get_db()
    hr = conn.execute('SELECT * FROM hiring_requests WHERE id = ? AND to_email = ?', (request_id, user['email'])).fetchone()
    if not hr:
        conn.close()
        return redirect(url_for('dashboard', message='Request not found.'))

    company = conn.execute('SELECT * FROM companies WHERE id = ?', (hr['company_id'],)).fetchone()
    if not company:
        conn.close()
        return redirect(url_for('dashboard', message='Company not found.'))

    if action == 'accept':
        hired_email = hr['from_email'] if user['role'] == 'Founder' else user['email']
        hired_user = conn.execute('SELECT * FROM users WHERE email = ?', (hired_email,)).fetchone()
        if hired_user and hired_user['company'] and hired_user['company'] != 'Unemployed':
            add_experience(hired_email, hired_user['company'], hired_user['role'], hired_user['role'])
        conn.execute(
            'UPDATE users SET company = ?, role = ? WHERE email = ?',
            (company['name'], hr['role_title'], hired_email),
        )
        conn.execute('UPDATE hiring_requests SET status = ? WHERE id = ?', ('accepted', request_id))
        conn.commit()
        add_notification(hr['from_email'], f'{user["full_name"]} accepted your request for {company["name"]}.', url_for('dashboard'))
        conn.close()
        return redirect(url_for('dashboard', message='You accepted the request.'))

    conn.execute('UPDATE hiring_requests SET status = ? WHERE id = ?', ('declined', request_id))
    conn.commit()
    conn.close()
    add_notification(hr['from_email'], f'{user["full_name"]} declined your request for {company["name"]}.', url_for('dashboard'))
    return redirect(url_for('dashboard', message='You declined the request.'))


@app.route('/friend-request', methods=['POST'])
def friend_request():
    user = current_user()
    if not user:
        return redirect('/')

    target_email = request.form.get('target_email', '').strip().lower()
    if not target_email or target_email == user['email']:
        return redirect(url_for('dashboard', message='Invalid friend request.'))

    conn = get_db()
    target = conn.execute('SELECT * FROM users WHERE email = ?', (target_email,)).fetchone()
    if not target:
        conn.close()
        return redirect(url_for('dashboard', message='User not found.'))

    existing = conn.execute(
        'SELECT id FROM connections WHERE (requestor_email = ? AND target_email = ?) OR (requestor_email = ? AND target_email = ?)',
        (user['email'], target_email, target_email, user['email']),
    ).fetchone()
    if existing:
        conn.close()
        return redirect(url_for('dashboard', message='You are already connected with this user.'))

    conn.execute(
        'INSERT INTO connections (requestor_email, target_email, status, created_at) VALUES (?, ?, ?, ?)',
        (user['email'], target_email, 'accepted', datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')),
    )
    conn.commit()
    conn.close()
    add_notification(target_email, f'{user["full_name"]} added you as a connection.', url_for('profile', email=user['email']))
    return redirect(url_for('dashboard', message='Connection added.'))


@app.route('/chat/<other_email>')
def chat(other_email):
    user = current_user()
    if not user:
        return redirect('/')

    other_email = other_email.strip().lower()
    if other_email == user['email']:
        return redirect(url_for('dashboard', message='Cannot chat with yourself.'))

    conn = get_db()
    other = conn.execute('SELECT * FROM users WHERE email = ?', (other_email,)).fetchone()
    if not other:
        conn.close()
        return redirect(url_for('dashboard', message='User not found.'))

    messages = conn.execute(
        'SELECT * FROM chat_messages WHERE (sender_email = ? AND recipient_email = ?) OR (sender_email = ? AND recipient_email = ?) ORDER BY created_at ASC',
        (user['email'], other_email, other_email, user['email']),
    ).fetchall()
    conn.close()

    return render_template('chat.html', user=user, other=other, messages=messages)


@app.route('/send-message', methods=['POST'])
def send_message():
    user = current_user()
    if not user:
        return redirect('/')

    recipient_email = request.form.get('recipient_email', '').strip().lower()
    message = request.form.get('message', '').strip()
    if not recipient_email or not message or recipient_email == user['email']:
        return redirect(url_for('dashboard', message='Cannot send empty message.'))

    conn = get_db()
    recipient = conn.execute('SELECT * FROM users WHERE email = ?', (recipient_email,)).fetchone()
    if not recipient:
        conn.close()
        return redirect(url_for('dashboard', message='Recipient not found.'))

    conn.execute(
        'INSERT INTO chat_messages (sender_email, recipient_email, message, created_at) VALUES (?, ?, ?, ?)',
        (user['email'], recipient_email, message, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')),
    )
    conn.commit()
    conn.close()
    add_notification(recipient_email, f'{user["full_name"]} sent you a chat message.', url_for('chat', other_email=user['email']))
    return redirect(url_for('chat', other_email=recipient_email))


@app.route('/company/<int:company_id>/create-promotion', methods=['POST'])
def create_promotion(company_id):
    user = current_user()
    if not user:
        return redirect('/')

    conn = get_db()
    company = conn.execute('SELECT * FROM companies WHERE id = ?', (company_id,)).fetchone()
    if not company or company['created_by'] != user['email']:
        conn.close()
        return redirect(url_for('company_page', company_id=company_id))

    title = request.form.get('title', '').strip()
    level = request.form.get('level', '').strip()
    description = request.form.get('description', '').strip()
    if title and level:
        role = conn.execute('SELECT * FROM company_roles WHERE company_id = ? AND title = ? AND level = ?', (company_id, title, level)).fetchone()
        if not role:
            result = conn.execute(
                'INSERT INTO company_roles (company_id, title, level, description) VALUES (?, ?, ?, ?)',
                (company_id, title, level, description or 'Role added for a new hiring promotion.'),
            )
            role_id = result.lastrowid
        else:
            role_id = role['id']
        conn.execute(
            'INSERT INTO job_promotions (company_id, role_id, description, is_open, created_at) VALUES (?, ?, ?, ?, ?)',
            (company_id, role_id, description or f'Hiring for {title} ({level}).', 1, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')),
        )
        conn.commit()
    conn.close()
    return redirect(url_for('company_page', company_id=company_id, message='Promotion created.'))


@app.route('/apply-promotion', methods=['POST'])
def apply_promotion():
    user = current_user()
    if not user:
        return redirect('/')

    promotion_id = request.form.get('promotion_id', type=int)
    conn = get_db()
    promotion = conn.execute(
        'SELECT p.id, p.company_id, c.name AS company_name, c.created_by, r.title AS role_title, r.level AS role_level FROM job_promotions p JOIN companies c ON p.company_id = c.id JOIN company_roles r ON p.role_id = r.id WHERE p.id = ? AND p.is_open = 1',
        (promotion_id,),
    ).fetchone()
    if not promotion:
        conn.close()
        return redirect(url_for('dashboard', message='Promotion not found.'))
    if user['company'] == promotion['company_name']:
        conn.close()
        return redirect(url_for('dashboard', message='You are already part of this company.'))

    existing = conn.execute(
        'SELECT id FROM job_applications WHERE promotion_id = ? AND applicant_email = ? AND status IN ("pending", "interviewing")',
        (promotion_id, user['email']),
    ).fetchone()
    if existing:
        conn.close()
        return redirect(url_for('dashboard', message='You already have an active application for this role.'))

    conn.execute(
        'INSERT INTO job_applications (promotion_id, applicant_email, status, created_at, updated_at) VALUES (?, ?, ?, ?, ?)',
        (promotion_id, user['email'], 'pending', datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')),
    )
    conn.commit()
    conn.close()
    add_notification(promotion['created_by'], f'{user["full_name"]} applied for {promotion["role_title"]} at {promotion["company_name"]}.', url_for('company_page', company_id=promotion['company_id']))
    return redirect(url_for('dashboard', message='Application submitted.'))


@app.route('/process-application', methods=['POST'])
def process_application():
    user = current_user()
    if not user:
        return redirect('/')

    application_id = request.form.get('application_id', type=int)
    action = request.form.get('action', '').strip().lower()
    conn = get_db()
    application = conn.execute(
        'SELECT ja.id, ja.applicant_email, ja.status, ja.promotion_id, jp.company_id, jp.role_id, c.name AS company_name, c.created_by, r.title AS role_title, r.level AS role_level FROM job_applications ja JOIN job_promotions jp ON ja.promotion_id = jp.id JOIN companies c ON jp.company_id = c.id JOIN company_roles r ON jp.role_id = r.id WHERE ja.id = ?',
        (application_id,),
    ).fetchone()
    if not application or application['created_by'] != user['email']:
        conn.close()
        return redirect(url_for('dashboard', message='Application not found.'))

    applicant = conn.execute('SELECT * FROM users WHERE email = ?', (application['applicant_email'],)).fetchone()
    if not applicant:
        conn.close()
        return redirect(url_for('dashboard', message='Applicant user not found.'))

    new_status = application['status']
    if action == 'interview':
        new_status = 'interviewing'
        add_notification(applicant['email'], f'Interview scheduled for {application["role_title"]} at {application["company_name"]}.', url_for('dashboard'))
    elif action == 'accept':
        if applicant['company'] and applicant['company'] != 'Unemployed':
            add_experience(applicant['email'], applicant['company'], applicant['role'], applicant['role'])
        conn.execute(
            'UPDATE users SET company = ?, role = ? WHERE email = ?',
            (application['company_name'], application['role_title'], applicant['email']),
        )
        conn.execute(
            'INSERT INTO role_assignments (company_id, user_email, role_id, assigned_at) VALUES (?, ?, ?, ?)',
            (application['company_id'], applicant['email'], application['role_id'], datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')),
        )
        new_status = 'accepted'
        add_notification(applicant['email'], f'Congratulations! You were hired as {application["role_title"]} at {application["company_name"]}.', url_for('profile', email=applicant['email']))
    elif action == 'decline':
        new_status = 'declined'
        add_notification(applicant['email'], f'Your application for {application["role_title"]} at {application["company_name"]} was declined.', url_for('dashboard'))

    conn.execute(
        'UPDATE job_applications SET status = ?, updated_at = ? WHERE id = ?',
        (new_status, datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'), application_id),
    )
    conn.commit()
    conn.close()
    return redirect(url_for('company_page', company_id=application['company_id'], message='Application updated.'))


@app.route('/read-notifications')
def read_notifications():
    user = current_user()
    if not user:
        return redirect('/')
    conn = get_db()
    conn.execute('UPDATE notifications SET is_read = 1 WHERE user_email = ?', (user['email'],))
    conn.commit()
    conn.close()
    return redirect(url_for('dashboard'))


@app.route('/register-company', methods=['GET', 'POST'])
def register_company():
    user = current_user()
    if not user:
        return redirect('/')

    error = ''
    company_name = ''
    description = ''

    if request.method == 'POST':
        company_name = request.form.get('company_name', '').strip()
        description = request.form.get('description', '').strip()

        if not company_name:
            error = 'Please enter a company name.'
        else:
            conn = get_db()
            existing = conn.execute('SELECT id FROM companies WHERE name = ?', (company_name,)).fetchone()
            if existing:
                error = 'A company with that name already exists.'
            else:
                prev_company = user['company']
                prev_role = user['role']
                conn.execute(
                    'INSERT INTO companies (name, description, created_by) VALUES (?, ?, ?)',
                    (company_name, description or 'No description provided.', user['email']),
                )
                conn.execute(
                    'UPDATE users SET company = ?, role = ? WHERE email = ?',
                    (company_name, 'Founder', user['email']),
                )
                conn.commit()
                conn.close()
                if prev_company and prev_company != 'Unemployed':
                    add_experience(user['email'], prev_company, prev_role, '')
                session['user']['company'] = company_name
                session['user']['role'] = 'Founder'
                return redirect(url_for('dashboard', message='Company registered successfully.'))
            conn.close()

    return render_template(
        'register_company.html',
        error=error,
        company_name=company_name,
        description=description,
    )


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)


