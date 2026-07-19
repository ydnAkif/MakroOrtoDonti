# 🦷 MAKRO ORTODONTİ - Proje Planı

> **Ortodonti Uygulaması** | Müşteri Kayıtları, Fatura Yönetimi, WhatsApp/E-posta Entegrasyonu

---

## 📌 Proje Özeti

Mevcut Excel tabanlı müşteri kayıtlarını ve siparişlerini modern bir web uygulamasına taşıma. Temel özellikler:

- 📋 **Hasta Yönetimi** - Yeni kayıt, düzenleme, silme, arama
- 💰 **Fatura Oluşturma** - EUR bazlı tedavi ücretleri, otomatik günlük kur çevirme
- 📄 **PDF Fatura** - Profesyonel fatura oluşturma ve indirme
- 📱 **WhatsApp Gönderimi** - Neonize ile ücretsiz fatura/hatırlatma gönderimi
- 📧 **E-posta Gönderimi** - PDF'li fatura e-postası
- 📊 **Raporlar** - Aylık gelir, borç dökümü, istatistikler
- 🔧 **Klinik Ayarları** - Dinamik admin panelinden yönetim

---

## 🏗️ Tech Stack

| Bileşen        | Seçim                     | Neden                                          |
| -------------- | ------------------------- | ---------------------------------------------- |
| **Backend**    | Python 3.10+ / Flask      | Basit, olgun, yeterli performans               |
| **Frontend**   | Jinja2 + Bootstrap 5      | Sunucu taraflı, hızlı geliştirme               |
| **Veritabanı** | SQLite + SQLAlchemy       | Sıfır kurulum, tek dosya, 300 hasta için ideal |
| **PDF**        | fpdf2                     | Hafif, Türkçe karakter desteği                 |
| **WhatsApp**   | Neonize (ücretsiz)        | Python native, QR/pair code auth               |
| **E-posta**    | smtplib (Python built-in) | Ücretsiz, SMTP üzerinden                       |
| **Döviz Kuru** | Frankfurter API           | Ücretsiz, auth yok, ECB verisi                 |
| **Auth**       | Flask-Login               | Oturum yönetimi                                |
| **Şifreleme**  | bcrypt                    | Güvenli şifre hashleme                         |
| **Form**       | Flask-WTF                 | CSRF korumalı formlar                          |

### Maliyet: **0 TL/ay** (Tamamen ücretsiz)

---

## 📁 Proje Yapısı

```
makroortodonti/
├── app/
│   ├── __init__.py              # Flask app factory
│   ├── config.py                # Yapılandırma
│   ├── extensions.py            # Flask extension'lar
│   │
│   ├── models/
│   │   ├── __init__.py
│   │   ├── base.py              # Base, TimestampMixin, SoftDeleteMixin
│   │   ├── patient.py           # Hasta modeli
│   │   ├── treatment.py         # Tedavi kataloğu
│   │   ├── invoice.py           # Fatura + kalem
│   │   ├── exchange_rate.py     # Döviz kurları
│   │   ├── user.py              # Kullanıcılar
│   │   └── settings.py          # Klinik ayarları
│   │
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py              # Giriş/çıkış
│   │   ├── dashboard.py         # Ana sayfa
│   │   ├── patients.py          # Hasta CRUD
│   │   ├── treatments.py        # Tedavi kataloğu
│   │   ├── invoices.py          # Fatura yönetimi
│   │   ├── whatsapp.py          # WhatsApp gönderimi
│   │   ├── email.py             # E-posta gönderimi
│   │   ├── reports.py           # Raporlar
│   │   └── settings.py          # Klinik ayarları
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── pdf_service.py       # PDF oluşturma
│   │   ├── whatsapp_service.py  # Neonize entegrasyonu
│   │   ├── email_service.py     # SMTP entegrasyonu
│   │   ├── exchange_service.py  # Döviz kuru servisi
│   │   └── invoice_service.py   # Fatura numarası + EUR→TRY
│   │
│   ├── templates/
│   │   ├── base.html            # Ana şablon (navbar + sidebar)
│   │   ├── auth/
│   │   │   └── login.html
│   │   ├── dashboard/
│   │   │   └── index.html
│   │   ├── patients/
│   │   │   ├── list.html
│   │   │   ├── form.html
│   │   │   └── detail.html
│   │   ├── treatments/
│   │   │   ├── list.html
│   │   │   └── form.html
│   │   ├── invoices/
│   │   │   ├── list.html
│   │   │   ├── form.html
│   │   │   ├── detail.html
│   │   │   └── send.html
│   │   ├── reports/
│   │   │   └── index.html
│   │   ├── settings/
│   │   │   └── index.html
│   │   └── components/
│   │       ├── navbar.html
│   │       ├── sidebar.html
│   │       ├── pagination.html
│   │       └── confirm_modal.html
│   │
│   └── static/
│       ├── css/
│       │   └── style.css
│       ├── js/
│       │   └── app.js
│       ├── images/
│       │   └── logo.png
│       └── fonts/
│           └── DejaVuSans.ttf    # Türkçe karakter için
│
├── data/
│   └── makroorto.db              # SQLite veritabanı (otomatik oluşur)
│
├── requirements.txt
├── .env.example
├── .gitignore
├── run.py                        # Uygulama başlatıcı
├── init_db.py                    # Veritabanı initializasyonu
└── README.md
```

