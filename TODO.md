# Makro Ortodonti — Doğrulanmış Teknik Roadmap

Son güncelleme: 20 Temmuz 2026

Bu belge yalnızca mevcut koddan, çalışan testlerden ve production kontrol zincirinden doğrulanmış işleri içerir. Öznel `92/100` benzeri skorlar kaldırılmıştır; sürüm kararı tamamlanma kanıtlarına göre verilir.

## Güncel doğrulama özeti

| Kontrol | Sonuç |
| --- | --- |
| Test keşfi | 421 test öğesi: 416 Python/Flask + parametrizasyonla 5 Playwright |
| Python/Flask paketi | 416 geçti (`Python 3.14.6`, 276,53 sn) |
| Playwright paketi | 5 geçti (Chromium; mobil ve masaüstü axe dâhil) |
| Branch-aware coverage | %95,82; kapı %90 |
| CI matrisi | Python 3.13 ve 3.14 |
| Çalışma ağacı | İnceleme başında temiz |

Coverage yüksek olsa da test sayısı ve coverage tek başına production hazırlığı anlamına gelmez. Aşağıdaki operasyonel kapılar ile güvenlik ve eşzamanlılık işleri ayrıca tamamlanmalıdır.

## Sürüm kapısı — kurum ve altyapı tarafından doğrulanacak

- [ ] `SECRET_KEY`, `ENCRYPTION_KEY` ve güncel backup anahtarı farklı, kalıcı değerler olarak secret store'da tanımlı.
- [ ] `SESSION_COOKIE_SECURE=true`, `FORCE_HSTS=true` ve gerekiyorsa `TRUST_PROXY`/`FORWARDED_ALLOW_IPS` staging üzerinde gerçek TLS zinciriyle doğrulandı.
- [ ] Aktif SQLite dosyasının bulunduğu disk/volume şifreli; dosya ve uygulama loglarına erişim yalnız yetkili hesaplarla sınırlı.
- [ ] Şifreli yedek farklı fiziksel hedefe kopyalandı, doğrulandı ve başka bir makinede restore tatbikatı geçti.
- [ ] Günlük kur yenileme ile audit purge komutları scheduler'a bağlandı ve başarısızlıkları için alarm tanımlandı.
- [ ] KVKK veri sorumlusu, yetki onaylayan kişi, saklama süresi sahibi ve olay müdahale sorumlusu belirlendi.
- [ ] Neonize/WhatsApp kullanımı, SMTP gönderimi ve hasta iletişim izinleri kurum politikası ile hukuken onaylandı.

## P1 — Güvenlik ve çalışma zamanı güvenilirliği

### Taze production bootstrap akışı ekle

- [ ] Örnek hasta/kurum/kur ve tedavi kayıtlarını oluşturmadan yalnız zorunlu `Settings` satırlarını ve ilk admini idempotent oluşturan CLI komutu ekle.
- [ ] İlk admin parolasını secret store/güvenli tek kullanımlık kanal üzerinden al; normal uygulama loguna yazma.
- [ ] Boş veritabanında `db upgrade -> bootstrap -> login -> ilk fatura` E2E testi ekle.

Bugün `init_db.py` development/demo verisi seed eder; yalnız `flask db upgrade` ise admin ve `invoice_next_number` oluşturmaz. Bu nedenle yeni production kurulumu için belgelenebilir, demosuz bir bootstrap komutu mevcut değildir.

### Giriş denemesi sınırlandırmasını yeniden tasarla

- [ ] `IP OR username` ile tek sayaç yerine IP ve hesap için bağımsız limitler, ayrı eşikler ve artan bekleme süresi uygula.
- [ ] Tek bir hesaba farklı IP'lerden yanlış parola gönderilerek kalıcı hizmet engelleme oluşmamasını test et.
- [ ] Aynı IP'den farklı kullanıcı adlarıyla credential-stuffing yapılmasını engelleyen test ekle.
- [ ] Eski `login_attempts` kayıtları için saklama/purge politikası ekle.

Mevcut `OR` sorgusu hem IP'yi hem hedef hesabı 5 hata/15 dakika eşiğine bağlar. Bunu doğrudan `AND` yapmak doğru çözüm değildir; iki saldırı ekseni ayrı izlenmelidir.

### WhatsApp gönderimini worker-safe ve asenkron yap

- [ ] Toplu gönderimdeki kişi başına `time.sleep(3)` ve senkron WSGI döngüsünü kalıcı job kuyruğuna taşı.
- [ ] Job durumu, kısmi hata, yeniden deneme, idempotency ve gönderim sonucunu veri tabanında sakla.
- [ ] `WhatsAppService._client/_connected` process-local durumunu Gunicorn çoklu worker modeliyle uyumlu hâle getir veya WhatsApp'ı tek ayrı worker servisine ayır.
- [ ] Telefon normalizasyonu, gönderim kotası ve hasta iletişim izni kontrolünü merkezileştir.

