import psycopg

conn = psycopg.connect("postgresql://postgres:mysecretpassword@localhost:5432/mydb")
cur = conn.cursor()
cur.execute("select email, left(password_hash, 22) from users order by email")
print("users:", cur.fetchall())
cur.execute("select u.email, m.role from memberships m join users u on u.id = m.user_id order by m.role")
print("memberships:", cur.fetchall())
cur.execute("select name from organizations")
print("organizations:", cur.fetchall())
cur.execute("select count(*) from knowledge_bases")
print("knowledge_bases count:", cur.fetchone()[0])
conn.close()
