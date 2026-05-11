import os
import sqlite3
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
        'company TEXT NOT NULL'
        ')'
    )
    conn.execute(
        'CREATE TABLE IF NOT EXISTS companies ('
        'id INTEGER PRIMARY KEY AUTOINCREMENT, '
        'name TEXT NOT NULL UNIQUE, '
        'description TEXT NOT NULL, '
        'created_by TEXT NOT NULL'
        ')'
    )

    existing_columns = [row['name'] for row in conn.execute("PRAGMA table_info(users)").fetchall()]
    if 'role' not in existing_columns:
        conn.execute("ALTER TABLE users ADD COLUMN role TEXT NOT NULL DEFAULT 'Professional'")

    conn.commit()
    conn.close()


init_db()


def login_user(user_row):
    session['user'] = {
        'full_name': user_row['full_name'],
        'email': user_row['email'],
        'company': user_row['company'],
        'role': user_row['role'],
    }


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
    user = session.get('user')
    if not user:
        return redirect('/')

    query = request.args.get('q', '').strip()
    message = request.args.get('message', '')
    conn = get_db()
    if query:
        query_param = f'%{query}%'
        matched_users = conn.execute(
            'SELECT full_name, email, company, role FROM users WHERE full_name LIKE ? OR email LIKE ? OR company LIKE ? ORDER BY full_name ASC',
            (query_param, query_param, query_param),
        ).fetchall()
        matched_companies = conn.execute(
            'SELECT name, description FROM companies WHERE name LIKE ? OR description LIKE ? ORDER BY name ASC',
            (query_param, query_param),
        ).fetchall()
    else:
        matched_users = []
        matched_companies = conn.execute(
            'SELECT name, description FROM companies ORDER BY id DESC LIMIT 5'
        ).fetchall()

    total_users = conn.execute('SELECT COUNT(1) FROM users').fetchone()[0]
    total_companies = conn.execute('SELECT COUNT(1) FROM companies').fetchone()[0]
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
    )


@app.route('/profile')
def profile():
    user = session.get('user')
    if not user:
        return redirect('/')

    conn = get_db()
    user_row = conn.execute('SELECT * FROM users WHERE email = ?', (user['email'],)).fetchone()
    if not user_row:
        conn.close()
        return redirect('/')

    if user_row['company'] and user_row['company'] != 'Unemployed':
        team_count = conn.execute(
            'SELECT COUNT(1) FROM users WHERE company = ? AND email != ?',
            (user_row['company'], user_row['email']),
        ).fetchone()[0]
    else:
        team_count = 0
    conn.close()

    return render_template('profile.html', user=user_row, team_count=team_count)


@app.route('/register-company', methods=['GET', 'POST'])
def register_company():
    user = session.get('user')
    if not user:
        return redirect('/')

    error = ''
    success = ''
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
                session['user']['company'] = company_name
                session['user']['role'] = 'Founder'
                return redirect(url_for('dashboard', message='Company registered successfully.'))
            conn.close()

    return render_template(
        'register_company.html',
        error=error,
        success=success,
        company_name=company_name,
        description=description,
    )


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/')


if __name__ == '__main__':
    app.run(debug=True)


