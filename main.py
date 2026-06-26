from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:  # Local SQLite fallback can run without PostgreSQL deps.
    psycopg = None
    dict_row = None


ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.environ.get("PLANNER_DB_PATH", os.path.join(ROOT_DIR, "planner.db"))
DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("PLANNER_DATABASE_URL")
HOST = os.environ.get("PLANNER_HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", os.environ.get("PLANNER_PORT", "8000")))


DEFAULT_STATE: dict[str, Any] = {
    "workspaces": [
        {
            "id": "ws-1",
            "title": "Ажил",
            "icon": "💼",
            "createdAt": "2026-01-01T00:00:00",
            "boards": [
                {
                    "id": "board-1",
                    "title": "2026 - 1 улирал",
                    "color": "#5c3d8f",
                    "starred": False,
                    "createdAt": "2026-01-01T00:00:00",
                    "columns": [
                        {
                            "id": "col-1",
                            "title": "PROJECT&PRODUCT DEV.",
                            "cards": [
                                {"id": "card-1", "title": "+ ТӨСӨЛ/PROJECT", "isCategory": True},
                                {"id": "card-2", "title": "+ БҮТЭЭГДЭХҮҮН/PRODUCT", "isCategory": True},
                            ],
                        },
                        {
                            "id": "col-2",
                            "title": "CUSTOMER SERVICE/EXPERIENCE",
                            "collapsed": True,
                            "cards": [
                                {"id": "card-cs-1", "title": "Үйлчилгээний чанар", "isCategory": True},
                                {"id": "card-cs-2", "title": "Хэрэглэгчийн санал хүсэлт", "isCategory": True},
                            ],
                        },
                        {
                            "id": "col-3",
                            "title": "MARKETING/SALES",
                            "cards": [
                                {"id": "card-3", "title": "+НЭР ХҮНД, БРЭНД, БРЭНДИНГ", "isCategory": True},
                                {"id": "card-4", "title": "+ БОРЛУУЛАЛТ", "isCategory": True},
                                {"id": "card-5", "title": "+ СУВАГ АРЧИЛГАА", "isCategory": True},
                                {"id": "card-6", "title": "+ ИДЭВХЖҮҮЛЭЛТ", "isCategory": True},
                                {"id": "card-7", "title": "+ ТОГТМОЛ ТӨЛБӨРҮҮД", "isCategory": True},
                                {"id": "card-8", "title": "+ СУРГАЛТ", "isCategory": True},
                                {"id": "card-9", "title": "+ ХЯНАЛТ, ШАЛГАЛТ", "isCategory": True},
                            ],
                        },
                        {
                            "id": "col-4",
                            "title": "BRAND/DESIGN",
                            "cards": [
                                {"id": "card-10", "title": "+ КОМПАНИТ АЖИЛ", "isCategory": True},
                                {
                                    "id": "card-11",
                                    "title": "САР ШИНЭ 2026",
                                    "label": {"text": "Хийж байгаа", "color": "#eb5a46"},
                                    "image": "https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?w=400&h=200&fit=crop",
                                    "attachments": 1,
                                },
                                {"id": "card-12", "title": "+ НЭР ХҮНД, БРЭНД", "isCategory": True},
                                {
                                    "id": "card-13",
                                    "title": "OV PPT",
                                    "image": "https://images.unsplash.com/photo-1557804506-669a67965ba0?w=400&h=200&fit=crop&q=80",
                                    "attachments": 24,
                                },
                            ],
                        },
                        {
                            "id": "col-5",
                            "title": "CALLCENTER",
                            "collapsed": True,
                            "cards": [
                                {"id": "card-cc-1", "title": "Дуудлагын тайлан", "isCategory": True},
                            ],
                        },
                        {"id": "col-6", "title": "MEETING", "collapsed": True, "cards": []},
                    ],
                }
            ],
        }
    ],
    "boardAccessMap": {
        "board-1": {
            "adminIds": ["1001"],
            "memberIds": ["1002", "1003"],
        }
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def get_sqlite_connection() -> sqlite3.Connection:
    db_dir = os.path.dirname(os.path.abspath(DB_PATH))
    if db_dir:
        os.makedirs(db_dir, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_postgres_connection():
    if psycopg is None:
        raise RuntimeError(
            "DATABASE_URL is set, but psycopg is not installed. "
            "Run `pip install -r requirements.txt` before starting the backend."
        )
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL is not configured.")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def using_postgres() -> bool:
    return bool(DATABASE_URL)


def init_sqlite_db() -> None:
    with get_sqlite_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS planner_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                state_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        row = conn.execute("SELECT id FROM planner_state WHERE id = 1").fetchone()
        if row is None:
            state_json = json.dumps(DEFAULT_STATE, ensure_ascii=False)
            timestamp = now_iso()
            conn.execute(
                """
                INSERT INTO planner_state (id, state_json, created_at, updated_at)
                VALUES (1, ?, ?, ?)
                """,
                (state_json, timestamp, timestamp),
            )


def init_postgres_db() -> None:
    with get_postgres_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS planner_state (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                state_json TEXT NOT NULL,
                created_at TIMESTAMPTZ NOT NULL,
                updated_at TIMESTAMPTZ NOT NULL
            )
            """
        )
        row = conn.execute("SELECT id FROM planner_state WHERE id = 1").fetchone()
        if row is None:
            state_json = json.dumps(DEFAULT_STATE, ensure_ascii=False)
            timestamp = now_iso()
            conn.execute(
                """
                INSERT INTO planner_state (id, state_json, created_at, updated_at)
                VALUES (1, %s, %s, %s)
                """,
                (state_json, timestamp, timestamp),
            )


def init_db() -> None:
    if using_postgres():
        init_postgres_db()
    else:
        init_sqlite_db()


def load_sqlite_state() -> dict[str, Any]:
    with get_sqlite_connection() as conn:
        row = conn.execute("SELECT state_json FROM planner_state WHERE id = 1").fetchone()
    if row is None:
        return DEFAULT_STATE
    return json.loads(row["state_json"])


def load_postgres_state() -> dict[str, Any]:
    with get_postgres_connection() as conn:
        row = conn.execute("SELECT state_json FROM planner_state WHERE id = 1").fetchone()
    if row is None:
        return DEFAULT_STATE
    return json.loads(row["state_json"])


def load_state() -> dict[str, Any]:
    if using_postgres():
        return load_postgres_state()
    return load_sqlite_state()


def save_sqlite_state(state: dict[str, Any]) -> dict[str, Any]:
    state_json = json.dumps(state, ensure_ascii=False)
    timestamp = now_iso()
    with get_sqlite_connection() as conn:
        conn.execute(
            """
            INSERT INTO planner_state (id, state_json, created_at, updated_at)
            VALUES (1, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
            """,
            (state_json, timestamp, timestamp),
        )
    return state


def save_postgres_state(state: dict[str, Any]) -> dict[str, Any]:
    state_json = json.dumps(state, ensure_ascii=False)
    timestamp = now_iso()
    with get_postgres_connection() as conn:
        conn.execute(
            """
            INSERT INTO planner_state (id, state_json, created_at, updated_at)
            VALUES (1, %s, %s, %s)
            ON CONFLICT(id) DO UPDATE SET
                state_json = excluded.state_json,
                updated_at = excluded.updated_at
            """,
            (state_json, timestamp, timestamp),
        )
    return state


def save_state(state: dict[str, Any]) -> dict[str, Any]:
    if using_postgres():
        return save_postgres_state(state)
    return save_sqlite_state(state)


def reset_state() -> dict[str, Any]:
    return save_state(DEFAULT_STATE)


def is_valid_state(payload: Any) -> bool:
    if not isinstance(payload, dict):
        return False
    if not isinstance(payload.get("workspaces"), list):
        return False
    if not isinstance(payload.get("boardAccessMap"), dict):
        return False
    return True


class PlannerRequestHandler(BaseHTTPRequestHandler):
    server_version = "PlannerBackend/1.0"

    def _send_json(self, status: int, payload: Any) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> Any:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return None
        raw_body = self.rfile.read(length)
        return json.loads(raw_body.decode("utf-8"))

    def do_OPTIONS(self) -> None:
        self._send_json(HTTPStatus.NO_CONTENT, {})

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/health":
            self._send_json(HTTPStatus.OK, {"ok": True, "dbPath": DB_PATH})
            return
        if path == "/api/state":
            self._send_json(HTTPStatus.OK, load_state())
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_PUT(self) -> None:
        path = urlparse(self.path).path
        if path != "/api/state":
            self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return
        try:
            payload = self._read_json()
        except json.JSONDecodeError:
            self._send_json(HTTPStatus.BAD_REQUEST, {"error": "Invalid JSON"})
            return
        if not is_valid_state(payload):
            self._send_json(
                HTTPStatus.BAD_REQUEST,
                {"error": "Expected payload with workspaces[] and boardAccessMap{}"},
            )
            return
        self._send_json(HTTPStatus.OK, save_state(payload))

    def do_DELETE(self) -> None:
        path = urlparse(self.path).path
        if path == "/api/state":
            self._send_json(HTTPStatus.OK, reset_state())
            return
        self._send_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def log_message(self, format: str, *args: Any) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] {self.address_string()} {format % args}")


def run() -> None:
    init_db()
    server = ThreadingHTTPServer((HOST, PORT), PlannerRequestHandler)
    print(f"Planner backend running at http://{HOST}:{PORT}")
    print(f"SQLite database: {DB_PATH}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping planner backend")
    finally:
        server.server_close()


if __name__ == "__main__":
    run()
