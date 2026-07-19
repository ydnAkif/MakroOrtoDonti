# TODO - Bug & Eksiklik Listesi

> Son guncelleme: 17 Temmuz 2026
> Test durumu: 65/65 geciyor

---

## 19 Temmuz 2026 - Teknik Denetim Sonuclari (Yeni)

> Genel skor: **78/100**
> Detay rapor: `AUDIT_2026-07-19.md`

### KRITIK / YUKSEK - Acil Cozulmeli

1. Hasta listesi Party id ile Patient route'una gidiyor (id uyumsuzlugu riski)

- **Dosya:** `app/templates/patients/list.html:46-47`
- **Durum:** ✅ Düzeltildi
- **Etki:** Yanlis kayit/404/500, veri guveni azalir.

2. SMTP sifresi plaintext tutuluyor ve ayarlar ekraninda geri yazdiriliyor

- **Dosya:** `app/templates/settings/index.html:84`
- **Durum:** ⏳ Beklemede
- **Etki:** Gizli bilgi sizma riski.

3. Prod guvenlik konfigurasyonu zorunlu kilinmamis

- **Dosya:** `.env:1-3`, `app/config.py:7`, `run.py:23`
- **Durum:** ⏳ Beklemede
- **Etki:** Debug/varsayilan sifre/secret zafiyeti.

### ORTA - Stabilite ve Mimari

4. Giris endpoint'inde rate limiting/lockout yok

- **Dosya:** `app/routes/auth.py`
- **Durum:** ⏳ Beklemede

5. Form parse noktalarinda defensive validation eksik (bad input -> 500 riski)

- **Dosya:** `app/routes/settings.py:72-73`, `app/routes/payments.py:31-35,63,72`, `app/routes/parties.py:59,63,120,124`, `app/routes/invoices.py:90-91`, `app/routes/patients.py:193`
- **Durum:** ✅ Düzeltildi

6. Dashboard/Reports metrikleri Party-first degil

- **Dosya:** `app/routes/dashboard.py:15,50-51`, `app/routes/reports.py:94,98`
- **Durum:** ⏳ Beklemede

7. Request icinde dis API rate fetch (ilk istekte latency)

- **Dosya:** `app/__init__.py`, `app/services/exchange_service.py`
- **Durum:** ⏳ Beklemede

### DUSUK-ORTA - Teknik Borc

8. Party-Patient cift modelde drift riski (kismi senkron)

- **Dosya:** `app/routes/parties.py`, `app/routes/patients.py`
- **Durum:** ✅ Düzeltildi

---

## KRITIK - Veri Bozulma / Yanlis Hesaplama

### 1. `Invoice.recalculate_totals()` indirim ve KDV'yi yok sayiyor

- **Dosya:** `app/models/models.py:265-267`
- **Duzeltildi:** ✅ `line_total_eur` property'sini kullanarak toplam hesaplaniyor.
- **Test:** `test_recalculate_totals_includes_discount_and_vat`, `test_invoice_vat_in_totals`

### 2. E-posta servisi sadece patient faturalarinda calisiyor

- **Dosya:** `app/services/email_service.py:27`
- **Duzeltildi:** ✅ `invoice.party.email` + patient fallback.
- **Test:** `test_email_service_party_only`

### 3. WhatsApp servisi ayni sekilde crasliyor

- **Dosya:** `app/services/whatsapp_service.py:141`
- **Duzeltildi:** ✅ Party-first erisim + patient fallback.
- **Test:** `test_whatsapp_service_party_only`

---

## YUKSEK - Kirik Ozellikler / Runtime Hatalar

### 4. Dashboard son faturalar patient-only varsayimi

- **Dosya:** `app/templates/dashboard/index.html:110`
- **Duzeltildi:** ✅ Party-first fallback kullaniliyor.
- **Test:** `test_party_only_dashboard_no_crash`

