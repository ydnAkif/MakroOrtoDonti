# Makro Ortodonti — Teknik Yol Haritası ve TODO

Son değerlendirme: 19 Temmuz 2026

Bu belge mevcut kodun, 73 otomatik testin ve çalışan uygulamanın masaüstü ile 400×765 mobil görünümünün incelenmesiyle hazırlanmıştır. `PLAN.md` ürün vizyonunu korur; bu dosya ise uygulanabilir teknik önceliklerin güncel kaynağıdır.

## Mevcut skor: 71/100

Bu skor çalışan bir iç araç/MVP ile güvenli ve sürdürülebilir bir üretim sistemi arasındaki farkı esas alır. Ürün kapsamı ve görsel kalite güçlüdür; veri bütünlüğü, güvenlik ve operasyonel hazırlık toplam skoru aşağı çeker.

| Alan | Ağırlık | Skor | Katkı | Kısa değerlendirme |
| --- | ---: | ---: | ---: | --- |
| Görsel UI | %10 | 88 | 8,8 | Özgün klinik kimliği, tutarlı renk/tipografi, başarılı masaüstü hiyerarşisi |
| UX ve erişilebilirlik | %10 | 74 | 7,4 | İyi gezinme ve boş durumlar; özel arama seçicisi ve mobil tablolar zayıf |
| Fonksiyonel kapsam | %12 | 88 | 10,6 | Kişi, tedavi, fatura, tahsilat, PDF, rapor, e-posta ve WhatsApp akışları geniş |
| Mimari | %12 | 71 | 8,5 | Blueprint/service ayrımı iyi; başlangıçta veri değiştirme ve çift model teknik borç |
| Kod kalitesi | %10 | 70 | 7,0 | Okunabilir modüler yapı; geniş exception yakalama ve dağınık transaction sınırları var |
| Veri bütünlüğü | %14 | 60 | 8,4 | İlişkiler ve testler var; `Party/Patient`, `float` para ve eksik invariant kontrolleri riskli |
| Güvenlik ve mahremiyet | %16 | 55 | 8,8 | CSRF, bcrypt, auth ve rol kontrolü var; secret/SMTP, DOM XSS ve hardening eksikleri ciddi |
| Test ve kalite güvence | %10 | 80 | 8,0 | 73 test geçiyor; coverage eşiği, CSRF açık testler, E2E ve saldırı testleri yok |
| Operasyon ve performans | %6 | 55 | 3,3 | Küçük ölçek için yeterli; migration, backup, WSGI, gözlemlenebilirlik ve CI eksik |
| **Toplam** | **%100** |  | **70,8 → 71** | **Güçlü MVP, henüz üretim güvenliği seviyesinde değil** |

Ek kalibrasyon:

- İç kullanım MVP hazırlığı: yaklaşık **82/100**
- İnternete açık üretim hazırlığı: yaklaşık **58/100**
- Tasarım sistemi ve görsel sunum: yaklaşık **88/100**

## Doğrulanan mevcut durum

- [x] `.venv/bin/python -m pytest -q`: **73 passed**, yaklaşık 58 saniye
- [x] Python derleme kontrolü: `app`, `tests`, `run.py`, `init_db.py` başarılı
- [x] `pip check`: bozuk bağımlılık yok
- [x] Uygulama temiz bir geçici SQLite veritabanıyla başlatıldı
- [x] Giriş, panel, kişiler, faturalar, yeni fatura ve raporlar masaüstünde incelendi
- [x] Kişiler ekranı 400×765 responsive görünümde incelendi
- [x] Aktif çalışma verisi olan `data/makroortodonti.db` korundu
- [x] Kullanılmayan eski veritabanı kopyası, logo kopyaları ve üretilmiş cache/TeX dosyaları temizlendi

Not: `.venv/bin/pytest -q` doğrudan çalıştırıldığında `app` import hatası veriyor; standart doğrulama komutu şimdilik `.venv/bin/python -m pytest -q` olmalıdır.

