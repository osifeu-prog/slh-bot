import sqlite3
import json

DB_NAME = 'slh_empire.db'

def show_system_wallets():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT user_id, wallet_balance FROM wallets ORDER BY wallet_balance DESC")
    users = c.fetchall()
    conn.close()

    print("\n=== יתרות במערכת SLH EMPIRE ===")
    total = 0
    for u in users:
        print(f"{u[0]}: {u[1]} SLH")
        total += u[1]
    print(f"סהכ: {total} SLH | משתמשים: {len(users)}")
    return users

def add_user_from_binance(user_id, balance):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO wallets VALUES (?,?)", (user_id, balance))
    conn.commit()
    conn.close()
    print(f"הוסף: {user_id} עם {balance} SLH")

if __name__ == "__main__":
    show_system_wallets()
    print("\nכדי להוסיף משתמש מבייננס: add_user_from_binance('USER_ID', 500)")
