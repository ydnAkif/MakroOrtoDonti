# Makro Ortodonti

Makro Ortodonti; hasta ve müşteri kayıtlarını, işlem kataloğunu, EUR bazlı faturaları, tahsilatları ve klinik raporlarını tek yerde yöneten Flask tabanlı bir klinik operasyon uygulamasıdır.

## Öne çıkan özellikler

- Hasta, diş hekimi müşterisi ve kurumsal müşteri yönetimi
- İşlem kataloğu (Ana İşlemler / Ekstra İşlemler) ve Excel içe aktarma
- EUR bazlı fatura, KDV/iskonto ve sabit fatura kuru
- Kısmi tahsilat, vade takibi ve fazla ödeme koruması
- Dönem hareketleri ile dönem sonu alacak yaşlandırması
- Türkçe PDF fatura çıktısı ve SMTP ile gönderim
- WhatsApp bağlantısı ve gönderim akışları
- Admin/staff rolleri, CSRF koruması ve giriş denemesi kilidi
- Değişiklik audit'i, KVKK export/anonimleştirme ve saklama politikası
- Veritabanı health check, şifreli/doğrulamalı SQLite yedekleme ve atomik restore
- Responsive, klavye odağı görünür klinik yönetim arayüzü

## Teknoloji

- Python 3.13 ve 3.14 (CI ile doğrulanan sürümler)
- Flask, Flask-Login, Flask-WTF ve Flask-SQLAlchemy
- SQLite, SQLAlchemy 2, Alembic/Flask-Migrate ve kesin ölçekli `Numeric` finans alanları
- Jinja2, Bootstrap 5 ve özel tasarım sistemi
- fpdf2, OpenPyXL ve Neonize
- Gunicorn production sunucusu
- Pytest ve branch coverage

## Yerel demo kurulumu

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
FLASK_DEBUG=true python run.py
```

Uygulama varsayılan olarak `http://127.0.0.1:5001` adresinde açılır. `run.py` ilk çalıştırmada örnek işlem kataloğunu (44 Ana İşlem + 10 Ekstra İşlem), kur, hasta ve müşteri kayıtlarıyla birlikte admin oluşturur. Üretilen admin parolası yalnız oluşturma anında terminale yazılır. Sabit bir başlangıç parolası gerekiyorsa veritabanını oluşturmadan önce `DEFAULT_ADMIN_PASSWORD` tanımlanabilir.

## Ortam değişkenleri

| Değişken | Açıklama | Varsayılan |
| --- | --- | --- |
| `SECRET_KEY` | Oturum imzalama anahtarı; production için zorunlu | Development anahtarı |
| `ENCRYPTION_KEY` | SMTP gibi hassas ayarlar için ayrı şifreleme anahtarı; production için zorunlu | Development anahtarı |
| `BACKUP_ENCRYPTION_KEYS` | Güncel anahtar önce olacak şekilde virgülle ayrılmış yedek şifreleme/rotasyon anahtarları | Boş |
| `DATABASE_URL` | SQLAlchemy SQLite bağlantısı | `sqlite:///.../data/makroortodonti.db` |
| `DATABASE_ENCRYPTION_AT_REST` | Sunucu disk/volume şifrelemesinin etkin olduğunu doğrulayan production beyanı | `false` |
| `REMOTE_BACKUP_URL` | Şifreli yedeklerin farklı fiziksel hedefi | Boş |
| `DEFAULT_ADMIN_PASSWORD` | İlk admin için isteğe bağlı parola | Güvenli rastgele parola |
| `FLASK_DEBUG` | Development debug modu | `false` |
| `SESSION_COOKIE_SECURE` | Cookie'yi yalnızca HTTPS üzerinden gönderir | `false` |
| `TRUST_PROXY` | Tek ve güvenilen reverse proxy başlıklarını kabul eder | `false` |
| `FORCE_HSTS` | TLS reverse proxy doğrulandıktan sonra HSTS başlığı gönderir | `false` |
| `AUDIT_RETENTION_DAYS` | Denetim kayıtlarının saklama süresi | `3650` |
| `SENTRY_DSN` | PII göndermeyen opsiyonel production hata izleme | Boş |
| `PORT`, `BIND`, `WORKERS` | Gunicorn ağ ve worker ayarları | `8000`, `0.0.0.0`, en fazla 4 worker |

