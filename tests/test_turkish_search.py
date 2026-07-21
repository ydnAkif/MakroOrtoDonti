"""Türkçe duyarlı arama testleri: tr_fold, rota aramaları ve içe aktarma dedupe'u."""

from __future__ import annotations

import io

from openpyxl import Workbook

from app.extensions import db
from app.models.models import Party, PartyType, Treatment
from app.services.search_service import tr_fold, tr_order

from conftest import login


class TestTrFold:
    def test_turkish_letters_fold_to_ascii(self):
        assert tr_fold("Şahin İŞCAN") == "sahin iscan"
        assert tr_fold("Pınar") == "pinar"
        assert tr_fold("IĞDIR ÇÖĞÜŞ") == "igdir cogus"
        assert tr_fold("Büşra Öztopal") == "busra oztopal"

    def test_ascii_unchanged(self):
        assert tr_fold("Dr. Smith") == "dr. smith"

    def test_none_and_empty(self):
        assert tr_fold(None) == ""
        assert tr_fold("") == ""


def _seed_dentist(app, name, phone=None):
    with app.app_context():
        party = Party(party_type=PartyType.DENTIST, name=name, phone=phone)
        db.session.add(party)
        db.session.commit()
        return party.id


class TestTurkishOrdering:
    def test_turkish_letters_interleave_not_after_z(self, app):
        names = [
            "Büşra", "Çağla", "Canan", "Oya", "Ömer", "Parla", "Sevil",
            "Şule", "Yusuf", "Zümrüt",
        ]
        with app.app_context():
            for n in names:
                db.session.add(Party(party_type=PartyType.DENTIST, name=n))
            db.session.commit()

            ordered = [
                n for n in db.session.execute(
                    db.select(Party.name)
                    .where(Party.party_type == PartyType.DENTIST)
                    .order_by(tr_order(Party.name))
                ).scalars().all()
                if n in names
            ]

        # DB order must match Python's Turkish-folded sort exactly: Ç inside
        # the C block, Ö with O, Ş with S — not clustered after Z.
        assert ordered == sorted(names, key=tr_fold)
        # Concretely: Ç sits between B and C, not at the end.
        assert ordered.index("Çağla") < ordered.index("Canan")
        assert ordered.index("Büşra") < ordered.index("Çağla")
        # Ö clusters with O; the two O-names are adjacent.
        assert abs(ordered.index("Ömer") - ordered.index("Oya")) == 1

    def test_list_page_orders_turkish_names_correctly(self, client, app):
        login(client, "admin", "admin-pass")
        with app.app_context():
            for n in ["Zümrüt", "Ahmet", "Çağla", "Canan"]:
                db.session.add(Party(party_type=PartyType.DENTIST, name=n))
            db.session.commit()
        html = client.get("/parties/").get_data(as_text=True)
        # Çağla appears before Canan and before Zümrüt in the rendered order
        assert html.index("Çağla") < html.index("Canan") < html.index("Zümrüt")


