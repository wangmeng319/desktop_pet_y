import sqlite3
from contextlib import closing
from pathlib import Path

from PySide6.QtCore import QStandardPaths


class ChatMemory:
    def __init__(self):
        location = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        if not location:
            raise OSError("No application data location")
        folder = Path(location)
        folder.mkdir(parents=True, exist_ok=True)
        self.path = folder / "chat-history.sqlite3"
        with closing(self.connect()) as db, db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL
                )
            """)

    def connect(self):
        return sqlite3.connect(self.path, timeout=0.5)

    def read(self):
        with closing(self.connect()) as db:
            return db.execute("SELECT question, answer FROM turns ORDER BY id").fetchall()

    def append(self, question, answer):
        with closing(self.connect()) as db, db:
            db.execute("INSERT INTO turns (question, answer) VALUES (?, ?)", (question, answer))

    def clear(self):
        with closing(self.connect()) as db, db:
            db.execute("PRAGMA secure_delete = ON")
            db.execute("DELETE FROM turns")
