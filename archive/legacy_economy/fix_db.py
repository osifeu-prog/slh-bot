import sqlite3
conn = sqlite3.connect('slh_empire.db')
c = conn.cursor()
c.execute('ALTER TABLE wallets ADD COLUMN chat_id INTEGER')
conn.commit()
conn.close()
print("DB עודכן")
