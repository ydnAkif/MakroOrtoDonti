# Yol Haritasi: Model ve UI/UX Revizyonu

## 1) Veri modeli genisletme (Hasta -> Kisi/Musteri)

Hedef: Hasta merkezli kayit yapisini, dis hekimi musterileri ve kurumsal musterileri de kapsayacak sekilde genisletmek.

- Yeni cekirdek varlik: `Party`
- Alt tipler:
  - `patient`
  - `dentist_customer`
  - `company_customer`
- Ortak alanlar:
  - ad/unvan, telefon, e-posta, adres, not
  - vergi no / kimlik no (opsiyonel)
  - aktif/pasif durumu
- Fatura iliskisi:
  - `Invoice.party_id` (zorunlu)
  - `Invoice.patient_id` gecis suresince uyumluluk kolonu olarak kalabilir

Asamali gecis:

1. `Party` tablosunu ekle, mevcut hastalari Party'ye backfill et.
2. Yeni kayit ekranlarini `Party` uzerinden calistir.
3. Raporlari Party bazli hale getir.
4. Son asamada `Patient` bagimliliklarini kaldir.

## 2) Fatura satiri genelleme

Hedef: Sadece tedavi degil, urun, laboratuvar, danismanlik gibi satirlari da ayni yapiyla faturalayabilmek.

- `InvoiceItem` icin hedef alanlar:
  - `item_type` (`treatment`, `service`, `product`, `custom`)
  - `reference_id` (opsiyonel, tedaviye bagliysa)
  - `description` (zorunlu)
  - `quantity`, `unit_price_eur`, `unit_price_try`
- Gelecekte KDV/iskonto destegi:
  - `vat_rate`, `discount_type`, `discount_value`

## 3) UI/UX: once bilgi mimarisi

Ana menu hedefi:

- Panel
- Kisiler
- Tedavi Katalogu
- Finans (Faturalar, Tahsilatlar, Kurlar)
- Iletisim (WhatsApp, E-posta)
- Raporlar
- Ayarlar

Kisiler bilgi mimarisi:

- Liste: tip, durum, son islem, borc bakiyesi
- Detay sekmeleri:
  - Profil
  - Islem gecmisi
  - Faturalar
  - Iletisim gecmisi

Finans bilgi mimarisi:

- Fatura listesi
- Tahsilat listesi
- Kur yonetimi
- Yaslandirma raporu (0-30, 31-60, 61+)

## 4) UI/UX: gorsel iyilestirme prensipleri

- Bilgi yogun ekranlarda kart yerine tablo agirlikli tasarim
- Mobilde sabit alt gezinme veya drawer fallback
- Renk semantigi:
  - yesil: tahsil edildi
  - sari: bekliyor
  - kirmizi: gecikmis
- Her ekranda "birincil aksiyon" tek ve belirgin

## 5) Kademeli cikis plani

- Faz A: guvenlik ve veri butunlugu (tamamlandi)
- Faz B: model gecisi altyapisi (Party tablosu + migration)
- Faz C: Finans modulu genisleme (genel satir, tahsilat)
- Faz D: IA uygulama + gorsel revizyon
- Faz E: performans/test kapsam genisletme
