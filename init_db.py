#!/usr/bin/env python3
"""Initialize database with seed data."""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app import create_app, db
from app.models.database import init_db, get_session, seed_sample_data


def main():
    print("Veritabanı oluşturuluyor...")
    init_db()

    print("Örnek veriler ekleniyor...")
    session = get_session()
    seed_sample_data(session)
    session.close()

    print("Veritabanı başarıyla oluşturuldu!")
    print("Dosya: data/makroortodonti.db")
    print("")
    print("Giriş bilgileri:")
    print("  Kullanıcı: admin")
    print("  Şifre: admin123")
    print("")
    print("Uygulamayı başlatmak için: python run.py")


if __name__ == "__main__":
    main()
