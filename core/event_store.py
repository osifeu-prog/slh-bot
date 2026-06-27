import sqlite3, json, time, threading

class EventStore:
    def __init__(self, db_path="events.db"):
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.lock = threading.Lock()
        self._init()

    def _init(self):
        cur = self.conn.cursor()
        cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            event TEXT,
            payload TEXT,
            status TEXT DEFAULT 'pending',
            created_at REAL
        )
        """)
        self.conn.commit()

    def add(self, event, payload):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "INSERT INTO events(event,payload,created_at) VALUES (?,?,?)",
                (event, json.dumps(payload), time.time())
            )
            self.conn.commit()

    def fetch_batch(self, limit=10):
        with self.lock:
            cur = self.conn.cursor()
            cur.execute(
                "SELECT id, event, payload FROM events WHERE status='pending' ORDER BY id LIMIT ?",
                (limit,)
            )
            rows = cur.fetchall()
            ids = [r[0] for r in rows]
            if ids:
                cur.executemany(
                    "UPDATE events SET status='processing' WHERE id=?",
                    [(i,) for i in ids]
                )
                self.conn.commit()
            return rows

    def mark_done(self, event_id):
        with self.lock:
            self.conn.execute("UPDATE events SET status='done' WHERE id=?", (event_id,))
            self.conn.commit()
