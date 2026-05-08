"""
WorkBuddy Backend Module
Handles all business logic: folder scanning, file organization, and database management

This module contains:
- Data models (FileRecord, ScanResult)
- Database operations (HistoryDB)
- Folder scanning (FolderScanner)
- File organization (Organizer)
- Utility functions for file handling

Key Design:
- Separation of concerns: UI-independent business logic
- Immutable data structures (frozen dataclasses) for thread safety
- SQLite for persistent history and undo capability
"""

from __future__ import annotations

import csv
import hashlib
import os
import shutil
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

APP_TITLE = "Folder Analyzer + Auto Organizer"
DB_FILENAME = "workbuddy_history.sqlite3"
QUARANTINE_DIRNAME = ".workbuddy_quarantine"


FILE_CATEGORIES: Dict[str, Tuple[str, ...]] = {
    "Images": (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tiff"),
    "Documents": (".pdf", ".doc", ".docx", ".ppt", ".pptx", ".txt", ".md"),
    "Spreadsheets": (".xls", ".xlsx", ".csv"),
    "Code": (".py", ".js", ".ts", ".java", ".c", ".cpp", ".html", ".css", ".json"),
    "Audio": (".mp3", ".wav", ".m4a", ".ogg", ".flac"),
    "Video": (".mp4", ".mov", ".mkv", ".avi", ".webm"),
    "Archives": (".zip", ".rar", ".7z", ".tar", ".gz"),
}


def now_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def human_bytes(num_bytes: int) -> str:
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(num_bytes)
    for u in units:
        if size < 1024 or u == units[-1]:
            if u == "B":
                return f"{int(size)} {u}"
            return f"{size:.2f} {u}"
        size /= 1024.0
    return f"{num_bytes} B"


def safe_relpath(path: Path, base: Path) -> str:
    try:
        return str(path.relative_to(base))
    except Exception:
        return str(path)


def category_for_extension(suffix: str) -> str:
    s = suffix.lower()
    for category, exts in FILE_CATEGORIES.items():
        if s in exts:
            return category
    if not s:
        return "No Extension"
    return "Other"


@dataclass(frozen=True)
class FileRecord:
    name: str
    rel_path: str
    ext: str
    category: str
    size_bytes: int
    modified_iso: str


@dataclass(frozen=True)
class ScanResult:
    folder: str
    recursive: bool
    include_hidden: bool
    started_at_iso: str
    finished_at_iso: str
    file_count: int
    total_size_bytes: int
    records: Tuple[FileRecord, ...]

    @property
    def total_size_human(self) -> str:
        return human_bytes(self.total_size_bytes)


class HistoryDB:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _init_db(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS scans (
                    scan_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    folder TEXT NOT NULL,
                    recursive INTEGER NOT NULL,
                    include_hidden INTEGER NOT NULL,
                    started_at TEXT NOT NULL,
                    finished_at TEXT NOT NULL,
                    file_count INTEGER NOT NULL,
                    total_size_bytes INTEGER NOT NULL
                );
                CREATE TABLE IF NOT EXISTS files (
                    file_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scan_id INTEGER NOT NULL,
                    name TEXT NOT NULL,
                    rel_path TEXT NOT NULL,
                    ext TEXT NOT NULL,
                    category TEXT NOT NULL,
                    size_bytes INTEGER NOT NULL,
                    modified_iso TEXT NOT NULL,
                    FOREIGN KEY(scan_id) REFERENCES scans(scan_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_files_scan_id ON files(scan_id);
                CREATE INDEX IF NOT EXISTS idx_files_category ON files(category);

                CREATE TABLE IF NOT EXISTS organize_ops (
                    op_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    base_folder TEXT NOT NULL,
                    applied_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS organize_moves (
                    move_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    op_id INTEGER NOT NULL,
                    src_rel_path TEXT NOT NULL,
                    dest_rel_path TEXT NOT NULL,
                    FOREIGN KEY(op_id) REFERENCES organize_ops(op_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_organize_ops_base ON organize_ops(base_folder);
                CREATE INDEX IF NOT EXISTS idx_organize_moves_op ON organize_moves(op_id);

                CREATE TABLE IF NOT EXISTS quarantine_ops (
                    qop_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    base_folder TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT ''
                );
                CREATE TABLE IF NOT EXISTS quarantine_items (
                    item_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    qop_id INTEGER NOT NULL,
                    src_rel_path TEXT NOT NULL,
                    quarantine_rel_path TEXT NOT NULL,
                    FOREIGN KEY(qop_id) REFERENCES quarantine_ops(qop_id) ON DELETE CASCADE
                );
                CREATE INDEX IF NOT EXISTS idx_quarantine_ops_base ON quarantine_ops(base_folder);
                CREATE INDEX IF NOT EXISTS idx_quarantine_items_qop ON quarantine_items(qop_id);
                """
            )

    def save_scan(self, result: ScanResult) -> int:
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO scans(folder, recursive, include_hidden, started_at, finished_at, file_count, total_size_bytes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.folder,
                    int(result.recursive),
                    int(result.include_hidden),
                    result.started_at_iso,
                    result.finished_at_iso,
                    result.file_count,
                    result.total_size_bytes,
                ),
            )
            scan_id = int(cur.lastrowid)
            cur.executemany(
                """
                INSERT INTO files(scan_id, name, rel_path, ext, category, size_bytes, modified_iso)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        scan_id,
                        r.name,
                        r.rel_path,
                        r.ext,
                        r.category,
                        r.size_bytes,
                        r.modified_iso,
                    )
                    for r in result.records
                ],
            )
            return scan_id

    def list_recent_scans(self, limit: int = 10) -> List[Tuple[int, str, str, int, int]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT scan_id, folder, finished_at, file_count, total_size_bytes
                FROM scans
                ORDER BY scan_id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [(int(r[0]), str(r[1]), str(r[2]), int(r[3]), int(r[4])) for r in rows]

    def list_scans_for_folder(self, *, folder: str, limit: int = 60) -> List[Tuple[int, str, int, int]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT scan_id, finished_at, file_count, total_size_bytes
                FROM scans
                WHERE folder = ?
                ORDER BY scan_id DESC
                LIMIT ?
                """,
                (folder, limit),
            ).fetchall()
        return [(int(r[0]), str(r[1]), int(r[2]), int(r[3])) for r in rows]

    def get_scan_header(self, scan_id: int) -> Optional[Tuple[int, str, str, int, int]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT scan_id, folder, finished_at, file_count, total_size_bytes
                FROM scans
                WHERE scan_id = ?
                """,
                (scan_id,),
            ).fetchone()
        if not row:
            return None
        return (int(row[0]), str(row[1]), str(row[2]), int(row[3]), int(row[4]))

    def get_scan_files(self, scan_id: int) -> List[Tuple[str, str, str, int]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT rel_path, category, ext, size_bytes
                FROM files
                WHERE scan_id = ?
                """,
                (scan_id,),
            ).fetchall()
        return [(str(r[0]), str(r[1]), str(r[2]), int(r[3])) for r in rows]

    def save_organize_op(self, *, base_folder: str, moves: List[Tuple[str, str]]) -> int:
        if not moves:
            raise ValueError("No moves to save.")
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO organize_ops(base_folder, applied_at)
                VALUES (?, ?)
                """,
                (base_folder, now_iso()),
            )
            op_id = int(cur.lastrowid)
            cur.executemany(
                """
                INSERT INTO organize_moves(op_id, src_rel_path, dest_rel_path)
                VALUES (?, ?, ?)
                """,
                [(op_id, src, dest) for (src, dest) in moves],
            )
            return op_id

    def list_organize_ops(self, *, base_folder: str, limit: int = 50) -> List[Tuple[int, str, int]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT o.op_id, o.applied_at, COUNT(m.move_id) AS move_count
                FROM organize_ops o
                LEFT JOIN organize_moves m ON m.op_id = o.op_id
                WHERE o.base_folder = ?
                GROUP BY o.op_id, o.applied_at
                ORDER BY o.op_id DESC
                LIMIT ?
                """,
                (base_folder, limit),
            ).fetchall()
        return [(int(r[0]), str(r[1]), int(r[2])) for r in rows]

    def get_organize_op(self, op_id: int) -> Optional[Tuple[int, str, str, List[Tuple[str, str]]]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT op_id, base_folder, applied_at
                FROM organize_ops
                WHERE op_id = ?
                """,
                (op_id,),
            ).fetchone()
            if not row:
                return None
            base_folder = str(row[1])
            applied_at = str(row[2])
            moves_rows = conn.execute(
                """
                SELECT src_rel_path, dest_rel_path
                FROM organize_moves
                WHERE op_id = ?
                ORDER BY move_id ASC
                """,
                (op_id,),
            ).fetchall()
        moves = [(str(r[0]), str(r[1])) for r in moves_rows]
        return (int(row[0]), base_folder, applied_at, moves)

    def get_last_organize_op(self, *, base_folder: str) -> Optional[Tuple[int, str, List[Tuple[str, str]]]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT op_id, applied_at
                FROM organize_ops
                WHERE base_folder = ?
                ORDER BY op_id DESC
                LIMIT 1
                """,
                (base_folder,),
            ).fetchone()
            if not row:
                return None
            op_id = int(row[0])
            applied_at = str(row[1])
            moves_rows = conn.execute(
                """
                SELECT src_rel_path, dest_rel_path
                FROM organize_moves
                WHERE op_id = ?
                ORDER BY move_id ASC
                """,
                (op_id,),
            ).fetchall()
        moves = [(str(r[0]), str(r[1])) for r in moves_rows]
        return (op_id, applied_at, moves)

    def delete_organize_op(self, op_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM organize_ops WHERE op_id = ?", (op_id,))

    def save_quarantine_op(self, *, base_folder: str, items: List[Tuple[str, str]], note: str = "") -> int:
        if not items:
            raise ValueError("No quarantine items to save.")
        with self._connect() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO quarantine_ops(base_folder, created_at, note)
                VALUES (?, ?, ?)
                """,
                (base_folder, now_iso(), note or ""),
            )
            qop_id = int(cur.lastrowid)
            cur.executemany(
                """
                INSERT INTO quarantine_items(qop_id, src_rel_path, quarantine_rel_path)
                VALUES (?, ?, ?)
                """,
                [(qop_id, src, qrel) for (src, qrel) in items],
            )
            return qop_id

    def list_quarantine_ops(self, *, base_folder: str, limit: int = 50) -> List[Tuple[int, str, str, int]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT q.qop_id, q.created_at, q.note, COUNT(i.item_id) AS item_count
                FROM quarantine_ops q
                LEFT JOIN quarantine_items i ON i.qop_id = q.qop_id
                WHERE q.base_folder = ?
                GROUP BY q.qop_id, q.created_at, q.note
                ORDER BY q.qop_id DESC
                LIMIT ?
                """,
                (base_folder, limit),
            ).fetchall()
        return [(int(r[0]), str(r[1]), str(r[2]), int(r[3])) for r in rows]

    def get_quarantine_op(self, qop_id: int) -> Optional[Tuple[int, str, str, str, List[Tuple[str, str]]]]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT qop_id, base_folder, created_at, note
                FROM quarantine_ops
                WHERE qop_id = ?
                """,
                (qop_id,),
            ).fetchone()
            if not row:
                return None
            base_folder = str(row[1])
            created_at = str(row[2])
            note = str(row[3] or "")
            items_rows = conn.execute(
                """
                SELECT src_rel_path, quarantine_rel_path
                FROM quarantine_items
                WHERE qop_id = ?
                ORDER BY item_id ASC
                """,
                (qop_id,),
            ).fetchall()
        items = [(str(r[0]), str(r[1])) for r in items_rows]
        return (int(row[0]), base_folder, created_at, note, items)

    def delete_quarantine_op(self, qop_id: int) -> None:
        with self._connect() as conn:
            conn.execute("DELETE FROM quarantine_ops WHERE qop_id = ?", (qop_id,))


class FolderScanner:
    def scan(self, folder: Path, *, recursive: bool, include_hidden: bool) -> ScanResult:
        started = now_iso()
        records: List[FileRecord] = []
        total = 0

        if not folder.exists() or not folder.is_dir():
            raise ValueError("Selected folder does not exist or is not a directory.")

        iterator: Iterable[Path]
        if recursive:
            iterator = folder.rglob("*")
        else:
            iterator = folder.glob("*")

        for p in iterator:
            if p.is_dir():
                continue
            if not include_hidden and self._is_hidden(p):
                continue
            try:
                stat = p.stat()
            except OSError:
                # Some files might be locked; skip instead of crashing.
                continue

            ext = p.suffix.lower()
            cat = category_for_extension(ext)
            size = int(stat.st_size)
            total += size
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            records.append(
                FileRecord(
                    name=p.name,
                    rel_path=safe_relpath(p, folder),
                    ext=ext or "",
                    category=cat,
                    size_bytes=size,
                    modified_iso=modified,
                )
            )

        finished = now_iso()
        records.sort(key=lambda r: (r.category, r.ext, -r.size_bytes, r.rel_path.lower()))
        return ScanResult(
            folder=str(folder),
            recursive=recursive,
            include_hidden=include_hidden,
            started_at_iso=started,
            finished_at_iso=finished,
            file_count=len(records),
            total_size_bytes=total,
            records=tuple(records),
        )

    @staticmethod
    def _is_hidden(path: Path) -> bool:
        # Cross-platform "good enough": dotfile or Windows FILE_ATTRIBUTE_HIDDEN.
        if path.name.startswith("."):
            return True
        if os.name == "nt":
            try:
                import ctypes

                FILE_ATTRIBUTE_HIDDEN = 0x2
                attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
                if attrs == -1:
                    return False
                return bool(attrs & FILE_ATTRIBUTE_HIDDEN)
            except Exception:
                return False
        return False


class Organizer:
    def propose_moves(self, result: ScanResult, *, create_category_folders: bool) -> List[Tuple[Path, Path]]:
        base = Path(result.folder)
        proposed: List[Tuple[Path, Path]] = []
        for r in result.records:
            src = base / r.rel_path
            if create_category_folders:
                dest_dir = base / r.category
            else:
                dest_dir = base
            dest = dest_dir / r.name
            if src.resolve() == dest.resolve():
                continue
            proposed.append((src, dest))
        return proposed

    def propose_moves_rule(self, result: ScanResult, *, rule: str) -> List[Tuple[Path, Path]]:
        base = Path(result.folder)
        proposed: List[Tuple[Path, Path]] = []

        for r in result.records:
            # Safety: never re-organize quarantine contents
            if r.rel_path.replace("\\", "/").startswith(f"{QUARANTINE_DIRNAME}/") or r.rel_path == QUARANTINE_DIRNAME:
                continue

            src = base / r.rel_path
            if rule == "category":
                dest_dir = base / r.category
            elif rule == "date_ym":
                try:
                    dt = datetime.strptime(r.modified_iso, "%Y-%m-%d %H:%M:%S")
                    dest_dir = base / f"{dt.year:04d}" / f"{dt.month:02d}"
                except Exception:
                    dest_dir = base / "Unknown Date"
            elif rule == "category_ext":
                ext = (r.ext or "").lower().lstrip(".") or "no_ext"
                dest_dir = base / r.category / ext
            else:
                raise ValueError("Unknown rule")

            dest = dest_dir / r.name
            try:
                if src.resolve() == dest.resolve():
                    continue
            except Exception:
                # If resolve fails (permissions), still include move attempt.
                pass
            proposed.append((src, dest))

        return proposed

    def apply_moves(self, moves: List[Tuple[Path, Path]]) -> Tuple[List[Tuple[Path, Path]], int]:
        executed: List[Tuple[Path, Path]] = []
        moved = 0
        skipped = 0
        for src, dest in moves:
            try:
                dest.parent.mkdir(parents=True, exist_ok=True)
                final_dest = self._dedupe_destination(dest)
                shutil.move(str(src), str(final_dest))
                moved += 1
                executed.append((src, final_dest))
            except Exception:
                skipped += 1
        return executed, skipped

    @staticmethod
    def _dedupe_destination(dest: Path) -> Path:
        if not dest.exists():
            return dest
        stem = dest.stem
        suffix = dest.suffix
        parent = dest.parent
        for i in range(1, 9999):
            candidate = parent / f"{stem} ({i}){suffix}"
            if not candidate.exists():
                return candidate
        return parent / f"{stem} (copy){suffix}"