Mevcut akışta 50 alıcı en az 150 saniye request süresi üretir. Ayrıca bir worker'da kurulan bağlantı başka worker tarafından görülmez.

### Dış servis hatalarını kullanıcıdan ayır

- [ ] SMTP, WhatsApp, kur yenileme ve XLSX import exception metinlerini yalnız server loguna yaz; kullanıcıya sabit, eyleme dönük hata kodu ve request ID göster.
- [ ] SMTP bağlantısına açık timeout ve güvenli kapanış (`with`/`quit` fallback) ekle.
- [ ] SMTP TLS sertifika doğrulaması ve desteklenen port/TLS modu için production testi ekle.

Şu anda bazı `str(exc)` değerleri flash mesajına dönüyor; DNS, sunucu veya bağlantı ayrıntısı açığa çıkabilir.

### CSP'yi sıkılaştır

- [ ] Şablonlardaki inline `<script>`, `onclick` ve `onchange` kodlarını `app/static/js/` altına taşı veya request başına nonce kullan.
- [ ] `script-src 'unsafe-inline'` kaldırıldıktan sonra CSP regresyon testi ekle.
- [ ] Inline `style` ihtiyacını azaltıp mümkünse `style-src 'unsafe-inline'` için de nonce/hash planla.

Mevcut CSP yararlı bir temel oluşturur; ancak `unsafe-inline` nedeniyle güçlü bir script allowlist sağlamaz. Bu ifade tek başına kanıtlanmış XSS açığı değildir.

### Hassas veri erişim audit kapsamını kararlaştır

- [ ] Hasta detay görüntüleme, KVKK export ve anonimleştirme gibi hassas endpoint'ler için erişim olayı kaydedilip kaydedilmeyeceğini kurum politikasıyla belirle.
- [ ] Erişim kaydı tutulacaksa veri içeriğini loglamadan aktör, amaç/işlem, kişi ID, zaman ve request ID kaydet.
- [ ] Audit loglarının kendisine erişimi ve export işlemlerini ayrıca denetle.

Mevcut transactional audit yalnız ORM create/update/delete değişikliklerini kaydeder; salt-okuma erişimleri kapsam dışıdır.

## P2 — Veri bütünlüğü ve mimari bakım

### Finansal transaction sınırlarını sadeleştir

- [ ] `InvoiceService.create_invoice*()` içindeki `session.commit()` çağrılarını üst katmana taşı; servis `flush()` edip hatayı çağırana bırakmalı.
- [ ] `get_exchange_rate()` dönüş tipini `Decimal` yap ve fatura kodundaki `diff > 0.01` karşılaştırmasını `Decimal("0.01")` ile değiştir.
- [ ] Tutar iskontosu satır toplamlarını `money()` ile iki haneye normalize et.
- [ ] Fatura tarihi/son ödeme tarihi ve ödeme tarihi için kurumun izin verdiği tarih invariantlarını açıkça tanımlayıp test et.

### Party ve form doğrulamasını merkezileştir

- [ ] Hasta, kişi ve kurum ekleme/düzenleme route'larında ad, telefon, e-posta, vergi/kimlik numarası ve alan uzunluklarını ortak doğrulayıcıyla kontrol et.
- [ ] Unique constraint/`IntegrityError` durumlarını rollback edip kullanıcı dostu 409/validasyon mesajına çevir.
- [ ] `referred_by_id` için aktif diş hekimi türü doğrulaması yap; rastgele Party ID kabul etme.

### Model ve zaman semantiğini temizle

- [ ] `PatientTreatment.patient` ilişkisinin iki kez tanımlanmasını kaldır.
- [ ] Audit ve WhatsApp zaman alanlarında tek UTC stratejisi belirle; kolon, Python değeri ve JSON gösterimini timezone uyumlu yap.
- [ ] Legacy `Patient` modelinin ne zaman kaldırılacağını migration ve rollback planıyla belirle.

### Ölü ve tekrarlanan kodu azalt

- [ ] Kullanılmayan `auto_rate_error` context/template yolunu kaldır veya gerçek hata durumuna bağla.
- [ ] Artık production akışında çağrılmayan `ensure_daily_rate()` background-thread yolunu ve testlerini kaldır.
- [ ] `InvoiceService` dosyasını `app/models/` yerine `app/services/` altına taşı.
- [ ] `Config.SMTP_*` ile veritabanındaki SMTP ayarlarından hangisinin tek kaynak olduğunu belirle; kullanılmayan config yolunu kaldır.
- [ ] Tedavi kategori etiketlerini tek sabitte topla; kullanılmayan importları temizle.
- [ ] `clinic_name` ve kur sağlık context sorgularını ölç; gerekirse request-scope veya kısa TTL cache kullan.

