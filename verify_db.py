import duckdb

con = duckdb.connect('data/analytics_warehouse/factors.duckdb')
res = con.execute("SELECT ticker, COUNT(*) FROM bond_specific_factors GROUP BY ticker").fetchall()
print(res)
con.close()