## En güçlü taraflar

- Klinik iş akışına özel, hazır şablon hissi vermeyen görsel kimlik
- Masaüstünde iyi bilgi hiyerarşisi; mobilde çalışan üst menü ve alt hızlı erişim
- Jinja/Flask ölçeğine uygun blueprint ve service ayrımı
- Fatura, KDV, iskonto, tahsilat, PDF ve dönem raporlarında geniş fonksiyonel kapsam
- CSRF altyapısı, bcrypt parola doğrulaması, güvenli yönlendirme kontrolü ve admin rol korumaları
- Legacy akışlar dahil kritik CRUD ve finans senaryolarını kapsayan 73 regresyon testi
- `selectin` ilişkiler ve temel indekslerle küçük klinik ölçeğine uygun sorgu temeli

## P0 — Üretim öncesi zorunlu işler

### SEC-001 — SMTP secret saklamasını değiştir

- [ ] `app/services/security_service.py` içindeki XOR + Base64 yaklaşımını kaldır
- [ ] SMTP şifresini tercihen yalnızca environment/secret store içinde tut; veritabanında tutulacaksa Fernet/AES-GCM gibi doğrulamalı şifreleme ve ayrı, kalıcı bir encryption key kullan
- [ ] Decryption başarısız olduğunda plaintext döndürme davranışını kaldır; güvenli biçimde hata ver
- [ ] Ayarlar ekranı mevcut şifreyi hiçbir zaman geri göstermemeli veya istemciye taşımamalı
- [ ] Secret rotasyonu ve eski ciphertext migration senaryosu ekle

Kabul ölçütü: uygulama `SECRET_KEY` değişse bile SMTP secret bozulmamalı; yanlış anahtar plaintext üretmemeli; testler secret değerini log/HTML içinde görmemeli.

### SEC-002 — Secret ve session politikasını fail-closed yap

- [ ] Production ortamında eksik/zayıf `SECRET_KEY` için her açılışta rastgele anahtar üretmek yerine uygulamayı başlatma hatasıyla durdur
- [ ] `SESSION_COOKIE_SECURE`, `SESSION_COOKIE_HTTPONLY`, `SESSION_COOKIE_SAMESITE`, oturum süresi ve yeniden kimlik doğrulama politikasını açıkça ayarla
- [ ] `TRUSTED_HOSTS`, HTTPS yönlendirme/HSTS ve reverse-proxy güven sınırını tanımla
- [ ] Login IP tespitinde `X-Forwarded-For` başlığını yalnızca güvenilen proxy arkasında kabul et
- [ ] Başarısız giriş kayıtları için temizlik/retention ve hesap kilitleme kötüye kullanımına karşı politika ekle

### SEC-003 — Fatura formundaki DOM XSS yüzeyini kapat

- [ ] `app/templates/invoices/form.html` içindeki `innerHTML` üretiminde `item.description`, `treatment_name` ve benzeri değişkenleri HTML olarak birleştirme
- [ ] Dinamik satırları `textContent`/DOM node API ile üret veya merkezi bir escape fonksiyonu kullan
- [ ] Zararlı tedavi açıklaması, XLSX importu ve özel kalem girdisi için XSS regresyon testleri ekle
- [ ] CSP uygulamasına hazırlık için inline scriptleri statik JS modüllerine taşı

Kabul ölçütü: `<img onerror=...>` ve benzeri payloadlar metin olarak görünmeli, JavaScript çalıştırmamalı.

### DATA-001 — `Party` ve `Patient` için tek doğruluk kaynağına geç

- [ ] Hedef modeli `Party` olarak kesinleştir; `Patient`ı geçici uyumluluk katmanı olarak sınırla
- [ ] `/patients` route ve şablonlarını ya `Party` tabanına taşı ya da kontrollü biçimde kaldır
- [ ] `app/templates/patients/list.html` düzenleme bağlantısının `Party.id` yerine yanlış `Patient.id` kullanma riskini gider
- [ ] Kişi türü patient → dentist/company değiştiğinde eski `Patient` kaydının aktif kalmasını engelle
- [ ] Mevcut `Party ↔ Patient ↔ Invoice` eşleşmelerini doğrulayan tek seferlik migration ve audit komutu yaz
- [ ] Çift yazımı kaldırdıktan sonra legacy kolon/model için aşamalı silme planı uygula

