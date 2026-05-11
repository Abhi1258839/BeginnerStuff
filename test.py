import os
import sqlite3
from flask import Flask, request, session, redirect, url_for, render_template

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'  # Change this to a random secret key
DATABASE = os.path.join(app.root_path, 'users.db')


def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db_connection()
    conn.execute(
        '''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL
        )
        '''
    )
    conn.commit()
    conn.close()


init_db()


@app.route('/')
def home():
    if 'logged_in' in session:
        return (
            f"Welcome, {session.get('username')}! This is your Trading App dashboard. "
            '<a href="/logout">Logout</a>'
        )
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        conn = get_db_connection()
        user = conn.execute(
            'SELECT * FROM users WHERE username = ? AND password = ?',
            (username, password),
        ).fetchone()
        conn.close()

        if user:
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('home'))
        return render_template('login.html', error='Invalid username or password')
    return render_template('login.html')


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        if not username or not email or not password:
            return render_template('signup.html', error='All fields are required')

        conn = get_db_connection()
        try:
            conn.execute(
                'INSERT INTO users (username, password, email) VALUES (?, ?, ?)',
                (username, password, email),
            )
            conn.commit()
            conn.close()
            session['logged_in'] = True
            session['username'] = username
            return redirect(url_for('home'))
        except sqlite3.IntegrityError:
            conn.close()
            return render_template(
                'signup.html',
                error='Username or email already exists',
            )

    return render_template('signup.html')


@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    session.pop('username', None)
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run(debug=True)