Her anahtar için ayrı güçlü bir değer üretmek için komutu iki kez çalıştırın:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

Production ortamında `SECRET_KEY` veya `ENCRYPTION_KEY` eksik, 32 karakterden kısa ya da örnek değerdeyse uygulama güvenli biçimde başlamayı reddeder. Bu iki anahtar birbirinden farklı ve kalıcı olmalıdır. HTTPS arkasında `SESSION_COOKIE_SECURE=true` kullanılmalıdır. `TRUST_PROXY=true` yalnızca uygulamanın doğrudan internete kapalı olduğu ve tek güvenilir reverse proxy arkasında çalıştığı durumda açılmalıdır.

## Mevcut veritabanıyla production çalıştırma

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export ENCRYPTION_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export SESSION_COOKIE_SECURE=true
export FORCE_HSTS=true
export DATABASE_ENCRYPTION_AT_REST=true
flask --app run:app db upgrade
gunicorn --workers 1 --bind 0.0.0.0:8000 "run:app"
```

> **Not:** WhatsApp entegrasyonu nedeniyle gunicorn **tek worker** ile çalıştırılmalıdır (aşağıya bakın).

Health/readiness kontrolü kimlik doğrulama gerektirmez:

```bash
curl http://127.0.0.1:8000/health
# {"db":true,"status":"ok"}
```

SQLite küçük klinik ekipleri için uygundur. Yoğun eşzamanlı yazma veya çok sunuculu dağıtım gerekiyorsa PostgreSQL'e geçiş planlanmalıdır.

## Migration ve veri geçişi

Mevcut veritabanını yükseltmeden önce doğrulanmış backup alın:

```bash
flask --app run:app db upgrade
flask --app run:app db current
```

İlk revision boş şemayı da oluşturabilir; ancak uygulama için zorunlu settings/admin bootstrap'ını yapmaz. Mevcut veride eski `Patient` kayıtlarını `Party` ile eşler, tedavi geçmişini `party_id` üzerine taşır ve finans kolonlarını `Numeric` yapar. `20260720_02` migration'ı mevcut tedavi kataloğunu siler ve Makro Ortodonti'ye özel 54 işlemle (44 Ana İşlemler + 10 Ekstra İşlemler) yeniden doldurur; bu migration'idempotent değildir ve yalnız bir kez çalıştırılmalıdır. SQLite batch geçişi sonunda foreign-key kontrolü başarısızsa migration da başarısız olur. Uygulama yeni legacy `Patient` satırı üretmez; tablo yalnızca kontrollü geriye dönük veri geçişi için tutulur.

## WhatsApp bağlantısı

WhatsApp gönderimi [Neonize](https://github.com/krypton-byte/neonize) (WhatsApp Web protokolü) ile çalışır; ücretli bir API gerektirmez. Bağlantı akışı:

1. Uygulamayı başlatın ve **WhatsApp** sayfasını açın (`/whatsapp/`).
2. **Bağlan** butonuna tıklayın. Sayfa birkaç saniye içinde QR kod gösterir.
3. Telefonunuzda WhatsApp > Bağlı Cihazlar > Cihaz Bağla ile QR kodu tarayın. (Telefon numarası girerseniz QR yerine eşleştirme kodu gösterilir.)
4. Tarama sonrası sayfa otomatik olarak "Bağlı" durumuna geçer.

Oturum `data/whatsapp_session.db` dosyasında saklanır; uygulama yeniden başlatıldığında bu dosya varsa arka planda otomatik yeniden bağlanır, tekrar QR taraması gerekmez. Kenar çubuğundaki WhatsApp menüsünde bağlantı durumu (yeşil/sarı/gri nokta) görünür; bağlantı yokken Genel Bakış sayfası "Bağlan" yönlendirmesi gösterir.

**Makbuz gönderimi (WhatsApp sayfasından):** WhatsApp sayfasındaki "Makbuz Gönderimi" paneli seçilen dönemin makbuzlu doktorlarını listeler. Doktorlar tek tek veya "Gönderilmemişleri Seç" ile toplu seçilir; gönderim arka planda kuyruk olarak çalışır (doktorlar arasında 3 saniye bekleme), ilerleme sayfada canlı izlenir. Her başarılı gönderimde makbuz "Gönderildi" durumuna geçer. Aynı anda tek toplu gönderim çalışır; telefonu olmayan doktorlar seçilemez ve dönemde makbuzu oluşturulmamış doktor varsa panel Makbuzlar sayfasına yönlendirir.

**Gönderim geçmişi:** Her gönderim denemesi (el ile veya otomatik) `makbuz_send_logs` tablosuna kalıcı olarak yazılır ve WhatsApp sayfasındaki "Gönderim Geçmişi" bölümünde tarih, doktor, dönem, sonuç ve kaynak bilgisiyle listelenir. Yeni tabloyu oluşturmak için `flask --app run:app db upgrade` çalıştırın.

**Otomatik gönderim:** WhatsApp sayfasındaki "Otomatik gönderim" anahtarı açıksa, her ayın 1'inde saat 06:30'da (06:00'daki otomatik taslak üretiminden sonra) önceki ayın taslak makbuzları telefonu kayıtlı doktorlara otomatik gönderilir. WhatsApp bağlı değilse gönderim atlanır ve log'a uyarı düşülür; taslaklar elle gönderilebilir. Ayar varsayılan olarak kapalıdır.

**Tek worker zorunluluğu:** WhatsApp istemcisi süreç içinde tek bir arka plan thread'inde çalışır ve oturum dosyası süreçler arasında paylaşılamaz. Gunicorn **`--workers 1`** ile çalıştırılmalıdır. Yanlışlıkla çok worker başlatılırsa `data/whatsapp.worker.lock` üzerindeki dosya kilidi sayesinde istemciyi yalnız bir worker sahiplenir; diğer worker'lardaki gönderimler açık bir hata mesajıyla reddedilir.

## Zamanlanmış işler

Döviz kuru artık kullanıcı isteği içinden thread başlatmaz. Sistem cron'u veya platform scheduler'ı günde bir kez şu komutu çalıştırmalıdır:

```bash
flask --app run:app refresh-exchange-rate
```

Audit saklama politikasını uygulamak için günlük/haftalık olarak:

```bash
flask --app run:app purge-expired-audit-logs
```

## Denetim ve KVKK

- ORM create/update/delete değişiklikleri aktör, endpoint, IP ve `X-Request-ID` ile aynı transaction içinde `audit_logs` tablosuna yazılır.
- Hasta kaydını yalnız görüntüleme gibi salt-okuma erişimleri bugün audit edilmez.
- Admin denetim ekranı: `/privacy/audit`.
- Kişi veri paketi: `/privacy/parties/<id>/export`.
- Anonimleştirme, açık finansal kayıt varsa `409` ile reddedilir.
- `AUDIT_RETENTION_DAYS` yalnızca kurumun onaylı saklama politikasına göre ayarlanmalıdır.

## Yetki matrisi

Route yetkileri merkezi ve adlandırılmıştır: `clinical.view/edit/delete`,
`billing.view/edit/delete`, `reports.view`, `messaging.use`, `settings.manage` ve
`privacy.audit/export/anonymize`. `staff` günlük klinik ve finans işlemlerini yapabilir;
kişi/hasta, fatura ve ödeme silme ile ayar ve KVKK işlemleri yalnız `admin`
yetkisindedir. Tedavi kataloğundaki soft-deactivate işlemi bugün `clinical.edit`
kapsamındadır.

## Veritabanı yedekleme

SQLite veritabanını yedeklemek için `data/` dizinindeki `.db` dosyasını kopyalayın.
Veritabanı, yedekler ve uygulama logları yalnızca yetkili kişilerce erişilebilir olmalıdır.

## Test ve kalite kontrolleri

```bash
pytest
pytest --cov=app --cov-report=term-missing --cov-fail-under=90
python -m playwright install chromium
pytest tests/e2e --browser chromium
python -m compileall -q app run.py
python -m pip check
```

GitHub Actions, her push ve pull request için Python 3.13/3.14 üzerinde derleme, Playwright Chromium kurulumu, test ve branch coverage kapısını çalıştırır.

## Güvenlik notları

- Form gönderimleri CSRF ile korunur.
- Parolalar bcrypt ile hashlenir; SMTP şifresi ayrı `ENCRYPTION_KEY` üzerinden Fernet ile doğrulamalı olarak şifrelenir.
- Eski XOR/Base64 biçimindeki SMTP şifreleri güvenli biçimde çözülemez. Güncellemeden sonra Ayarlar ekranından SMTP şifresini bir kez yeniden kaydedin.
- Fatura satırları sunucuda doğrulanır; negatif tutar, geçersiz KDV/iskonto ve eksik referans reddedilir.
- Bootstrap, ikonlar, font ve axe varlıkları self-host edilir; çalışma zamanında üçüncü taraf CDN çağrısı yoktur.
- CSP, `X-Content-Type-Options`, Referrer Policy, Permissions Policy ve `X-Request-ID` her yanıta eklenir; HSTS yalnızca doğrulanmış HTTPS ortamında açılır. Mevcut inline scriptler nedeniyle CSP `unsafe-inline` içerir; nonce/haricî script sertleştirmesi roadmap'tedir.
- Hasta ve finans verileri KVKK kapsamındadır. Veritabanı, yedekler ve uygulama logları yalnızca yetkili kişilerce erişilebilir olmalıdır.

## Bilinen sınırlar

- WhatsApp toplu gönderimi HTTP request içinde senkron ve kişi başına 3 saniye beklemeli çalışır.
- WhatsApp bağlantı durumu process-local olduğundan çoklu Gunicorn worker ile güvenilir değildir.
- SMTP/WhatsApp/kur/import akışlarının bazıları haricî exception metnini kullanıcı mesajına taşır.
- Login kilidi IP ve kullanıcı adını tek `OR` sayacında birleştirir; hedefli hesap kilitleme riskini azaltacak bağımsız limitler planlanmıştır.
- Transactional audit veri değişikliklerini kapsar, hassas salt-okuma erişimlerini kapsamaz.
- CSP inline JavaScript nedeniyle `script-src 'unsafe-inline'` kullanır.
- `/patients/` listesi henüz server-side pagination kullanmaz.
- SQLite küçük klinik dağıtımı içindir; yüksek eşzamanlılık ve çok sunuculu çalışma desteklenmez.

## Proje yapısı

```text
app/
  models/       SQLAlchemy modelleri ve fatura domain servisi
  routes/       Flask blueprint/controller katmanı
  services/     PDF, e-posta, kur, güvenlik ve WhatsApp servisleri
  templates/    Jinja2 arayüzleri
  static/       Tasarım sistemi, JavaScript, marka ve PDF fontları
tests/          Kritik akış, güvenlik ve kalite testleri
run.py          Development giriş noktası
```

## Lisans ve kullanım

Bu depo özel klinik kullanımı için geliştirilmiştir. Dağıtım, hasta verisi işleme ve üçüncü taraf entegrasyonları kurumun güvenlik ve KVKK politikalarına uygun yürütülmelidir.