---

## 🗃️ Veritabanı Şeması

### Tablolar Arası İlişkiler

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│     patients     │────▶│patient_treatments │◀────│    treatments    │
│─────────────────│     │──────────────────│     │─────────────────│
│ id (PK)         │     │ id (PK)          │     │ id (PK)         │
│ first_name      │     │ patient_id (FK)  │     │ name            │
│ last_name       │     │ treatment_id(FK) │     │ description     │
│ phone           │     │ date             │     │ category        │
│ email           │     │ notes            │     │ price_eur       │
│ address         │     │ price_override   │     │ is_active       │
│ city            │     └──────────────────┘     └─────────────────┘
│ notes           │
│ is_active       │     ┌──────────────────┐     ┌─────────────────┐
│ created_at      │────▶│     invoices      │────▶│  invoice_items   │
│ updated_at      │     │──────────────────│     │─────────────────│
└─────────────────┘     │ id (PK)          │     │ id (PK)         │
                        │ patient_id (FK)  │     │ invoice_id (FK) │
                        │ invoice_number   │     │ treatment_id(FK)│
                        │ invoice_date     │     │ description     │
                        │ due_date         │     │ quantity        │
                        │ total_eur        │     │ unit_price_eur  │
                        │ total_try        │     │ unit_price_try  │
                        │ exchange_rate    │     │ total_eur       │
                        │ status           │     │ total_try       │
                        │ notes            │     └─────────────────┘
                        │ is_deleted       │
                        │ created_at       │     ┌─────────────────┐
                        │ updated_at       │     │ exchange_rates   │
                        └──────────────────┘     │─────────────────│
                                                 │ id (PK)         │
┌─────────────────┐     ┌──────────────────┐     │ rate_date       │
│     users       │     │    settings      │     │ eur_try_rate    │
│─────────────────│     │──────────────────│     │ source          │
│ id (PK)         │     │ id (PK)          │     │ created_at      │
│ username        │     │ key (UNIQUE)     │     └─────────────────┘
│ password_hash   │     │ value            │
│ full_name       │     │ updated_at       │     ┌──────────────────┐
│ role            │     └──────────────────┘     │whatsapp_sessions  │
│ is_active       │                              │──────────────────│
│ created_at      │                              │ id (PK)          │
└─────────────────┘                              │ phone_number     │
                                                 │ session_data     │
                                                 │ is_connected     │
                                                 │ last_active      │
                                                 │ created_at       │
                                                 └──────────────────┘
