# Makro Ortodonti — Ürün ve Teknik Plan

Son güncelleme: 20 Temmuz 2026

Bu belge ürünün mevcut sınırlarını ve planlanan yönünü tanımlar. Uygulanmış özelliklerin kullanım ayrıntıları `README.md`, doğrulanmış teknik işler ve sürüm kapıları `TODO.md` içindedir.

## 1. Amaç

Makro Ortodonti, küçük bir klinikte hasta ve müşteri kayıtları ile tedavi, fatura, tahsilat ve iletişim operasyonlarını tek, self-hosted web uygulamasında yönetmek için geliştirilir.

Temel ilkeler:

- Klinik personeli günlük işi tek arayüzden ve düşük eğitim maliyetiyle yürütür.
- Finansal değerler EUR temelinde kesin `Decimal` hesaplanır; TRY karşılığı işlem tarihindeki kurla izlenir.
- Hasta ve müşteri verileri least-privilege, audit, şifreli yedek ve açık saklama politikasıyla korunur.
- SQLite küçük ekip dağıtımı için varsayılandır; ölçülen eşzamanlılık ihtiyacı artarsa PostgreSQL'e geçilir.
- Haricî servis kesintisi klinik ana kayıtlarına ve finansal bütünlüğe zarar vermez.

## 2. Mevcut ürün kapsamı

### Kimlik ve yetki

- Flask-Login oturumu, bcrypt parola hash'i ve CSRF koruması.
- `admin` ve `staff` rolleri için merkezi izin matrisi.
- Staff klinik, finans, rapor ve mesajlaşma işlerini yapabilir.
- Kişi/fatura/ödeme silme, ayar yönetimi, audit, KVKK export ve anonimleştirme admin-only'dir; tedavi kataloğu soft-deactivate işlemi `clinical.edit` kapsamındadır.

### Kişi ve klinik kayıtları

- `Party`, hasta, diş hekimi müşterisi ve kurumsal müşteri için operasyonel tek kaynaktır.
- Hasta tedavi geçmişi, yönlendiren diş hekimi ve kişi bazlı fatura geçmişi bulunur.
- `Patient` tablosu yalnız legacy migration/uyumluluk amacıyla tutulur.

### Tedavi, fatura ve tahsilat

- Kategorili tedavi kataloğu ve XLSX içe aktarma.
- Tedavi, ürün, hizmet, laboratuvar ve özel fatura kalemleri.
- KDV, yüzde/tutar iskontosu, atomik fatura numarası ve sabit fatura kuru.
- Kısmi tahsilat, ödeme kuru, vade durumu ve fazla ödeme koruması.
- Soft-delete/iptal ayrımı ve yetkiye bağlı silme işlemleri.

### Raporlama ve çıktı

- Dönem faturaları, tahsilatlar, açık alacaklar ve alacak yaşlandırması.
- Tedavi/kategori dağılımı ve EUR/TRY özetleri.
- Türkçe font destekli PDF fatura ve SMTP eki.

### İletişim

- Neonize ile WhatsApp bağlantı, tekil bildirim ve toplu mesaj arayüzü.
- SMTP ayarlarının veritabanında Fernet ile şifreli saklanması.
- WhatsApp toplu gönderimi bugün senkron çalışır; production ölçeği için `TODO.md` içindeki job kuyruğu işi zorunludur.

### Mahremiyet ve operasyon

- ORM değişikliklerini aktör, IP, endpoint ve request ID ile aynı transaction'da audit etme.
- Admin audit ekranı, kişi verisi export'u ve finansal kaydı koruyan anonimleştirme.
- Şifreli ve doğrulamalı SQLite backup, anahtar rotasyonu ve atomik restore.
- Health endpoint, yapılandırılmış access log, güvenlik başlıkları ve opsiyonel Sentry.

## 3. Sistem sınırları

```text
Tarayıcı
   |
   v
Flask / Gunicorn
   |-- auth + RBAC + CSRF
   |-- blueprint route'ları
   |-- domain/entegrasyon servisleri
   |
   +--> SQLite / SQLAlchemy / Alembic
   +--> SMTP
   +--> Neonize / WhatsApp
   +--> Frankfurter EUR/TRY API
   +--> şifreli off-host backup hedefi
```

Bugünkü varsayılan dağıtım tek uygulama hostu ve küçük klinik ekibidir. Gunicorn birden fazla HTTP worker çalıştırabilse de process-local WhatsApp durumu çoklu worker için henüz güvenli değildir. SQLite için foreign key ve busy timeout açıktır; bu ayarlar yüksek yazma eşzamanlılığının yerine geçmez.

## 4. Veri modeli özeti

```text
Party
 |-- PatientTreatment --> Treatment
 |-- Invoice --> InvoiceItem --> Treatment (opsiyonel)
              `-> Payment
 |-- referred_by --> Party (diş hekimi)

User --> LoginAttempt
AuditLog
Settings
ExchangeRate
WhatsAppSession

