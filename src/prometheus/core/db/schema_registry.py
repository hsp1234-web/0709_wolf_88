import sqlite3
from pathlib import Path
from typing import Set


class SchemaRegistry:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self._create_table()

    def _create_table(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS schema_registry (
                    format_fingerprint TEXT PRIMARY KEY,
                    header TEXT,
                    encoding TEXT,
                    file_count INTEGER DEFAULT 1,
                    first_seen_file TEXT
                )
            """)

    def add_or_update_schema(self, fingerprint: str, header: str, encoding: str, filename: str):
        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT file_count FROM schema_registry WHERE format_fingerprint = ?",
                (fingerprint,),
            )
            existing = cursor.fetchone()

            if existing:
                new_count = existing[0] + 1
                cursor.execute(
                    "UPDATE schema_registry SET file_count = ? WHERE format_fingerprint = ?",
                    (new_count, fingerprint),
                )
                return "updated"
            else:
                cursor.execute(
                    "INSERT INTO schema_registry VALUES (?, ?, ?, 1, ?)",
                    (fingerprint, header, encoding, filename),
                )
                return "new"

    def get_known_fingerprints(self) -> Set[str]:
        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute("SELECT format_fingerprint FROM schema_registry")
            return {row[0] for row in cursor.fetchall()}

    def get_all_schemas(self) -> dict:
        with self.conn:
            cursor = self.conn.cursor()
            cursor.execute("SELECT format_fingerprint, header, encoding FROM schema_registry")
            return {row[0]: (row[1], row[2]) for row in cursor.fetchall()}

    def close(self):
        self.conn.close()