### 5. Fatura listesi ayni sorun

- **Dosya:** `app/templates/invoices/list.html:59`
- **Duzeltildi:** ✅ Party-first fallback kullaniliyor.

### 6. Fatura detay ayni sorun (3 yerde)

- **Dosya:** `app/templates/invoices/detail.html:30-32, 133-134`
- **Duzeltildi:** ✅ Party-first fallback, customer degiskeni ile.
- **Test:** `test_party_only_invoice_detail_no_crash`

### 7. Parties listesi enum karsilastirma hatasi

- **Dosya:** `app/templates/parties/list.html:80, 85, 96`
- **Duzeltildi:** ✅ `.value` ile karsilastirma yapiliyor.
- **Test:** `test_party_list_enum_badges`

### 8. Odeme listesi template degisken uyumsuzlugu

- **Dosya:** `app/templates/payments/list.html:18-31` vs `app/routes/payments.py:44-53`
- **Duzeltildi:** ✅ Route ile eslesme saglandi.
- **Test:** `test_payments_list_no_crash`

### 9. Odeme formu `current_rate` eksik

- **Dosya:** `app/templates/payments/form.html:120` vs `app/routes/payments.py:118`
- **Duzeltildi:** ✅ Route `current_rate` gonderiyor.
- **Test:** `test_payment_form_no_crash`

---

## ORTA - Guvenlik / Mimari

### 10. Fatura numarasi uretiminde race condition

- **Dosya:** `app/models/invoice_service.py:19-42`
- **Duzeltildi:** ✅ `update()` statement-based locking kullaniliyor.

### 11. Logout GET ile calisiyor (CSRF riski)

- **Dosya:** `app/routes/auth.py:55`
- **Duzeltildi:** ✅ POST-only form ile degistirildi.

### 12. WhatsApp rotasi Patient modelini kullaniyor

- **Dosya:** `app/routes/whatsapp.py:16-22`
- **Duzeltildi:** ✅ Party modeline gecildi.

---

## KUCUK - Iyilestirmeler

### 13. PDF servisi party-only faturalarda bos bilgi gosterebilir

- **Dosya:** `app/services/pdf_service.py:215-220`
- **Duzeltildi:** ✅ Party-first priority ile musteri bilgisi aliniyor.

### 14. Settings'te SMTP sifresi plaintext olarak kaydediliyor

- **Dosya:** `app/routes/settings.py:38`, `app/templates/settings/index.html:84`
- **Durum:** ⏳ Beklemede - sifreleme altyapisi gerekiyor.

### 15. `.env` dosyasinda zayif sifre ve secret key

- **Dosya:** `.env`, `app/config.py:7`
- **Durum:** ⏳ Beklemede - production'a geciste ele alinacak.

---

## ONCELIK SIRASI

| #     | Oncelik | Kisa Aciklama                                         | Durum |
| ----- | ------- | ----------------------------------------------------- | ----- |
| 1     | KRITIK  | recalculate_totals indirim/KDV hesapsiz               | ✅    |
| 2     | KRITIK  | email_service party-only crasliyor                    | ✅    |
| 3     | KRITIK  | whatsapp_service party-only crasliyor                 | ✅    |
| 4-6   | YUKSEK  | Dashboard/fatura template'leri patient-only crasliyor | ✅    |
| 7     | YUKSEK  | Parties listesi enum hatasi                           | ✅    |
| 8-9   | YUKSEK  | Odeme sayfalari template uyumsuz                      | ✅    |
| 10    | ORTA    | Invoice numarasi race condition                       | ✅    |
| 11    | ORTA    | Logout CSRF                                           | ✅    |
| 12    | ORTA    | WhatsApp Patient model kullanimi                      | ✅    |
| 13    | KUCUK   | PDF servisi party-first                               | ✅    |
| 14-15 | KUCUK   | SMTP sifreleme, .env guvenlik                         | ⏳    |
