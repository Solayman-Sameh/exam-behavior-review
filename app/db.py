import sqlite3
from contextlib import contextmanager
from pathlib import Path


class AlertDatabase:
    def __init__(self, db_path):
        self.path = Path(db_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.create_tables()

    @contextmanager
    def _connect(self):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def create_tables(self):
        with self._connect() as db:
            db.execute('''CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT UNIQUE NOT NULL,
                run_id TEXT NOT NULL, video_filename TEXT NOT NULL,
                track_id INTEGER NOT NULL, behavior_type TEXT NOT NULL,
                confidence REAL NOT NULL, evidence TEXT NOT NULL,
                video_time_s REAL NOT NULL, wall_time TEXT NOT NULL,
                screenshot_path TEXT NOT NULL)''')

    def insert_alert(self, event):
        fields = ('event_id','run_id','video_filename','track_id','behavior_type',
                  'confidence','evidence','video_time_s','wall_time','screenshot_path')
        with self._connect() as db:
            cursor = db.execute(f"INSERT INTO alerts ({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                                [event[k] for k in fields])
            return cursor.lastrowid

    def get_alerts(self, limit=100, offset=0):
        with self._connect() as db:
            return [dict(row) for row in db.execute('SELECT * FROM alerts ORDER BY id DESC LIMIT ? OFFSET ?', (limit,offset))]

    def get_alert_by_id(self, alert_id):
        with self._connect() as db:
            row = db.execute('SELECT * FROM alerts WHERE id=?', (alert_id,)).fetchone()
            return dict(row) if row else None

    def clear_alerts(self):
        with self._connect() as db:
            db.execute('DELETE FROM alerts')

