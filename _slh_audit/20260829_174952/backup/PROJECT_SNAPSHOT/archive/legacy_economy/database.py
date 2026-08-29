import sqlite3
DB_NAME = 'slh_empire.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS wallets
                 (user_id TEXT PRIMARY KEY, wallet_balance INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS academy_courses
                 (course_id TEXT PRIMARY KEY, title TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS academy_progress
                 (user_id TEXT, course_id TEXT, completed INTEGER)''')
    c.execute('''CREATE TABLE IF NOT EXISTS votes
                 (vote_id TEXT PRIMARY KEY, title TEXT, status TEXT)''')
    c.execute("INSERT OR IGNORE INTO wallets VALUES ('OWNER', 1000)")
    c.execute("INSERT OR IGNORE INTO academy_courses VALUES ('bitcoin_101', 'ביטקוין 101')")
    conn.commit()
    conn.close()

init_db()
print("DB Initialized")
