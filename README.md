# Makro Ortodonti

Makro Ortodonti; hasta ve müşteri kayıtlarını, tedavi kataloğunu, EUR bazlı faturaları, tahsilatları ve klinik raporlarını tek yerde yöneten Flask tabanlı bir klinik operasyon uygulamasıdır.

## Öne çıkan özellikler

- Hasta, diş hekimi müşterisi ve kurumsal müşteri yönetimi
- Tedavi kataloğu ve Excel içe aktarma
- EUR bazlı fatura, KDV/iskonto ve sabit fatura kuru
- Kısmi tahsilat, vade takibi ve fazla ödeme koruması
- Dönem hareketleri ile dönem sonu alacak yaşlandırması
- Türkçe PDF fatura çıktısı ve SMTP ile gönderim
- WhatsApp bağlantısı ve gönderim akışları
- Admin/staff rolleri, CSRF koruması ve giriş denemesi kilidi
- Veritabanı health check ve doğrulamalı SQLite yedekleme
- Responsive, klavye odağı görünür klinik yönetim arayüzü

## Teknoloji

- Python 3.13+
- Flask, Flask-Login, Flask-WTF ve Flask-SQLAlchemy
- SQLite, SQLAlchemy 2, Alembic/Flask-Migrate ve kesin ölçekli `Numeric` finans alanları
- Jinja2, Bootstrap 5 ve özel tasarım sistemi
- fpdf2, OpenPyXL ve Neonize
- Gunicorn production sunucusu
- Pytest ve branch coverage

## Hızlı başlangıç

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
cp .env.example .env
python init_db.py
python run.py
```

Uygulama varsayılan olarak `http://127.0.0.1:5000` adresinde açılır. `init_db.py`, ilk admin kullanıcısı için güvenli bir parola üretir ve yalnızca oluşturma anında terminale yazar. Sabit bir başlangıç parolası gerekiyorsa veritabanını oluşturmadan önce `DEFAULT_ADMIN_PASSWORD` tanımlanabilir.

## Ortam değişkenleri

| Değişken | Açıklama | Varsayılan |
| --- | --- | --- |
| `SECRET_KEY` | Oturum imzalama anahtarı; production için zorunlu | Development anahtarı |
| `ENCRYPTION_KEY` | SMTP gibi hassas ayarlar için ayrı şifreleme anahtarı; production için zorunlu | Development anahtarı |
| `DATABASE_URL` | SQLAlchemy SQLite bağlantısı | `sqlite:///.../data/makroortodonti.db` |
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

## Production çalıştırma

```bash
export SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export ENCRYPTION_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(48))')"
export SESSION_COOKIE_SECURE=true
export FORCE_HSTS=true
flask --app run:app db upgrade
python run_production.py
```

Health/readiness kontrolü kimlik doğrulama gerektirmez:

```bash
curl http://127.0.0.1:8000/health
# {"db":true,"status":"ok"}
```

SQLite küçük klinik ekipleri için uygundur. Yoğun eşzamanlı yazma veya çok sunuculu dağıtım gerekiyorsa PostgreSQL'e geçiş planlanmalıdır.

## Migration ve veri geçişi

Yeni kurulum ve mevcut veritabanı aynı Alembic zincirini kullanır:

```bash
python backup.py backup
flask --app run:app db upgrade
flask --app run:app db current
```

İlk revision eski `Patient` kayıtlarını `Party` ile eşler, tedavi geçmişini `party_id` üzerine taşır ve finans kolonlarını `Numeric` yapar. SQLite batch geçişi sonunda foreign-key kontrolü başarısızsa migration da başarısız olur. Uygulama yeni legacy `Patient` satırı üretmez; tablo yalnızca kontrollü geriye dönük veri geçişi için tutulur.

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

