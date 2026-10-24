"""Минимальный PostgREST-подобный клиент поверх psycopg для тестов job.

Покрывает цепочки .table().select/update/insert.eq.in_.order.limit.execute(),
которыми пользуется staff_document_check / lifecycle. Не production-клиент.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


def _adapt(value: Any) -> Any:
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list) and value and isinstance(value[0], dict):
        return json.dumps(value, ensure_ascii=False)
    return value


@dataclass
class _ExecResult:
    data: list[dict[str, Any]]


@dataclass
class _Query:
    conn: Any
    table: str
    action: str = "select"
    columns: str = "*"
    payload: dict[str, Any] | None = None
    filters: list[tuple[str, str, Any]] = field(default_factory=list)
    order_col: str | None = None
    order_desc: bool = False
    limit_n: int | None = None

    def select(self, columns: str = "*") -> _Query:
        self.action = "select"
        self.columns = columns
        return self

    def insert(self, payload: dict[str, Any]) -> _Query:
        self.action = "insert"
        self.payload = dict(payload)
        return self

    def update(self, payload: dict[str, Any]) -> _Query:
        self.action = "update"
        self.payload = dict(payload)
        return self

    def eq(self, col: str, value: Any) -> _Query:
        self.filters.append(("eq", col, value))
        return self

    def in_(self, col: str, values: list[Any]) -> _Query:
        self.filters.append(("in", col, list(values)))
        return self

    def order(self, col: str, desc: bool = False) -> _Query:
        self.order_col = col
        self.order_desc = desc
        return self

    def limit(self, n: int) -> _Query:
        self.limit_n = n
        return self

    def _where_sql(self) -> tuple[str, list[Any]]:
        parts: list[str] = []
        args: list[Any] = []
        for kind, col, val in self.filters:
            if kind == "eq":
                parts.append(f"{col} = %s")
                args.append(val)
            elif kind == "in":
                if not val:
                    parts.append("FALSE")
                else:
                    placeholders = ", ".join(["%s"] * len(val))
                    parts.append(f"{col} IN ({placeholders})")
                    args.extend(val)
        if not parts:
            return "", args
        return " WHERE " + " AND ".join(parts), args

    def execute(self) -> _ExecResult:
        where, args = self._where_sql()
        with self.conn.cursor() as cur:
            if self.action == "select":
                cols = self.columns if self.columns != "*" else "*"
                sql = f"SELECT {cols} FROM {self.table}{where}"
                if self.order_col:
                    sql += f" ORDER BY {self.order_col} {'DESC' if self.order_desc else 'ASC'}"
                if self.limit_n is not None:
                    sql += f" LIMIT {int(self.limit_n)}"
                cur.execute(sql, args)
                rows = cur.fetchall()
                colnames = [d.name for d in cur.description] if cur.description else []
                data = [_row_to_dict(colnames, r) for r in rows]
                return _ExecResult(data=data)

            if self.action == "insert":
                assert self.payload is not None
                cols = list(self.payload.keys())
                vals = [_adapt(self.payload[c]) for c in cols]
                # jsonb columns
                placeholders = []
                for c, _v in zip(cols, vals, strict=True):
                    if c in {"result", "flags"} and isinstance(
                        self.payload[c], (dict, list)
                    ):
                        placeholders.append("%s::jsonb")
                    else:
                        placeholders.append("%s")
                sql = (
                    f"INSERT INTO {self.table} ({', '.join(cols)}) "
                    f"VALUES ({', '.join(placeholders)}) RETURNING *"
                )
                cur.execute(sql, vals)
                row = cur.fetchone()
                colnames = [d.name for d in cur.description]
                self.conn.commit()
                return _ExecResult(data=[_row_to_dict(colnames, row)] if row else [])

            if self.action == "update":
                assert self.payload is not None
                sets = []
                set_args: list[Any] = []
                for c, v in self.payload.items():
                    if c in {"result", "flags"} and isinstance(v, (dict, list)):
                        sets.append(f"{c} = %s::jsonb")
                        set_args.append(json.dumps(v, ensure_ascii=False))
                    else:
                        sets.append(f"{c} = %s")
                        set_args.append(v)
                sql = (
                    f"UPDATE {self.table} SET {', '.join(sets)}{where} RETURNING *"
                )
                cur.execute(sql, set_args + args)
                rows = cur.fetchall()
                colnames = [d.name for d in cur.description] if cur.description else []
                self.conn.commit()
                return _ExecResult(data=[_row_to_dict(colnames, r) for r in rows])

        raise RuntimeError(f"unsupported action {self.action}")


def _row_to_dict(colnames: list[str], row: Any) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for i, name in enumerate(colnames):
        val = row[i]
        if isinstance(val, UUID):
            val = str(val)
        elif hasattr(val, "isoformat"):
            val = val.isoformat()
        out[name] = val
    return out


class PgRestShim:
    def __init__(self, conn: Any) -> None:
        self._conn = conn

    def table(self, name: str) -> _Query:
        return _Query(conn=self._conn, table=name)
