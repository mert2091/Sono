"""
Geçmiş & Kütüphane Servisi.
SQLite veritabanı ile okunan belgelerin geçmişini saklar.
"""

import sqlite3
import threading
from datetime import datetime
from typing import List, Dict, Any

from utils.paths import HISTORY_DB_PATH

DB_PATH = str(HISTORY_DB_PATH)
_init_lock = threading.Lock()
_initialized = False


def init_db():
    """Veritabanını ve tabloları ilk çağrıda oluşturur; eksik sütunları güvenle ekler."""
    global _initialized
    if _initialized:
        return
    with _init_lock:
        if _initialized:
            return
        conn = sqlite3.connect(DB_PATH)
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    text_content TEXT,
                    translation_content TEXT,
                    source_type TEXT,
                    word_count INTEGER,
                    created_at TEXT,
                    last_paragraph INTEGER DEFAULT 0,
                    total_paragraphs INTEGER DEFAULT 0
                )
            """)
            cursor.execute("PRAGMA table_info(history)")
            existing_cols = {row[1] for row in cursor.fetchall()}
            if "last_paragraph" not in existing_cols:
                cursor.execute("ALTER TABLE history ADD COLUMN last_paragraph INTEGER DEFAULT 0")
            if "total_paragraphs" not in existing_cols:
                cursor.execute("ALTER TABLE history ADD COLUMN total_paragraphs INTEGER DEFAULT 0")
            conn.commit()
            _initialized = True
        finally:
            conn.close()


def update_history_progress(item_id: int, last_paragraph: int, total_paragraphs: int = 0) -> None:
    """Belgenin kaldığı son paragraf indeksini SQLite'a kaydeder."""
    if not item_id or item_id < 0:
        return
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE history SET last_paragraph = ?, total_paragraphs = ? WHERE id = ?",
        (max(0, int(last_paragraph)), max(0, int(total_paragraphs)), int(item_id)),
    )
    conn.commit()
    conn.close()


def add_history_entry(title: str, text: str, translation: str = "", source_type: str = "Görsel") -> int:
    """Yeni bir okuma kaydını veritabanına ekler."""
    if not text or not text.strip():
        return -1

    init_db()
    words = len(text.strip().split())
    created = datetime.now().strftime("%d.%m.%Y %H:%M")
    clean_title = (title[:40] + "...") if len(title) > 40 else title

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO history (title, text_content, translation_content, source_type, word_count, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (clean_title, text, translation, source_type, words, created))
    item_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return item_id


def get_all_history(limit: int = 40) -> List[Dict[str, Any]]:
    """Tüm geçmiş kayıtları en yeniden eskiye doğru listeler."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,))
    rows = cursor.fetchall()
    results = [dict(row) for row in rows]
    conn.close()
    return results


def delete_history_entry(item_id: int):
    """Belirtilen kaydı siler."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history WHERE id = ?", (item_id,))
    conn.commit()
    conn.close()


def clear_all_history():
    """Tüm geçmişi temizler."""
    init_db()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM history")
    conn.commit()
    conn.close()