- ORM değişiklikleri aktör, endpoint, IP ve `X-Request-ID` ile aynı transaction içinde `audit_logs` tablosuna yazılır.
- Admin denetim ekranı: `/privacy/audit`.
- Kişi veri paketi: `/privacy/parties/<id>/export`.
- Anonimleştirme, açık finansal kayıt varsa `409` ile reddedilir.
- `AUDIT_RETENTION_DAYS` yalnızca kurumun onaylı saklama politikasına göre ayarlanmalıdır.

## Veritabanı yedekleme

Tutarlı bir online SQLite yedeği oluşturmak ve son 30 kopyayı saklamak için:

```bash
python backup.py backup
python backup.py list
python backup.py verify
```

Farklı saklama adedi:

```bash
python backup.py backup --keep 14
```

Geri yükleme aktif veritabanını değiştirir. Önce uygulamayı tamamen durdurun; araç mevcut veritabanının ayrıca doğrulanmış güvenlik kopyasını alır ve yeni dosyayı atomik olarak yerleştirir:

```bash
python backup.py restore data/backups/makroortodonti_YYYY-MM-DDTHH-MM-SS-ffffff.db --yes
```

Yerel backup dizini tek başına felaket kurtarma çözümü değildir. Yedekler erişim kontrollü, şifreli ve farklı bir fiziksel konuma düzenli olarak kopyalanmalıdır.

## Test ve kalite kontrolleri

```bash
pytest
pytest --cov=app --cov-report=term-missing --cov-fail-under=70
pytest tests/e2e --browser chromium
python -m compileall -q app backup.py run.py run_production.py
python -m pip check
```

GitHub Actions, her push ve pull request için Python 3.13/3.14 üzerinde derleme, Playwright Chromium kurulumu, test ve branch coverage kapısını çalıştırır. E2E paketi masaüstü ve 400×765 mobil axe WCAG taraması yapar.

## Güvenlik notları

- Form gönderimleri CSRF ile korunur.
- Parolalar bcrypt ile hashlenir; SMTP şifresi ayrı `ENCRYPTION_KEY` üzerinden Fernet ile doğrulamalı olarak şifrelenir.
- Eski XOR/Base64 biçimindeki SMTP şifreleri güvenli biçimde çözülemez. Güncellemeden sonra Ayarlar ekranından SMTP şifresini bir kez yeniden kaydedin.
- Fatura satırları sunucuda doğrulanır; negatif tutar, geçersiz KDV/iskonto ve eksik referans reddedilir.
- Bootstrap, ikonlar, font ve axe varlıkları self-host edilir; çalışma zamanında üçüncü taraf CDN çağrısı yoktur.
- CSP, `X-Content-Type-Options`, Referrer Policy, Permissions Policy ve `X-Request-ID` her yanıta eklenir; HSTS yalnızca doğrulanmış HTTPS ortamında açılır.
- Hasta ve finans verileri KVKK kapsamındadır. Veritabanı, yedekler ve uygulama logları yalnızca yetkili kişilerce erişilebilir olmalıdır.

## Proje yapısı

```text
app/
  models/       SQLAlchemy modelleri ve fatura servisleri
  routes/       Flask blueprint/controller katmanı
  services/     PDF, e-posta, kur, güvenlik ve WhatsApp servisleri
  templates/    Jinja2 arayüzleri
  static/       Tasarım sistemi, JavaScript, marka ve PDF fontları
tests/          Kritik akış, güvenlik ve kalite testleri
backup.py       SQLite backup/verify/restore aracı
init_db.py      İlk veritabanı ve admin oluşturma
run.py          Development giriş noktası
run_production.py  Gunicorn production giriş noktası
```

`PLAN.md` ürün vizyonunu, `TODO.md` ise doğrulanmış teknik takip maddelerini içerir.

## Lisans ve kullanım

Bu depo özel klinik kullanımı için geliştirilmiştir. Dağıtım, hasta verisi işleme ve üçüncü taraf entegrasyonları kurumun güvenlik ve KVKK politikalarına uygun yürütülmelidir.
