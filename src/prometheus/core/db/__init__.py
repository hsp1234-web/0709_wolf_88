import duckdb

def get_db_connection(db_path):
    return duckdb.connect(database=db_path, read_only=False)
