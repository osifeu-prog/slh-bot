import sqlite3
import time
import json
import os

class MemoryCore:
    def __init__(self, db_path="slh_memory.db"):
        self.db = sqlite3.connect(db_path, check_same_thread=False)
        self._init_db()

    def _init_db(self):
        cur = self.db.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts REAL,
            user TEXT,
            event_type TEXT,
            payload TEXT
        )
        """)

        cur.execute("""
        CREATE TABLE IF NOT EXISTS agent_stats (
            agent TEXT,
            score REAL,
            ts REAL
        )
        """)

        self.db.commit()

    def log_event(self, user, event_type, payload):
        cur = self.db.cursor()
        cur.execute(
            "INSERT INTO events (ts, user, event_type, payload) VALUES (?,?,?,?)",
            (time.time(), user, event_type, json.dumps(payload))
        )
        self.db.commit()

    def get_user_events(self, user):
        cur = self.db.cursor()
        cur.execute("SELECT ts, event_type, payload FROM events WHERE user=? ORDER BY ts DESC", (user,))
        return cur.fetchall()

    def log_agent(self, agent, score):
        cur = self.db.cursor()
        cur.execute(
            "INSERT INTO agent_stats VALUES (?,?,?)",
            (agent, score, time.time())
        )
        self.db.commit()

    def top_agents(self):
        cur = self.db.cursor()
        cur.execute("""
            SELECT agent, AVG(score) as avg_score
            FROM agent_stats
            GROUP BY agent
            ORDER BY avg_score DESC
        """)
        return cur.fetchall()