```

### Tablo Detayları

#### 1. patients (Hastalar)

```sql
CREATE TABLE patients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL,          -- WhatsApp numarası
    email VARCHAR(120),
    address TEXT,
    city VARCHAR(100),
    notes TEXT,
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_patients_name ON patients(last_name, first_name);
CREATE INDEX idx_patients_phone ON patients(phone);
CREATE INDEX idx_patients_active ON patients(is_active);
```

#### 2. treatments (Tedavi Kataloğu)

```sql
CREATE TABLE treatments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    category VARCHAR(50) NOT NULL,       -- ortodonti, protetik, cerrahi vb.
    price_eur DECIMAL(10,2) NOT NULL,    -- EUR bazlı fiyat
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_treatments_category ON treatments(category, is_active);
```

#### 3. patient_treatments (Hasta Tedavileri)

```sql
CREATE TABLE patient_treatments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    treatment_id INTEGER NOT NULL,
    treatment_date DATE NOT NULL,
    notes TEXT,
    price_override_eur DECIMAL(10,2),    -- Hasta özel fiyat (null ise katalog fiyatı)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id),
    FOREIGN KEY (treatment_id) REFERENCES treatments(id)
);

CREATE INDEX idx_patient_treatments_patient ON patient_treatments(patient_id);
CREATE INDEX idx_patient_treatments_date ON patient_treatments(treatment_date);
```

#### 4. invoices (Faturalar)

```sql
CREATE TABLE invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    invoice_number VARCHAR(30) UNIQUE NOT NULL,  -- MKR-2026-0001
    invoice_date DATE NOT NULL,
    due_date DATE,
    total_eur DECIMAL(12,2) NOT NULL,
    total_try DECIMAL(12,2) NOT NULL,
    exchange_rate DECIMAL(10,4) NOT NULL,        -- Oluşturulma anındaki kur
    status VARCHAR(20) DEFAULT 'pending',        -- pending/paid/overdue/cancelled
    notes TEXT,
    is_deleted BOOLEAN DEFAULT 0,                -- Soft delete
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patients(id)
);

CREATE INDEX idx_invoices_patient ON invoices(patient_id, invoice_date);
CREATE INDEX idx_invoices_status ON invoices(status, invoice_date);
CREATE INDEX idx_invoices_number ON invoices(invoice_number);
```

#### 5. invoice_items (Fatura Kalemleri)

```sql
CREATE TABLE invoice_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL,
    treatment_id INTEGER,
    description VARCHAR(200) NOT NULL,
    quantity INTEGER DEFAULT 1,
    unit_price_eur DECIMAL(10,2) NOT NULL,
    unit_price_try DECIMAL(10,2) NOT NULL,
    total_eur DECIMAL(12,2) NOT NULL,
    total_try DECIMAL(12,2) NOT NULL,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id),
    FOREIGN KEY (treatment_id) REFERENCES treatments(id)
);

CREATE INDEX idx_invoice_items_invoice ON invoice_items(invoice_id);
```

#### 6. exchange_rates (Döviz Kurları)

```sql
CREATE TABLE exchange_rates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rate_date DATE NOT NULL,
    eur_try_rate DECIMAL(10,4) NOT NULL,
    source VARCHAR(50) DEFAULT 'ECB',           -- ECB/Frankfurter
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(rate_date, source)
);

CREATE INDEX idx_exchange_rates_date ON exchange_rates(rate_date DESC);
```

#### 7. settings (Klinik Ayarları)

```sql
CREATE TABLE settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    key VARCHAR(100) UNIQUE NOT NULL,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- Örnek ayarlar:
-- clinic_name: "Makro Ortodonti"
-- clinic_address: "İstanbul, Türkiye"
-- clinic_phone: "+90 212 XXX XX XX"
-- clinic_email: "info@makroorto.com"
-- clinic_logo: "logo.png"
-- invoice_prefix: "MKR"
-- invoice_counter: "1"
-- smtp_server: "smtp.gmail.com"
-- smtp_port: "587"
-- smtp_username: ""
-- smtp_password: ""
```

#### 8. users (Kullanıcılar)

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    full_name VARCHAR(150),
    role VARCHAR(20) DEFAULT 'staff',           -- admin/staff
    is_active BOOLEAN DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 9. whatsapp_sessions (WhatsApp Oturumları)

```sql
CREATE TABLE whatsapp_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    phone_number VARCHAR(20) NOT NULL,
    session_data TEXT,                          -- Neonize session JSON
    is_connected BOOLEAN DEFAULT 0,
    last_active DATETIME,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