Patient -- legacy compatibility --> Party
```

Finansal alanlar SQL `Numeric`, Python tarafında `Decimal` kullanır. `Party` yeni klinik kayıtlarının tek kaynağıdır; yeni kod `Patient` tablosuna bağımlılık eklememelidir.

## 5. Yol haritası

### Faz A — Güvenli ilk production

Başarı ölçütü: `TODO.md` sürüm kapısının tamamı kanıtlanmış, geri yükleme başka makinede yapılmış ve kurum sorumluları atanmış olmalıdır.

- Secret store ve gerçek TLS/proxy doğrulaması.
- Demo veri üretmeyen, idempotent ilk admin/settings bootstrap komutu.
- Off-host şifreli backup ve restore tatbikatı.
- Scheduler işleri ve başarısızlık alarmları.
- KVKK yetki, saklama, export ve olay müdahale prosedürü.

### Faz B — İletişim ve güvenlik sertleştirmesi

Başarı ölçütü: HTTP request içinde uzun gönderim kalmaz; dış servis hata ayrıntısı kullanıcıya sızmaz; CSP inline script izni olmadan çalışır.

- Bağımsız IP/hesap rate limit modeli.
- WhatsApp job kuyruğu ve process-independent bağlantı sahibi.
- SMTP/WhatsApp timeout, retry, idempotency ve gözlemlenebilirlik.
- Nonce veya haricî JavaScript ile sıkı CSP.
- Kurum kararına göre hassas okuma audit'i.

### Faz C — Domain ve test sadeleştirmesi

Başarı ölçütü: transaction sahibi açık, route'larda tekrar eden doğrulama azalır ve hızlı test paketi birkaç dakika yerine kısa feedback sağlar.

- Invoice servisinde commit sınırının üst katmana taşınması.
- Party/form doğrulama servisi ve veri tabanı hata çevirisi.
- Legacy/ölü kod temizliği ve model zaman semantiğinin birleştirilmesi.
- Mükerrer coverage testlerinin davranış odaklı test matrisine dönüştürülmesi.
- Lint, dependency scan ve CI timeout/concurrency kontrolleri.

### Faz D — Ölçüme bağlı ölçek

Başarı ölçütü: hedef p95 yanıt süresi ve eşzamanlı yazma kapasitesi ölçülür; PostgreSQL kararı tahmine değil yük testine dayanır.

- Hasta listesi pagination ve rapor sorgusu ölçümü.
- Merkezi metrik/alert panosu.
- Gerekiyorsa PostgreSQL migration, backup ve rollback runbook'u.
- Randevu, stok, çoklu şube ve API gibi ürün genişletmelerinin klinik ihtiyacıyla önceliklendirilmesi.

## 6. Kapsam dışı veya karar bekleyenler

- Uygulama hukuki KVKK uyumunu tek başına garanti etmez; teknik kontroller kurum süreçlerinin yerine geçmez.
- Çoklu şube, randevu, stok ve mobil API mevcut teslimat kapsamı değildir.
- WhatsApp mesaj teslim/okunma durumu ve PDF dosyası gönderimi mevcut metin bildirimi akışının garanti edilmiş parçası değildir.
- Yüksek erişilebilirlik ve çok sunuculu çalışma PostgreSQL ve process-independent entegrasyon durumu tamamlanmadan desteklenmez.
- Production verisi geliştirici bilgisayarına kopyalanmamalıdır; tatbikat yalnız erişim kontrollü ve anonimleştirilmiş kopyayla yapılır.

## 7. Karar kayıtları

| Karar | Gerekçe | Yeniden değerlendirme tetikleyicisi |
| --- | --- | --- |
| `Party` tek doğruluk kaynağı | Hasta dışı müşterileri aynı finans akışında yönetmek | Legacy `Patient` bağımlılıkları sıfırlandığında tabloyu kaldırma |
| EUR temel para birimi | Klinik fiyatlandırma modeli ve sabit fatura kuru | Muhasebe/yerel para gereksinimi değişirse |
| SQLite varsayılanı | Küçük ekip, kolay self-hosting ve düşük operasyon maliyeti | Ölçülen kilitlenme, write throughput veya HA ihtiyacı |
| Admin-only ayar/KVKK/kişi-finans silme | Least privilege ve geri döndürülemez işlemleri sınırlandırma | Kurumda yeni rol ve onay akışı tanımlanırsa |
| Scheduler ile kur yenileme | Request yaşam döngüsünden bağımsız ve gözlenebilir çalışma | Platform-native job altyapısı seçilirse |

## 8. Kalite hedefleri

- Branch-aware coverage alt sınırı: %90; kritik davranış testi coverage yüzdesinden önceliklidir.
- Desteklenen Python: CI üzerinde 3.13 ve 3.14.
- Kritik E2E: giriş, kişi → fatura → ödeme, güvenlik başlıkları ve ciddi/kritik axe ihlali olmaması.
- Finans: tüm tutarlar `Decimal`; float ile para karşılaştırması kabul edilmez.
- Güvenlik: production secret'ları fail-closed; staff least-privilege; kullanıcıya ham exception dönmez.
- Operasyon: son başarılı backup yaşı, restore kanıtı, kur güncelliği ve dış servis başarısızlığı gözlenebilir olmalıdır.