Kabul ölçütü: aynı kişinin iki modelde farklı ad/telefon/durum taşıması mümkün olmamalı; tüm route kimlikleri tek tip olmalı.

### DATA-002 — Finansal invariantları sunucuda zorunlu kıl

- [ ] Para ve kur alanlarında binary `float` yerine `Decimal`/SQL `Numeric` kullan
- [ ] Quantity > 0, unit price ≥ 0, VAT 0–100, yüzde iskonto 0–100 ve tutar iskontosu satır tutarını aşamaz kurallarını service katmanında doğrula
- [ ] `party_id`, `treatment_id` ve diğer referansların gerçekten var/aktif olduğunu fatura oluşturmadan önce doğrula
- [ ] Fazla tahsilatı açık bir iş kuralına bağla: reddet, kredi bakiyesi oluştur veya kullanıcıdan onay iste
- [ ] Tahsilat silinirken silinen kaydın toplamdan gerçekten çıkarıldığını doğrula; mevcut collection hesaplamasına güvenme
- [ ] Fatura durumunu manuel durumdan değil ödeme toplamı + vade kurallarından türeten tek servis oluştur
- [ ] SQLite foreign key enforcement ve gerekli `CHECK` constraintlerini etkinleştir

Kabul ölçütü: negatif fatura, %100 üzeri iskonto, orphan invoice ve yanlış “ödendi” durumu veritabanına yazılamamalı.

### DATA-003 — Gerçek migration ve yedekleme zinciri kur

- [ ] Alembic/Flask-Migrate ekle; `create_all` + elle `ALTER TABLE` yaklaşımını bırak
- [ ] Migrationları hem boş veritabanında hem mevcut veri kopyasında CI içinde çalıştır
- [ ] Günlük otomatik SQLite backup, rotation, bütünlük kontrolü ve restore komutu ekle
- [ ] Backup dosyalarını uygulama veritabanıyla aynı diskte tek kopya olarak bırakma
- [ ] Restore tatbikatını belgeleyip test et

Kabul ölçütü: son üretim verisinin kopyası yeni bir makinede belgelenmiş tek komut dizisiyle geri açılabilmeli.

## P1 — 1–3 hafta içinde

### APP-001 — Transaction ve hata yönetimini merkezileştir

- [ ] Service metotlarının içeride `commit()` etmesini bırak; transaction sınırını route/use-case katmanında yönet
- [ ] `IntegrityError`, bozuk JSON, eksik form alanı ve beklenmeyen DB hatalarında rollback + kullanıcıya güvenli 4xx yanıtı ver
- [ ] `except Exception: pass` bloklarını yapılandırılmış log ve kontrollü hata akışıyla değiştir
- [ ] 404, 403, 409, 422 ve 500 hata sayfaları/API yanıtları ekle
- [ ] Uygulama açılışında eksik tahsilat üretme gibi veri değiştiren “self-healing” işlemleri açık migration/management komutuna taşı

### APP-002 — Savunmacı doğrulamayı tamamla

- [ ] Geçersiz `?type=` değerinin `PartyType(...)` üzerinden 500 üretmesini engelle
- [ ] Tedavi ekle/düzenle route'larında doğrudan `float(...)` ve zorunlu `request.form[...]` kullanımlarını doğrulama şemasına taşı
- [ ] E-posta, telefon, tarih aralığı, enum ve yüklenen XLSX boyut/satır limitlerini doğrula
- [ ] `MAX_CONTENT_LENGTH` ve yükleme zaman/açıklık limitleri ekle
- [ ] Flask-WTF form sınıfları veya Pydantic/Marshmallow benzeri tek bir doğrulama yaklaşımı seç