---

## 🎯 Modüller ve Özellikler

### 1. 🔐 Kimlik Doğrulama (Auth)

- Kullanıcı girişi/çıkışı
- Şifre bcrypt ile hash'lenir
- Oturum yönetimi (Flask-Login)
- Yetkilendirme (admin/staff)

### 2. 📊 Dashboard (Ana Sayfa)

- Bugünkü fatura özeti
- Son eklenen hastalar
- Toplam hasta/borc sayısı
- Hızlı fatura oluşturma butonu
- Son faturalar listesi
- EUR/TRY güncel kur

### 3. 👤 Hasta Yönetimi (CRUD)

- **Ekleme:** Ad, soyad, telefon (WhatsApp), e-posta, adres, notlar
- **Listeleme:** Arama, filtreleme, sayfalama
- **Detay:** Hasta bilgileri + tedavi geçmişi + faturalar
- **Düzenleme:** Tüm bilgileri güncelleme
- **Silme:** Soft delete (is_active = false)

### 4. 💊 Tedavi Kataloğu

- **Ekleme:** Tedavi adı, açıklama, kategori, EUR fiyatı
- **Kategoriler:** Ortodonti, Protetik, Cerrahi, Koruyucu, Restoratif, Perio/Endo, İmplant, Kozmetik, Diğer
- **Fiyatlandırma:** EUR bazlı, günlük kur ile TRY karşılığı gösterilir
- **59 hazır tedavi** (14 ortodontik dahil)

### 5. 🧾 Fatura Yönetimi

- **Oluşturma:** Hasta seçimi + tedavi kalemleri ekleme
- **EUR→TRY Çevirme:** Oluşturulma anındaki kur sabitlenir
- **Otomatik numara:** MKR-2026-0001 formatında
- **Durum takibi:** Bekliyor / Ödendi / Gecikmiş / İptal
- **PDF oluşturma:** Profesyonel fatura PDF'i
- **Düzenleme:** Fatura kalemlerini ekleme/çıkarma

### 6. 📱 WhatsApp Entegrasyonu (Neonize)

- **Oturum açma:** QR code tarama veya pair code
- **Tekli gönderim:** Tek bir hastaya fatura/hatırlatma
- **Toplu gönderim:** Tüm hastalara fatura bildirimi
- **Mesaj şablonları:**

  ```
  Sayın {hasta_adı},

  {tarih} tarihli faturanız hazırlanmıştır.

  Toplam Tutar: {tutar} TRY
  Son Ödeme: {son_odeme}

  Faturanız ekte gönderilmiştir.

  Saygılarımızla,
  {klinik_adı}
  ```

- **Durum takibi:** Gönderildi / Teslim edildi / Okundu

### 7. 📧 E-posta Entegrasyonu

- **SMTP ayarları:** Gmail, Outlook, özel SMTP
- **PDF'li fatura:** E-posta ile PDF eki olarak gönderim
- **Hatırlatma e-postası:** Geciken faturalar için otomatik

### 8. 📈 Raporlar

- **Aylık gelir raporu:** EUR ve TRY cinsinden
- **Hasta bazlı borç dökümü**
- **Tedavi istatistikleri:** En çok yapılan tedaviler
- **Fatura durumu raporu**

### 9. ⚙️ Klinik Ayarları