class TestPartySearch:
    def test_ascii_query_finds_turkish_name(self, client, app):
        login(client, "admin", "admin-pass")
        _seed_dentist(app, "Şahin İşcan")
        response = client.get("/parties/?search=sahin")
        assert "Şahin İşcan".encode() in response.data

    def test_uppercase_turkish_query(self, client, app):
        login(client, "admin", "admin-pass")
        _seed_dentist(app, "Pınar Kutay")
        for q in ("PINAR", "pınar", "pinar", "kutay"):
            response = client.get(f"/parties/?search={q}")
            assert "Pınar Kutay".encode() in response.data, q

    def test_turkish_query_finds_ascii_name(self, client, app):
        login(client, "admin", "admin-pass")
        _seed_dentist(app, "Pinar Duz")  # ASCII kayıtlı isim
        response = client.get("/parties/?search=pınar")
        assert b"Pinar Duz" in response.data

    def test_phone_search_ignores_spaces(self, client, app):
        login(client, "admin", "admin-pass")
        _seed_dentist(app, "Dr. Telefon", phone="+90 536 361 93 78")
        response = client.get("/parties/?search=5363619378")
        assert b"Dr. Telefon" in response.data

    def test_no_match_returns_empty(self, client, app):
        login(client, "admin", "admin-pass")
        _seed_dentist(app, "Şahin İşcan")
        response = client.get("/parties/?search=olmayanisim")
        assert "Şahin İşcan".encode() not in response.data

    def test_search_finds_name_that_lives_on_a_later_page(self, client, app):
        """25/sayfa listede 'Ö' ile başlayan isim son sayfalarda olsa bile
        arama tüm veritabanını tarayıp bulmalı (istemci-sayfa filtresi değil)."""
        login(client, "admin", "admin-pass")
        with app.app_context():
            # 30 doctor whose names sort before "Ö..." so the Ö one is on page 2+
            for i in range(30):
                db.session.add(Party(
                    party_type=PartyType.DENTIST, name=f"Ahmet {i:02d}"
                ))
            db.session.add(Party(party_type=PartyType.DENTIST, name="Ömer Özkan"))
            db.session.commit()

        # Default first page must NOT contain the Ö name (it paginates later)
        first_page = client.get("/parties/").get_data(as_text=True)
        assert "Ömer Özkan" not in first_page
        # Server-side search finds it regardless of page
        found = client.get("/parties/?search=omer").get_data(as_text=True)
        assert "Ömer Özkan" in found


class TestOtherSearches:
    def test_payments_doctor_search_turkish(self, client, app):
        login(client, "admin", "admin-pass")
        _seed_dentist(app, "Gülşah Çördük")
        response = client.get("/payments/?search=gulsah")
        assert "Gülşah Çördük".encode() in response.data

    def test_treatments_search_turkish(self, client, app):
        login(client, "admin", "admin-pass")
        with app.app_context():
            db.session.add(Treatment(name="Ölçü Alımı", category="ana_islemler", price_eur=10))
            db.session.commit()
        response = client.get("/treatments/?search=olcu")
        assert "Ölçü Alımı".encode() in response.data


def _xlsx(rows):
    wb = Workbook()
    ws = wb.active
    ws.append(["Ad Soyad", "Telefon", "E-posta", "Adres", "Vergi No", "Not"])
    for row in rows:
        ws.append(row)
    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer


class TestImportDedupe:
    def test_same_phone_different_names_both_created(self, client, app):
        """Aynı telefonu paylaşan farklı isimler (iki şubeli klinik) yutulmamalı."""
        login(client, "admin", "admin-pass")
        data = {"file": (_xlsx([
            ["Dentar Yenibosna", "+905425474405", None, None, None, None],
            ["Dent Ar Şirinevler", "+905425474405", None, None, None, None],
        ]), "d.xlsx")}
        response = client.post(
            "/parties/import", data=data, content_type="multipart/form-data", follow_redirects=True
        )
        assert "2 yeni" in response.get_data(as_text=True)
        with app.app_context():
            names = db.session.execute(
                db.select(Party.name).where(Party.phone == "+905425474405")
            ).scalars().all()
            assert sorted(names) == ["Dent Ar Şirinevler", "Dentar Yenibosna"]

    def test_turkish_case_name_match_updates(self, client, app):
        """'ŞAHİN işcan' gibi farklı büyük/küçük yazım mevcut kaydı güncellemeli."""
        login(client, "admin", "admin-pass")
        _seed_dentist(app, "Şahin İşcan", phone="+905551110001")

        data = {"file": (_xlsx([["ŞAHİN İŞCAN", "+905559998877", None, None, None, None]]), "d.xlsx")}
        response = client.post(
            "/parties/import", data=data, content_type="multipart/form-data", follow_redirects=True
        )
        assert "1 güncellendi" in response.get_data(as_text=True)
        with app.app_context():
            rows = db.session.execute(
                db.select(Party).where(Party.phone == "+905559998877")
            ).scalars().all()
            assert len(rows) == 1
            assert rows[0].name == "Şahin İşcan"
