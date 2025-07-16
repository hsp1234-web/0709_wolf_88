import duckdb

con = duckdb.connect('data/analytics_warehouse/factors.duckdb')
res = con.execute("SELECT ticker, COUNT(*) FROM universal_factors GROUP BY ticker").fetchall()
print(res)
con.close()