- Klinik bilgileri (ad, adres, telefon, logo)
- Fatura ayarları (ön ek, sıfır sayısı)
- E-posta yapılandırması (SMTP)
- WhatsApp durumu
- Yedekleme

---

## 📊 Tedavi Kataloğu

### Ortodonti (14 tedavi)

| Tedavi                    | EUR   |
| ------------------------- | ----- |
| Metal Braces (Full Set)   | 2.500 |
| Ceramic Braces (Full Set) | 3.500 |
| Invisalign Full           | 4.000 |
| Invisalign Lite           | 2.800 |
| Lingual Braces            | 4.500 |
| Retainer (Per Set)        | 300   |
| Palatal Expander          | 800   |
| Herbst Appliance          | 1.200 |
| Face Mask (Facial)        | 600   |
| Chin Cup                  | 400   |
| Space Maintainer          | 200   |
| Habit Breaking Appliance  | 300   |
| Orthodontic Consultation  | 50    |
| Panoramic X-Ray           | 80    |

### Protetik (10 tedavi)

| Tedavi                      | EUR   |
| --------------------------- | ----- |
| Zirconia Crown              | 550   |
| Porcelain Crown             | 450   |
| Metal Crown                 | 300   |
| Porcelain Veneer            | 400   |
| Composite Veneer            | 250   |
| Maryland Bridge             | 600   |
| Traditional Bridge (3-unit) | 1.200 |
| Partial Denture             | 800   |
| Complete Denture            | 1.500 |
| Implant-Supported Denture   | 1.800 |

### Cerrahi (7 tedavi)

| Tedavi                  | EUR   |
| ----------------------- | ----- |
| Simple Extraction       | 150   |
| Surgical Extraction     | 300   |
| Wisdom Tooth Extraction | 400   |
| Bone Grafting           | 600   |
| Sinus Lift              | 1.200 |
| Frenectomy              | 200   |
| Cyst Removal            | 500   |

### Koruyucu (5 tedavi)

| Tedavi                     | EUR |
| -------------------------- | --- |
| Professional Cleaning      | 80  |
| Fluoride Treatment         | 40  |
| Dental Sealant (Per Tooth) | 50  |
| Night Guard                | 200 |
| Sports Guard               | 150 |

### Restoratif (5 tedavi)

| Tedavi                     | EUR |
| -------------------------- | --- |
| Composite Filling (Small)  | 70  |
| Composite Filling (Medium) | 120 |
| Composite Filling (Large)  | 200 |
| Amalgam Filling            | 100 |
| Inlay/Onlay                | 400 |

### Perio/Endo (5 tedavi)

| Tedavi                 | EUR |
| ---------------------- | --- |
| Root Canal (Anterior)  | 300 |
| Root Canal (Premolar)  | 400 |
| Root Canal (Molar)     | 600 |
| Scaling & Root Planing | 250 |
| Gum Grafting           | 500 |

### İmplant (5 tedavi)

| Tedavi                    | EUR    |
| ------------------------- | ------ |
| Dental Implant (Titanium) | 1.200  |
| Dental Implant (Premium)  | 1.800  |
| All-on-4 (Per Jaw)        | 8.000  |
| All-on-6 (Per Jaw)        | 10.000 |
| Implant Abutment          | 300    |

### Kozmetik (3 tedavi)

| Tedavi                      | EUR |
| --------------------------- | --- |
| Teeth Whitening (In-Office) | 400 |
| Teeth Whitening (Take-Home) | 200 |
| Gum Contouring              | 300 |

### Diğer (5 tedavi)

| Tedavi          | EUR |
| --------------- | --- |
| Consultation    | 50  |
| Emergency Visit | 100 |
| Temporary Crown | 80  |
| Mouthguard      | 150 |
| Digital X-Ray   | 60  |

---

## 🔧 Kurulum ve Çalıştırma

### Ön Koşullar

- Python 3.10 veya üzeri
- pip (Python paket yöneticisi)
- Git

### Kurulum Adımları

