from __future__ import annotations
import sqlite3
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional
import pandas as pd

class DBTools:
    def __init__(self, db_path: str | Path = "data/db/api_index.db"):
        self.db_path = str(db_path)
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.db_path)
        self.con.execute("PRAGMA foreign_keys=ON;")

    # --- basic ---
    def close(self) -> None:
        try: self.con.close()
        except Exception: pass

    def tables(self) -> list[str]:
        q = "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"
        return [r[0] for r in self.con.execute(q).fetchall()]

    def schema(self, table: str) -> str:
        q = "SELECT sql FROM sqlite_master WHERE type='table' AND name=?;"
        row = self.con.execute(q, (table,)).fetchone()
        if not row: raise ValueError(f"table not found: {table}")
        return row[0]

    def count(self, table: str) -> int:
        return int(self.con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])

    # --- read as DataFrame ---
    def read_table(self, table: str, limit: Optional[int] = None) -> pd.DataFrame:
        q = f"SELECT * FROM {table}" + (f" LIMIT {int(limit)}" if limit else "")
        return pd.read_sql_query(q, self.con)

    def read_sql(self, sql: str, params: Optional[Mapping[str, Any]] = None) -> pd.DataFrame:
        return pd.read_sql_query(sql, self.con, params=params or {})

    def to_dataframes(self) -> dict[str, pd.DataFrame]:
        return {t: self.read_table(t) for t in self.tables()}

    # --- write / modify ---
    def execute(self, sql: str, params: Iterable[Any] | Mapping[str, Any] | None = None) -> None:
        self.con.execute(sql, params or [])
        self.con.commit()

    def insert_row(self, table: str, row: Mapping[str, Any]) -> int:
        cols = list(row.keys())
        placeholders = ",".join([":" + c for c in cols])
        sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
        cur = self.con.execute(sql, row)
        self.con.commit()
        return cur.lastrowid

    def insert_many(self, table: str, rows: Iterable[Mapping[str, Any]]) -> int:
        rows = list(rows)
        if not rows: return 0
        cols = list(rows[0].keys())
        placeholders = ",".join([":" + c for c in cols])
        sql = f"INSERT INTO {table} ({','.join(cols)}) VALUES ({placeholders})"
        self.con.executemany(sql, rows)
        self.con.commit()
        return len(rows)

    def upsert(self, table: str, rows: Iterable[Mapping[str, Any]], unique_cols: list[str]) -> int:
        rows = list(rows)
        if not rows: return 0
        cols = list(rows[0].keys())
        non_keys = [c for c in cols if c not in unique_cols]
        insert_cols = ",".join(cols)
        insert_vals = ",".join([":" + c for c in cols])
        updates = ",".join([f"{c}=excluded.{c}" for c in non_keys])
        sql = (
            f"INSERT INTO {table} ({insert_cols}) VALUES ({insert_vals}) "
            f"ON CONFLICT ({','.join(unique_cols)}) DO UPDATE SET {updates}"
        )
        self.con.executemany(sql, rows)
        self.con.commit()
        return len(rows)

    # --- maintenance / export ---
    def integrity_check(self) -> str:
        row = self.con.execute("PRAGMA integrity_check;").fetchone()
        return row[0]

    def vacuum(self) -> None:
        self.con.execute("VACUUM;")

    def export_csv(self, table: str, csv_path: str | Path) -> Path:
        df = self.read_table(table)
        csv_path = Path(csv_path)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(csv_path, index=False)
        return csv_path
