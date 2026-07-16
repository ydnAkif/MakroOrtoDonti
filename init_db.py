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
    generated_password = seed_sample_data(session)
    session.close()

    print("Veritabanı başarıyla oluşturuldu!")
    print("Dosya: data/makroortodonti.db")
    print("")
    print("Giriş bilgileri:")
    print("  Kullanıcı: admin")
    if generated_password:
        print(f"  Şifre: {generated_password}")
        print("  Not: Güvenlik için rastgele şifre üretildi. İsterseniz DEFAULT_ADMIN_PASSWORD ile sabitleyebilirsiniz.")
    else:
        print("  Şifre: mevcut admin şifresi korundu")
    print("")
    print("Uygulamayı başlatmak için: python run.py")


if __name__ == "__main__":
    main()
