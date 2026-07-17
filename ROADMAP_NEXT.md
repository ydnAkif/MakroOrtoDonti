# Yol Haritasi: Model ve UI/UX Revizyonu

## 1) Veri modeli genisletme (Hasta -> Kisi/Musteri) ✅ TAMAMLANDI

Hedef: Hasta merkezli kayit yapisini, dis hekimi musterileri ve kurumsal musterileri de kapsayacak sekilde genisletmek.

- Yeni cekirdek varlik: `Party` ✅
- Alt tipler: ✅
  - `patient` ✅
  - `dentist_customer` ✅
  - `company_customer` ✅
- Ortak alanlar: ✅
  - ad/unvan, telefon, e-posta, adres, not
  - vergi no / kimlik no (opsiyonel)
  - aktif/pasif durumu
- Fatura iliskisi: ✅
  - `Invoice.party_id` (zorunlu) ✅
  - `Invoice.patient_id` gecis suresince uyumluluk kolonu olarak kaldi ✅

Asamali gecis: ✅ TAMAMLANDI
1. `Party` tablosunu ekle, mevcut hastalari Party'ye backfill et. ✅
2. Yeni kayit ekranlarini `Party` uzerinden calistir. ✅
3. Raporlari Party bazli hale getir. ✅ (Parties listesi + filtreler)
4. Son asamada `Patient` bagimliliklarini kaldir. (ileride)

## 2) Fatura satiri genelleme ✅ TAMAMLANDI

Hedef: Sadece tedavi degil, urun, laboratuvar, danismanlik gibi satirlari da ayni yapiyla faturalayabilmek.

- `InvoiceItem` icin hedef alanlar: ✅
  - `item_type` (`treatment`, `service`, `product`, `lab`, `custom`) ✅
  - `reference_id` (opsiyonel, tedaviye bagliysa) ✅
  - `description` (zorunlu) ✅
  - `quantity`, `unit_price_eur`, `unit_price_try` ✅
- KDV/iskonto destegi: ✅
  - `vat_rate`, `discount_type`, `discount_value` ✅
  - Hesaplama property'leri: `line_total_eur`, `line_total_try`, `vat_amount_eur`, `vat_amount_try` ✅

## 3) UI/UX: once bilgi mimarisi ✅ TAMAMLANDI

Ana menu hedefi: ✅
- Panel ✅
- Kisiler ✅
- Tedavi Katalogu ✅
- Finans (Faturalar, Tahsilatlar, Kurlar) ✅
- Iletisim (WhatsApp, E-posta) ✅
- Raporlar ✅
- Ayarlar ✅

Kisiler (Parties) bilgi mimarisi: ✅
- Liste: tip, durum, son islem, borc bakiyesi ✅
- Detay sekmeleri: Profil / Islem gecmisi / Faturalar / Iletisim gecmisi ✅ (tek sayfada)

Finans bilgi mimarisi: ✅
- Fatura listesi ✅
- Tahsilat listesi ✅
- Kur yonetimi ✅
- Yaslandirma raporu (0-30, 31-60, 61+) ✅

## 4) UI/UX: gorsel iyilestirme prensipleri ✅ TAMAMLANDI

- Bilgi yogun ekranlarda kart yerine tablo agirlikli tasarim ✅
- Mobilde sabit alt gezinme (fixed bottom nav) + drawer fallback ✅
- Renk semantigi: ✅
  - yesil: tahsil edildi / odendi
  - sari: bekliyor
  - kirmizi: gecikmis
- Her ekranda "birincil aksiyon" tek ve belirgin ✅

## 5) Finans Modulu Genisleme ✅ TAMAMLANDI

- Tahsilat (Payment) modeli ve route'lari ✅
- Fatura odeme durumu otomatik guncelleme ✅ (paid/partial/pending)
- Doviz kur yonetimi ✅ (Settings sayfasinda)

## 6) Tedavi Yonetimi ✅ TAMAMLANDI

- Tedavi katalogu CRUD ✅
- XLSX import (upsert, TR/EN kategori eslestirme) ✅
- Inline duzenleme (contenteditable + AJAX) ✅
- Fatura formunda tedavi secimi → otomatik aciklama/fiyat doldurma ✅

