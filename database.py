import sqlite3
from datetime import datetime

DB_PATH = "signals.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    
    # Tabel sinyal per user
    c.execute('''
        CREATE TABLE IF NOT EXISTS signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            mode TEXT,
            entry REAL,
            sl REAL,
            tp REAL,
            rr REAL,
            result TEXT,  -- 'win', 'loss', 'pending'
            date TEXT,
            feedback_score INTEGER,  -- 1-5
            feedback_text TEXT
        )
    ''')
    
    conn.commit()
    conn.close()

def save_signal(user_id, username, mode, entry, sl, tp, rr):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO signals (user_id, username, mode, entry, sl, tp, rr, result, date, feedback_score)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, username, mode, entry, sl, tp, rr, 'pending', datetime.now().isoformat(), None))
    conn.commit()
    conn.close()

def update_result(signal_id, result):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE signals SET result = ? WHERE id = ?', (result, signal_id))
    conn.commit()
    conn.close()

def add_feedback(signal_id, score, text=None):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE signals SET feedback_score = ?, feedback_text = ? WHERE id = ?', (score, text, signal_id))
    conn.commit()
    conn.close()

def get_user_history(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        SELECT mode, entry, sl, tp, rr, result, date, feedback_score 
        FROM signals WHERE user_id = ? ORDER BY date DESC LIMIT 50
    ''', (user_id,))
    rows = c.fetchall()
    conn.close()
    return rows

def get_user_winrate(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT result FROM signals WHERE user_id = ? AND result != "pending"', (user_id,))
    rows = c.fetchall()
    conn.close()
    if not rows:
        return 0
    wins = sum(1 for r in rows if r[0] == 'win')
    return round((wins / len(rows)) * 100, 2)

def get_global_feedback():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT feedback_score, feedback_text, username FROM signals WHERE feedback_score IS NOT NULL ORDER BY id DESC LIMIT 20')
    rows = c.fetchall()
    conn.close()
    return rows