### APP-003 — Fatura numarası üretimini yarış koşuluna dayanıklı yap

- [ ] “Oku → artır” akışını atomik transaction/sequence yaklaşımına çevir
- [ ] Ayar satırı yoksa oluştur; güncellenmeyen counter ile tekrar `0001` üretme riskini kaldır
- [ ] Eşzamanlı iki fatura oluşturma testi ekle
- [ ] Unique conflict sonrası rollback ve güvenli retry uygula

### UX-001 — Aranabilir select bileşenini erişilebilir yap

- [ ] Gizlenen `<select>` yerine WAI-ARIA combobox/listbox desenini uygula veya erişilebilir hazır bileşen kullan
- [ ] Görsel inputu gerçek label ile ilişkilendir; `aria-expanded`, `aria-controls`, aktif seçenek ve sonuç sayısını yönet
- [ ] Arrow Up/Down, Enter, Escape, Tab ve screen reader akışlarını destekle
- [ ] Mouse `mousedown` olayına bağımlılığı kaldır
- [ ] Playwright/axe veya eşdeğer E2E erişilebilirlik testi ekle

### UX-002 — Mobil veri yoğun ekranları iyileştir

- [ ] Kişi, fatura, tedavi ve tahsilat tablolarını 400 px altında kart/satır özeti görünümüne dönüştür veya yatay kaydırma ipucunu görünür yap
- [ ] Mobilde birincil işlem, kimlik, tutar ve durumun ekrana kaydırmadan görünmesini sağla
- [ ] Arama placeholder'ının kesilmesini ve yoğun filtre satırlarını düzelt
- [ ] 320, 375, 400, 768 ve 1024 px görsel regresyon matrisi ekle

### UX-003 — Semantik ve mikro-kopya temizliği

- [ ] `parties/list.html` boş filtrede oluşan `lar - Makro Ortodonti` sayfa başlığını düzelt
- [ ] Sayfanın ana başlığını tek `h1` yap; form kartlarında `h5` ile başlayan seviye atlamalarını düzelt
- [ ] Dekoratif Bootstrap ikonlarını `aria-hidden="true"` yap; erişilebilir adlarda özel ikon karakterlerini kaldır
- [ ] Navigasyon linklerine ilgili sayfada `aria-current="page"` ekle
- [ ] Navigasyon yapan linklerde yanlış `role="tab"` kullanımını kaldır veya gerçek tab davranışı uygula
- [ ] Flash kapatma butonlarına erişilebilir ad ekle

### OPS-001 — Üretim çalıştırma modelini kur

- [ ] Flask development server yerine Gunicorn/Waitress benzeri WSGI sunucu ve açık production komutu ekle
- [ ] Health/readiness endpointleri, yapılandırılmış log, request ID ve hata izleme ekle
- [ ] Döviz kuru güncellemesini request içinde daemon thread başlatmak yerine scheduler/job olarak çalıştır
- [ ] Job başarısızlığını sessizce yutma; son başarı, hata ve retry bilgisini görünür kıl
- [ ] Bootstrap, ikon ve fontları self-host et veya SRI + kontrollü CSP uygula; çevrimdışı/kapalı ağ davranışını test et

## P2 — 1–2 ay içinde

### QA-001 — Kalite kapılarını otomatikleştir

- [ ] `pyproject.toml` ekle; paket/import düzenini standartlaştır ve doğrudan `pytest` kullanımını düzelt
- [ ] Ruff/Black, mypy/pyright, Bandit/Semgrep ve dependency vulnerability taramasını CI'a ekle
- [ ] Coverage ölçümü ekle; başlangıç tabanını kaydet ve kritik service/route alanlarında en az %85 branch hedefle
- [ ] CSRF açık entegrasyon testleri ekle; mevcut fixture'ın `WTF_CSRF_ENABLED=False` olmasını ayrı test katmanıyla dengele
- [ ] Gerçek tarayıcı E2E: login, kişi, fatura, ödeme, PDF, yetkisiz rol ve mobil menü
- [ ] Property-based test: KDV/iskonto/kur/yuvarlama invariantları
- [ ] Test süresini profille; 73 test için yaklaşık 58 saniyelik süreyi düşür

