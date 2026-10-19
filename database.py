import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple, Iterator

DB_NAME = "navigator.db"


@contextmanager
def get_db_connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


def init_db():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS routes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_name TEXT DEFAULT 'Ivan',
                user_type TEXT DEFAULT 'driver',
                start_point TEXT NOT NULL,
                finish_point TEXT NOT NULL,
                route TEXT NOT NULL,
                distance REAL NOT NULL,
                time REAL NOT NULL,
                traffic REAL DEFAULT 1.0,
                actual_time REAL,
                actual_distance REAL,
                created_at TEXT NOT NULL
            );
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_routes_points ON routes (start_point, finish_point);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_routes_user ON routes (user_name);")
        conn.commit()


def save_route(
    start_point: str,
    finish_point: str,
    route: str,
    distance: float,
    time: float,
    traffic: float = 1.0,
    user_name: str = "Ivan",
    user_type: str = "driver",
    actual_time: Optional[float] = None,
    actual_distance: Optional[float] = None,
    created_at: Optional[str] = None
) -> int:
    if created_at is None:
        created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO routes (
                user_name, user_type, start_point, finish_point,
                route, distance, time, traffic,
                actual_time, actual_distance, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            user_name,
            user_type,
            start_point.upper().strip(),
            finish_point.upper().strip(),
            route.strip(),
            round(distance, 2),
            round(time, 2),
            round(traffic, 2),
            round(actual_time, 2) if actual_time is not None else None,
            round(actual_distance, 2) if actual_distance is not None else None,
            created_at
        ))
        conn.commit()
        return cursor.lastrowid


def update_actual_trip(route_id: int, actual_time: float, actual_distance: Optional[float] = None) -> bool:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if actual_distance is not None:
            cursor.execute("""
                UPDATE routes
                SET actual_time = ?, actual_distance = ?
                WHERE id = ?
            """, (round(actual_time, 2), round(actual_distance, 2), route_id))
        else:
            cursor.execute("""
                UPDATE routes
                SET actual_time = ?,
                    actual_distance = CASE WHEN actual_distance IS NULL THEN distance ELSE actual_distance END
                WHERE id = ?
            """, (round(actual_time, 2), route_id))
        conn.commit()
        return cursor.rowcount > 0


def get_route_by_id(route_id: int) -> Optional[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM routes WHERE id = ?", (route_id,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_recent_routes(limit: int = 20) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM routes
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def get_pending_routes(limit: int = 10) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM routes
            WHERE actual_time IS NULL
            ORDER BY id DESC
            LIMIT ?
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]


def get_route_stats_for_pair(start_point: str, finish_point: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                route,
                COUNT(*) AS total_count,
                COUNT(actual_time) AS completed_count,
                AVG(distance) AS avg_expected_distance,
                AVG(time) AS avg_expected_time,
                AVG(actual_time) AS avg_actual_time,
                AVG(actual_distance) AS avg_actual_distance,
                MIN(actual_time) AS min_actual_time,
                MAX(actual_time) AS max_actual_time
            FROM routes
            WHERE start_point = ? AND finish_point = ?
            GROUP BY route
            ORDER BY total_count DESC, avg_actual_time ASC
        """, (start_point.upper().strip(), finish_point.upper().strip()))

        results = []
        for row in cursor.fetchall():
            d = dict(row)
            d["total_count"] = d["total_count"] or 0
            d["completed_count"] = d["completed_count"] or 0
            d["avg_expected_time"] = round(d["avg_expected_time"], 1) if d["avg_expected_time"] else None
            d["avg_expected_distance"] = round(d["avg_expected_distance"], 1) if d["avg_expected_distance"] else None
            d["avg_actual_time"] = round(d["avg_actual_time"], 1) if d["avg_actual_time"] else None
            d["avg_actual_distance"] = round(d["avg_actual_distance"], 1) if d["avg_actual_distance"] else None
            if d["avg_actual_time"] and d["avg_expected_time"]:
                d["time_difference"] = round(d["avg_actual_time"] - d["avg_expected_time"], 1)
                d["delay_percent"] = round(((d["avg_actual_time"] - d["avg_expected_time"]) / d["avg_expected_time"]) * 100, 1)
            else:
                d["time_difference"] = 0.0
                d["delay_percent"] = 0.0
            results.append(d)
        return results


def get_user_stats_for_pair(user_name: str, start_point: str, finish_point: str) -> List[Dict[str, Any]]:
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                route,
                user_name,
                user_type,
                COUNT(*) AS user_count,
                COUNT(actual_time) AS completed_count,
                AVG(actual_time) AS avg_actual_time,
                AVG(time) AS avg_expected_time
            FROM routes
            WHERE user_name = ? AND start_point = ? AND finish_point = ?
            GROUP BY route
        """, (user_name, start_point.upper().strip(), finish_point.upper().strip()))
        return [dict(row) for row in cursor.fetchall()]


def get_overall_statistics() -> Dict[str, Any]:
    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                COUNT(*) AS total_records,
                COUNT(actual_time) AS completed_trips,
                AVG(distance) AS avg_distance,
                AVG(time) AS avg_predicted_time,
                AVG(actual_distance) AS avg_actual_distance,
                AVG(actual_time) AS avg_actual_time,
                AVG(actual_time - time) AS avg_time_diff
            FROM routes
        """)
        totals = dict(cursor.fetchone() or {})

        cursor.execute("""
            SELECT
                route,
                start_point,
                finish_point,
                COUNT(*) AS usage_count,
                COUNT(actual_time) AS actual_count,
                AVG(actual_time) AS avg_actual_time,
                AVG(time) AS avg_predicted_time
            FROM routes
            GROUP BY route
            ORDER BY usage_count DESC
            LIMIT 5
        """)
        popular_routes = [dict(row) for row in cursor.fetchall()]

        cursor.execute("""
            SELECT route, start_point, finish_point, AVG(actual_time) as avg_act
            FROM routes
            WHERE actual_time IS NOT NULL
            GROUP BY route
            ORDER BY avg_act ASC
            LIMIT 1
        """)
        fastest_row = cursor.fetchone()
        fastest_route = dict(fastest_row) if fastest_row else None

        cursor.execute("""
            SELECT route, start_point, finish_point, AVG(actual_time) as avg_act
            FROM routes
            WHERE actual_time IS NOT NULL
            GROUP BY route
            ORDER BY avg_act DESC
            LIMIT 1
        """)
        slowest_row = cursor.fetchone()
        slowest_route = dict(slowest_row) if slowest_row else None

        cursor.execute("""
            SELECT
                user_type,
                COUNT(*) AS trip_count,
                AVG(actual_time) AS avg_time,
                AVG(actual_distance) AS avg_dist
            FROM routes
            WHERE actual_time IS NOT NULL
            GROUP BY user_type
        """)
        user_types_stats = [dict(row) for row in cursor.fetchall()]

        return {
            "totals": totals,
            "popular_routes": popular_routes,
            "fastest_route": fastest_route,
            "slowest_route": slowest_route,
            "user_types_stats": user_types_stats
        }


def clear_database():
    with get_db_connection() as conn:
        conn.execute("DELETE FROM routes;")
        conn.commit()
