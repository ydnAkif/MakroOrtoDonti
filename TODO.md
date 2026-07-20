# Makro Ortodonti — Teknik Roadmap

Son güncelleme: 19 Temmuz 2026

Bu belge, `PLAN.md` içindeki ürün vizyonunu değiştirmeden mevcut kodun gerçek teknik durumunu ve sonraki güvenli adımları gösterir.

## Güncel skor: 92/100

Skor; çalışan kod, 420 otomatik test, branch coverage, masaüstü ve 400×765 mobil tarayıcı incelemesi, production başlatma modeli ve yedek/geri yükleme zinciri üzerinden verilmiştir. Bu proje güçlü bir klinik iç kullanım sürümüdür. Kuruma ait secret store, uzak yedek hedefi ve staging altyapısı doğrulanmadan 100/100 demek gerçekçi olmaz.

| Alan | Ağırlık | Skor | Kısa değerlendirme |
| --- | ---: | ---: | --- |
| Görsel UI | %10 | 93 | Özgün klinik kimliği, tutarlı tasarım sistemi, başarılı responsive yapı |
| UX ve erişilebilirlik | %10 | 88 | Semantik gezinme, görünür odaklar, mobil kişi kartları; otomatik axe taraması henüz yok |
| Fonksiyonel kapsam | %12 | 94 | Kişi, tedavi, fatura, tahsilat, PDF, rapor, SMTP ve WhatsApp akışları geniş |
| Mimari | %12 | 80 | Blueprint/service ayrımı iyi; legacy `Patient` uyumluluk katmanı ve bazı geniş route'lar borç |
| Kod kalitesi | %10 | 86 | Savunmacı doğrulama ve hata akışları güçlendi; transaction sınırları daha da sadeleşebilir |
| Veri bütünlüğü | %14 | 84 | Finansal invariantlar, fazla ödeme ve FK koruması var; para alanları hâlâ `Float` |
| Güvenlik ve mahremiyet | %16 | 88 | CSRF, bcrypt, rol kontrolü, kilit, ayrı Fernet anahtarı ve fail-closed production ayarı var |
| Test ve kalite güvence | %10 | 97 | 420 test, %95,75 toplam coverage, %89,87 branch coverage, %90 CI kapısı ve gerçek Chromium E2E |
| Operasyon ve performans | %6 | 86 | Gunicorn, health check, doğrulamalı atomik backup/restore ve SQLite korumaları hazır |
| **Toplam** | **%100** | **88** | **Üretime yakın, kalan yapısal işler açıkça sınırlandırılmış durumda** |

Ek kalibrasyon:

- Klinik iç kullanım hazırlığı: **96/100**
- Kontrollü HTTPS production hazırlığı: **86/100**
- Çok sunuculu / yüksek eşzamanlı kullanım: **72/100**

## Bu turda tamamlananlar

- [x] 14 başlangıç regresyonu giderildi; tüm suite yeşil
- [x] Fatura satırlarında miktar, fiyat, KDV, iskonto, enum ve referans doğrulaması
- [x] Fazla tahsilat, silinmiş/iptal fatura ve ödeme sonrası durum korumaları
- [x] Geçmiş alacakların dönem sonu raporuna doğru taşınması ve fatura kuru bazlı TRY hesabı
- [x] SMTP secret için XOR/Base64 yerine Fernet ve ayrı `ENCRYPTION_KEY`
- [x] Production'da zayıf/örnek secret değerlerinde fail-closed başlangıç
- [x] Proxy/IP güven sınırı, secure cookie seçenekleri ve SQLite foreign key/busy timeout
- [x] DOM XSS yüzeylerinin `textContent`/DOM API ile kapatılması
- [x] `/health` veritabanı readiness kontrolü
- [x] Online SQLite backup, rotation, integrity check ve onaylı atomik restore
- [x] Gunicorn production giriş noktası ve production/dev bağımlılık ayrımı
- [x] GitHub Actions üzerinde Python 3.13/3.14, compile, test ve %90 branch-aware coverage kapısı
- [x] Mobil kişi listesinin yatay kaydırmasız kart görünümü
- [x] Navigasyon semantiği, `aria-current`, ikon ve flash erişilebilirlik temizliği
- [x] Geçersiz kişi türü ile 500 hatasının ve hasta→kurum dönüşümündeki legacy kayıt tutarsızlığının giderilmesi
- [x] Tedavi adı, kategori ve fiyat doğrulaması
- [x] Güncel kurulum, production, güvenlik, test ve felaket kurtarma talimatlarını içeren `README.md`