```bash
# 1. Depoyu klonla
git clone <repo_url>
cd makroortodonti

# 2. Sanal ortam oluştur ve aktifleştir
python -m venv venv
source venv/bin/activate        # Linux/Mac
# venv\Scripts\activate         # Windows

# 3. Bağımlılıkları kur
pip install -r requirements.txt

# 4. Ortam değişkenlerini yapılandır
cp .env.example .env
# .env dosyasını düzenle:
# - SECRET_KEY: Rastgele bir güvenli anahtar
# - DATABASE_URL: sqlite:///data/makroorto.db
# - SMTP ayarları (isteğe bağlı)

# 5. Neonize kurulumu (WhatsApp için)
pip install neonize

# 6. Veritabanını oluştur ve ilk verileri ekle
python init_db.py

# 7. Uygulamayı başlat
python run.py
```

### Kullanım

- Tarayıcıda aç: `http://localhost:5000`
- Varsayılan giriş: `admin` / `admin123` (ilk girişte değiştirilmeli)

---

## 🛡️ Güvenlik

| Özellik          | Uygulama                       |
| ---------------- | ------------------------------ |
| Şifre saklama    | bcrypt hash                    |
| Oturum yönetimi  | Flask-Login, secure cookie     |
| CSRF koruması    | Flask-WTF token                |
| SQL enjeksiyon   | SQLAlchemy ORM (parameterized) |
| XSS              | Jinja2 autoescape              |
| WhatsApp oturumu | Şifreli session saklama        |
| Hassas veriler   | .env dosyasında                |
| HTTPS            | Production için önerilir       |

---

## 📈 Gelecek Genişletmeler

Mevcut modüler yapı ile kolayca eklenebilir:

- **API endpoint'leri** - Mobil uygulama entegrasyonu
- **Çoklu dil** - i18n yapısı ile İngilizce/Almanca desteği
- **Yedekleme** - Otomatik SQLite yedekleme
- **Rol bazlı erişim** - RBAC ile detaylı yetkilendirme
- **Barkod/QR** - Fatura barkodları
- **Randevu sistemi** - Takvim entegrasyonu
- **Stok yönetimi** - Malzeme takibi
- **Çoklu şube** - Farklı lokasyon desteği

---

## 📋 Geliştirme Aşamaları

### Aşama 1: Temel Yapı (1-2 gün)

- [ ] Proje yapısı oluşturma
- [ ] Flask app factory
- [ ] Veritabanı modelleri
- [ ] Kimlik doğrulama (login/logout)
- [ ] Dashboard

### Aşama 2: Hasta Yönetimi (1 gün)

- [ ] Hasta CRUD (ekleme, listeleme, düzenleme, silme)
- [ ] Arama ve filtreleme
- [ ] Hasta detay sayfası

### Aşama 3: Tedavi Kataloğu (0.5 gün)

- [ ] Tedavi CRUD
- [ ] Kategori bazlı listeleme
- [ ] 59 hazır tedavi verisi

### Aşama 4: Fatura Yönetimi (2 gün)

- [ ] Fatura oluşturma formu
- [ ] EUR→TRY otomatik çeviri
- [ ] Fatura numarası üretimi
- [ ] Fatura listeleme ve detay
- [ ] PDF oluşturma

### Aşama 5: İletişim Entegrasyonu (1-2 gün)

- [ ] WhatsApp oturum yönetimi (Neonize)
- [ ] WhatsApp mesaj gönderimi
- [ ] E-posta gönderimi (SMTP)
- [ ] Mesaj şablonları

### Aşama 6: Raporlar ve Ayarlar (1 gün)

- [ ] Dashboard istatistikleri
- [ ] Aylık gelir raporu
- [ ] Klinik ayarları sayfası

---

## 📞 İletişim

**Proje:** Makro Ortodonti
**Geliştirici:** opencode
**Başlangıç:** 2026

---

_Bu belge planlama aşamasındadır. Değişiklikler uygulama geliştirme sırasında yapılabilir._
