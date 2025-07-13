import sqlite3

conn = sqlite3.connect("output/logs/session.sqlite")
cursor = conn.cursor()
cursor.execute("SELECT message FROM logs WHERE level = 'ERROR' ORDER BY timestamp DESC LIMIT 1")
result = cursor.fetchone()
if result:
    print(result[0])
else:
    print("No error logs found.")
conn.close()