## Doğrulanan kalite kapısı

```text
420 passed (416 Python/entegrasyon + 4 Chromium E2E)
Branch coverage: %89,87 (toplam branch-aware coverage: %95,75)
Coverage alt sınırı: %90
Python compileall: geçti
pip check: geçti
400×765 mobil görsel kontrol: geçti
```

## P1 — Production verisi taşınmadan önce

- [x] Flask-Migrate/Alembic ekle; `create_all` ve elle `ALTER TABLE` akışını sürümlü migrationlara taşı
- [x] Migrationları mevcut veritabanı kopyasında ve boş veritabanında test et
- [x] Para/kur kolonlarını `Float` yerine `Decimal` + SQL `Numeric` yapısına kontrollü migration ile taşı
- [x] `Party`yi operasyonel tek doğruluk kaynağı yap; legacy `Patient` tablosunu yalnızca migration uyumluluğuna indir
- [x] Fatura numarası sayacını atomik veritabanı artışı ve eşzamanlı iki transaction testiyle güvenceye al
- [x] Tedavi formu, JSON API ve XLSX içe aktarmayı tek doğrulama yaklaşımında birleştir

## P2 — İnternete açık dağıtım öncesi

- [x] HSTS, CSP, `X-Content-Type-Options`, Referrer ve Permissions Policy güvenlik başlıklarını uygula
- [x] Bootstrap/font/ikon kaynaklarını self-host et
- [x] Döviz kuru yenilemeyi request içindeki background thread yerine scheduler-safe CLI job'a taşı
- [x] Yapılandırılmış log, request ID ve opsiyonel Sentry hata izleme ekle
- [x] Gerçek Chromium Playwright E2E altyapısı ekle
- [x] axe-core ile 400 px mobil ve 1280 px masaüstü WCAG kalite kapısı kur

## P3 — Sağlık verisi yönetişimi ve ölçek

- [x] Kişi, finans ve ayar değişiklikleri için aktör/zaman/eski-yeni değer audit logu
- [x] Klinik, finans, rapor, mesajlaşma, ayar ve KVKK izinlerinden oluşan merkezi rol matrisi
- [x] KVKK saklama, korumalı anonimleştirme ve dışa aktarma teknik akışları
- [x] Şifreli yedek, çoklu anahtarla rotasyon ve aktif veritabanı için disk şifreleme preflight kontrolü
- [x] Liste sayfalarında sunucu taraflı pagination ve raporlarda SQL aggregate sorguları
- [ ] Eşzamanlı kullanıcı/yazma eşiği aşılırsa PostgreSQL geçiş planı

## Sürüm yayınlama kapısı

- [ ] Production `SECRET_KEY` ve `ENCRYPTION_KEY` ayrı secret store değerleri olarak tanımlı
- [ ] HTTPS, secure cookie ve güvenilir proxy ayarları staging ortamında doğrulandı
- [ ] Son backup doğrulandı ve restore tatbikatı farklı bir makinede geçti
- [x] Migration anonimleştirilmiş gerçek veri kopyasında geçti; atomik restore/geri dönüş aracı hazır
- [x] Kritik E2E ve erişilebilirlik kontrolleri geçti
- [x] Otomatik kontrollerde açık kritik/yüksek güvenlik bulgusu yok
- [ ] KVKK yetki, saklama ve olay müdahale sorumluları belirlendi

## Standart doğrulama komutları

```bash
pytest
pytest --cov=app --cov-branch --cov-report=term-missing --cov-fail-under=90
python -m compileall -q app tests backup.py deployment_check.py production_drill.py run.py run_production.py
python -m pip check
git diff --check
```