### Dosya içe aktarma sözleşmesini düzelt

- [ ] OpenPyXL kullanılan akışta yalnız `.xlsx` kabul et veya gerçek `.xls` parser'ı ekle; bugün uzantı kontrolü `.xls` kabul ettiği hâlde okuyucu bu biçimi desteklemez.
- [ ] Satır bazlı hata raporu üret; geçersiz satırları yalnız sayaçla sessizce atlama.
- [ ] Workbook kapanışını hata durumunda da garanti et ve import işlemini açık transaction sınırında çalıştır.

### Liste ve rapor ölçek sınırlarını tamamla

- [ ] `/patients/` listesini diğer listeler gibi server-side pagination'a geçir.
- [ ] Büyük veri setinde rapor sorgularını ve eager-load davranışını ölç; hedef veri hacmi ve kabul edilen p95 süreyi yaz.
- [ ] SQLite eşzamanlı yazma eşiğini gerçek yük testiyle belirle; eşik aşılırsa PostgreSQL geçiş runbook'unu uygula.

## P2 — Test ve CI kalitesi

- [ ] Coverage-boost dosyalarındaki mükerrer senaryoları davranış matrisi çıkararak birleştir; coverage yüzdesini korumak tek amaç olmasın.
- [ ] Yalnız `302` kontrol eden testlerde hedef `Location`, flash mesajı ve kalıcı veri etkisini doğrula.
- [ ] Authz endpoint matrisi ekle: anonymous, staff ve admin için view/edit/delete/settings/privacy sınırları.
- [ ] Login DoS, multi-worker WhatsApp durumu, SMTP timeout/hata redaksiyonu ve salt-okuma audit kararını regresyon testlerine bağla.
- [ ] Türkçe metinleri PDF, SMTP subject/body, XLSX import ve arama/case-folding düzeyinde uçtan uca test et.
- [ ] CI'a lint/format kontrolü ve dependency vulnerability taraması ekle; job timeout ile concurrency cancellation tanımla.
- [ ] Yavaş testleri `pytest --durations` ile ölç; hızlı unit paketi ile tam entegrasyon/E2E paketini ayır.

## P3 — Ürün ve operasyon ölçeği

- [ ] Randevu, çoklu şube, stok ve haricî API taleplerini doğrulanmış klinik ihtiyacına göre ayrı ürün kararlarına dönüştür.
- [ ] PostgreSQL geçişinde enum, SQLite batch migration, invoice counter ve backup araçlarının uyumluluk planını hazırla.
- [ ] Merkezi log/metric/alert hedeflerini tanımla: 5xx oranı, SMTP/WhatsApp başarısızlığı, eski kur, backup yaşı, job kuyruğu ve DB kilit süresi.
- [ ] Audit logu için uygulama dışı değişmezlik/erişim kontrolü ve periyodik bütünlük doğrulaması değerlendir.

## Tamamlanmış temel yetenekler

- [x] App factory, blueprint yapısı, SQLAlchemy 2 ve Alembic migration zinciri.
- [x] `Party` operasyonel tek kaynak; legacy `Patient` kontrollü uyumluluk katmanı.
- [x] `Numeric`/`Decimal` finans kolonları, sabit fatura kuru, ödeme ve fazla tahsilat koruması.
- [x] Merkezi admin/staff izin matrisi; staff için kişi/fatura/ödeme silme, ayar ve KVKK yetkileri kapalı.
- [x] CSRF, bcrypt, Fernet SMTP şifreleme ve production secret fail-closed kontrolü.
- [x] Transactional değişiklik audit'i, KVKK export/anonimleştirme ve saklama CLI komutu.
- [x] Self-hosted frontend varlıkları, güvenlik başlıkları, request ID ve opsiyonel Sentry.
- [x] Doğrulamalı/şifreli SQLite backup, anahtar rotasyonu ve atomik restore.
- [x] Python 3.13/3.14 CI, %90 branch-aware coverage kapısı ve gerçek Chromium E2E/axe taraması.

## İncelemelerde görülen ancak hata olmayan iddialar

- `json.loads()` için ayrı `JSONDecodeError` bloğu zorunlu değildir; `JSONDecodeError`, mevcut `ValueError` bloğu tarafından yakalanır.
- Staff'ın `settings.manage` ve `privacy.*` alamaması mevcut least-privilege politikasının bilinçli parçasıdır.
- `billing.delete` staff'a verilmez; fatura ve ödeme silme admin-only'dir.
- Modern `fpdf2` SVG destekler; marka SVG'si PDF içinde kullanılmaktadır.
- `Migrate(compare_type=True)` mevcut Flask-Migrate/Alembic yapılandırmasında geçerli bir parametredir.