### ARCH-001 — Domain katmanını sadeleştir

- [ ] `models.py` monolitini party, billing, catalog, identity ve settings modüllerine ayır
- [ ] Para hesaplarını saf domain fonksiyonlarına taşı
- [ ] Route'ları ince controller; use-case/service katmanını framework'ten bağımsız hale getir
- [ ] DTO/form şemaları ile ORM modellerini doğrudan request payloadı taşımaktan ayır
- [ ] Uygulama context processor'ının her render'da DB transaction açıp veri değiştirmesini kaldır

### PERF-001 — Ölçek ve sorgu bütçesi

- [ ] Kişi/fatura/tahsilat listelerine sunucu taraflı pagination ekle
- [ ] Rapor sorgularını Python listeleri yerine uygun SQL aggregate sorgularına taşı
- [ ] Slow-query ölçümü ve sayfa başına sorgu bütçesi tanımla
- [ ] SQLite WAL, busy timeout ve eşzamanlı yazma sınırlarını test et
- [ ] Büyüme eşiği belirle; çok kullanıcılı/uzaktan erişimde PostgreSQL geçiş planı hazırla

### PRIV-001 — Sağlık ve finans verisi mahremiyeti

- [ ] Kişi, fatura, tahsilat ve ayar değişiklikleri için aktör/zaman/eski-yeni değer audit logu ekle
- [ ] Rol matrisini admin/staff ikilisinden görüntüleme, finans, klinik ve ayar yetkilerine ayır
- [ ] KVKK veri saklama, silme/anonymization, dışa aktarma ve erişim talebi akışlarını tanımla
- [ ] Veritabanı ve backup için disk/uygulama seviyesinde şifreleme yaklaşımı belirle
- [ ] Log ve hata mesajlarında hasta, e-posta, telefon, credential ve SMTP ayrıntılarını maskele

## P3 — Ürün olgunlaştırma

- [ ] WhatsApp bağlantı durumunu process belleğinden kalıcı ve doğrulanabilir state'e taşı
- [ ] E-posta/WhatsApp gönderimlerini kuyruk, retry, idempotency ve teslimat kaydıyla yönet
- [ ] Fatura/PDF için yasal belge gereksinimlerini mali müşavirle doğrula; “fatura” ile tahsilat belgesi ayrımını netleştir
- [ ] İptal/iade/kredi bakiyesi ve kısmi ödeme iş kurallarını ürün seviyesinde tamamla
- [ ] Dashboard metriklerine tarih aralığı ve tanım tooltipleri ekle
- [ ] `PLAN.md` içindeki eski dosya yapısı/veri şeması anlatımını uygulama gerçekliğiyle eşleştir

## Üretime çıkış kapısı

Aşağıdaki maddeler tamamlanmadan uygulama internete açık üretim sistemi olarak değerlendirilmemelidir:

- [ ] Tüm P0 maddeleri tamamlandı
- [ ] Açık yüksek/kritik güvenlik bulgusu yok
- [ ] `Party/Patient` tek kaynak migrationı ve finansal invariantlar doğrulandı
- [ ] Backup alındı ve boş makinede restore tatbikatı geçti
- [ ] Migrationlar mevcut üretim veri kopyasında geçti
- [ ] CSRF açık testler, E2E kritik akışlar ve erişilebilirlik taraması geçti
- [ ] Production WSGI + HTTPS + secure cookie + security header yapılandırması doğrulandı
- [ ] Structured log, health check ve hata alarmı çalışıyor
- [ ] Son test raporu ve bilinen riskler sürüm notuna eklendi

## Standart doğrulama komutları

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m compileall -q app tests run.py init_db.py
.venv/bin/pip check
```
