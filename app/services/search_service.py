"""Türkçe duyarlı arama yardımcıları.

SQLite'ın LIKE'ı yalnızca ASCII harflerde büyük/küçük harf bağımsızdır:
"şahin" araması "Şahin"i, "pinar" araması "Pınar"ı bulamaz. Burada hem
sorgu hem kolon değeri ortak bir ASCII iskelete indirgenir (İ/ı→i, Ş/ş→s,
Ğ/ğ→g, Ü/ü→u, Ö/ö→o, Ç/ç→c), böylece Türkçe karakterli isimler klavye
düzeninden bağımsız bulunur. SQLite bağlantılarına ``tr_fold`` fonksiyonu
otomatik kaydedilir; başka bir veritabanına geçilirse ``lower()`` tabanlı
yaklaşık davranışa düşülür.
"""

import sqlite3

from sqlalchemy import event, func
from sqlalchemy.engine import Engine

_FOLD_MAP = str.maketrans({
    "İ": "i", "I": "i", "ı": "i",
    "Ş": "s", "ş": "s",
    "Ğ": "g", "ğ": "g",
    "Ü": "u", "ü": "u",
    "Ö": "o", "ö": "o",
    "Ç": "c", "ç": "c",
    "Â": "a", "â": "a",
    "Î": "i", "î": "i",
    "Û": "u", "û": "u",
})


def tr_fold(value) -> str:
    """Metni aramaya uygun ASCII iskelete indirger (Türkçe harf eşlemesiyle)."""
    if value is None:
        return ""
    return str(value).translate(_FOLD_MAP).lower()


def _sqlite_tr_fold(value):
    if value is None:
        return None
    return tr_fold(value)


@event.listens_for(Engine, "connect")
def _register_sqlite_tr_fold(dbapi_connection, connection_record):
    if isinstance(dbapi_connection, sqlite3.Connection):
        dbapi_connection.create_function(
            "tr_fold", 1, _sqlite_tr_fold, deterministic=True
        )


def _is_sqlite() -> bool:
    from app.extensions import db

    return db.engine.dialect.name == "sqlite"


def tr_contains(column, query_text: str):
    """Türkçe duyarlı, büyük/küçük harf bağımsız ``LIKE %...%`` koşulu."""
    folded = tr_fold(query_text)
    if _is_sqlite():
        return func.tr_fold(column).contains(folded, autoescape=True)
    return func.lower(column).contains(folded, autoescape=True)


def tr_equals(column, query_text: str):
    """Türkçe duyarlı, büyük/küçük harf bağımsız eşitlik koşulu."""
    folded = tr_fold(query_text)
    if _is_sqlite():
        return func.tr_fold(column) == folded
    return func.lower(column) == folded