## 7) Sevk Sistemi ✅ TAMAMLANDI

- `Party.referred_by_id` (self-referential FK) ✅
- Hasta olustururken sevk eden dis hekimini secme ✅
- Typeahead hidden input change event destegi ✅

## 8) Test Kapsam Genisletme ✅ TAMAMLANDI

### Gecen Testler (65/65)

**test_critical_flows.py (18 test)**
- `test_login_success` ✅
- `test_invoice_create_flow` ✅ (legacy + yeni format)
- `test_settings_update_does_not_overwrite_unsent_fields` ✅
- `test_rate_fetch_updates_today_rate` ✅
- `test_invoice_pdf_download_works` ✅
- `test_party_crud_patient` ✅
- `test_party_crud_dentist_customer` ✅
- `test_party_crud_company_customer` ✅
- `test_party_type_filter` ✅
- `test_invoice_flexible_items` ✅
- `test_invoice_vat_discount_calculations` ✅
- `test_payment_flow` ✅
- `test_payment_list_filters` ✅
- `test_party_invoice_link_and_debt_calculation` ✅
- `test_reports_aging_report` ✅
- `test_legacy_invoice_compatibility` ✅
- `test_invoice_api_treatment_price` ✅
- `test_party_api_info` ✅

**test_comprehensive.py (47 test)**
- Auth: login invalid creds, logout, unauthenticated redirect ✅
- Dashboard: sayfa yukleme ✅
- Patients: list, add (+ Party olusturma), detail, edit (+ Party sync), delete (+ Party deaktivasyonu), add-treatment ✅
- Treatments: list, filter category, search, add, edit, delete, API update, API invalid, XLSX import, invalid file ✅
- Invoices: list, filter status, detail, status update, soft-delete, party preselect, no items rejected, amount discount, search ✅
- Payments: add, delete (+ invoice status geri alma) ✅
- Settings: page load, clinic info update, exchange rate manual add ✅
- Reports: page load ✅
- Parties: search, referred_by ✅
- Bug fix regression tests: recalculate_totals, party-only invoice/dashboard/detail crash, enum badges, payment list/form crash, email service, whatsapp service, VAT totals ✅

---

## Yapilacaklar (Sirali)

### Hemen
1. [x] Test dosyasini genislet (56/56 → 65/65 geciyor) ✅
2. [x] Reports sayfasina Yaslandirma raporu (aging) ✅
3. [x] Invoice modal formunda KDV/Iskonto alanlari gorunurlugu ✅
4. [x] Fatura olusturmada tedavi secimi dogrulama hatasi duzelt ✅
5. [x] Kisi Detay'dan fatura olustururken kisi onceden secili gelsin ✅
6. [x] TODO.md'deki 13 bug'i duzelt ✅ (recalculate_totals, email/wa service, template fallbacks, enum badges, payments template vars, race condition, logout CSRF, WhatsApp Party migration, PDF party-first)
7. [x] Bug fix regression testleri ekle ✅ (9 yeni test)

### Kisa Vadeli
8. [ ] API endpoint'leri (mobil entegrasyon icin)
9. [ ] Patient modelinden `party_id` ve `Patient.party` relationship'ini kullanarak `Patient` bagimliligi azaltma
10. [ ] Randevu sistemi (Calendar entegrasyonu)

### Uzun Vadeli
11. [ ] Otomatik SQLite yedekleme (cron/job)
12. [ ] Coklu dil (i18n) altyapisi
13. [ ] Barkod/QR fatura
14. [ ] Stok yonetimi (urun kalemleri icin)

---

## Kademeli Cikis Plani (Guncel)

- ✅ Faz A: guvenlik ve veri butunlugu (tamamlandi)
- ✅ Faz B: model gecisi altyapisi (Party tablosu + migration)
- ✅ Faz C: Finans modulu genisleme (genel satir, tahsilat)
- ✅ Faz D: IA uygulama + gorsel revizyon (sidebar, navbar, mobile nav)
- ✅ Faz E: performans/test kapsam genisletme (65 test, tumunu geciyor)
- ✅ Faz F: Tedavi yonetimi + sevk sistemi + UX duzeltmeleri
- ✅ Faz G: TODO.md bug fixleri (13/15 duzeltildi, 2 bekliyor)
