import psycopg

conn = psycopg.connect("postgresql://postgres:mysecretpassword@localhost:5432/mydb")
cur = conn.cursor()
cur.execute("select extname, extversion from pg_extension order by extname")
print("extensions:", cur.fetchall())
conn.close()
