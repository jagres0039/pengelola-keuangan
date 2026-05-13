# Pengelola Keuangan — Telegram Bot

Bot Telegram untuk catat pemasukan & pengeluaran bulanan. Multi-user (data tiap orang terisolasi), bahasa Indonesia, dilengkapi budget, chart, recurring transactions, reminder harian, dan import/export Excel.

## Fitur

- **Catat transaksi**: `/in <jumlah> [kategori] [catatan]` & `/out <jumlah> [kategori] [catatan]`
- **Ringkasan bulanan**: `/summary` atau `/summary 2026-04`
- **Riwayat & edit**: `/history`, `/edit <id> <field> <value>`, `/delete <id>`
- **Kategori per user**: `/categories` (default kategori di-seed otomatis pas `/start`)
- **Budget per kategori + auto alert**: `/budget set Makanan 1500000`
- **Chart visual**: `/chart` (pie kategori), `/chart trend` (line 6 bulan)
- **Recurring transactions**: `/recurring_add` (wizard step-by-step)
- **Reminder harian**: `/reminder on 20`
- **Export Excel/CSV**: `/export xlsx` / `/export csv`
- **Import Excel**: kirim file `.xlsx` ke chat → bot tampilkan preview perubahan → konfirmasi
- **Baca struk pembayaran (OCR)**: kirim foto struk → bot extract merchant, tanggal, total, kategori pakai Gemini Vision → konfirmasi sebelum simpan. Free tier (`GEMINI_API_KEY` dari [aistudio.google.com/apikey](https://aistudio.google.com/apikey)).
- **Parsing fleksibel**: `35rb`, `1.5jt`, `5,000.50`, `5.000`, semua diterima
- **Multi-currency & multi-timezone**: `/currency USD`, `/timezone Asia/Makassar`
- **Allow-list mode (opsional)**: batasi akses dengan `ALLOWED_USER_IDS` di env

## Tech stack

- Python 3.12 + `python-telegram-bot` 22
- PostgreSQL (production) / SQLite (local dev) via SQLAlchemy 2.0 + Alembic migrations
- `matplotlib` untuk chart, `openpyxl` untuk export/import Excel
- `APScheduler` (via PTB job queue) untuk reminder & recurring

## Setup local (tanpa Docker)

Butuh: Python 3.12 dan [uv](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone https://github.com/jagres0039/pengelola-keuangan.git
cd pengelola-keuangan

# Install dependencies
uv sync

# Copy env template
cp .env.example .env
# Edit .env: isi TELEGRAM_BOT_TOKEN dari @BotFather
# Default DATABASE_URL pake SQLite, gak perlu Postgres untuk dev

# Run migrations
uv run alembic upgrade head

# Run bot
uv run python -m pengelola_keuangan
```

## Setup di VPS (Docker + docker-compose)

Butuh: Docker & Docker Compose plugin.

```bash
# 1. Clone repo
git clone https://github.com/jagres0039/pengelola-keuangan.git
cd pengelola-keuangan

# 2. Set environment
cp .env.example .env
# Edit .env:
#   - TELEGRAM_BOT_TOKEN: token dari @BotFather
#   - POSTGRES_PASSWORD: password yang aman
#   - ALLOWED_USER_IDS: (opsional) batasi siapa yang boleh akses
#   - GEMINI_API_KEY: (opsional) aktifin fitur OCR struk
# DATABASE_URL otomatis di-set ke postgres lewat docker-compose

# 3. Build & jalankan
docker compose up -d --build

# 4. Cek log
docker compose logs -f bot
```

Bot otomatis jalan migration Alembic pas start, jadi schema langsung siap.

### Update di VPS

```bash
git pull
docker compose up -d --build
```

### Backup data

Postgres data tersimpan di volume `postgres_data`. Backup dengan:

```bash
docker compose exec db pg_dump -U bot pengelola_keuangan > backup-$(date +%F).sql
```

## Setup bot di Telegram

1. Chat dengan [@BotFather](https://t.me/BotFather)
2. `/newbot` → ikutin instruksi → copy token yang dikasih
3. Paste token ke `.env` di field `TELEGRAM_BOT_TOKEN`
4. (Opsional) `/setdescription`, `/setabouttext`, `/setuserpic` buat profile bot

Setelah bot jalan, chat botnya, ketik `/start`, dan langsung bisa pake.

## Daftar perintah lengkap

| Perintah | Fungsi |
|---|---|
| `/start` | Registrasi & seed kategori default |
| `/help` | Daftar semua perintah |
| `/in <jumlah> [kategori] [catatan]` | Catat pemasukan |
| `/out <jumlah> [kategori] [catatan]` | Catat pengeluaran |
| `/summary [YYYY-MM]` | Ringkasan bulan |
| `/history [n]` | Riwayat n transaksi terakhir (default 10) |
| `/edit <id> <field> <value>` | Edit field: `amount`, `note`, `category` |
| `/delete <id>` | Hapus transaksi |
| `/categories` | Lihat semua kategori |
| `/categories add in\|out <nama>` | Tambah kategori |
| `/categories rename <id> <nama>` | Rename kategori |
| `/categories del <id>` | Hapus kategori |
| `/budget` | Status budget bulan ini |
| `/budget set <kategori> <jumlah>` | Set budget |
| `/budget del <kategori>` | Hapus budget |
| `/chart` | Pie chart kategori |
| `/chart trend` | Line chart 6 bulan |
| `/recurring` | Daftar recurring |
| `/recurring_add` | Wizard tambah recurring |
| `/recurring del <id>` | Hapus recurring |
| `/reminder on [jam]` | Reminder harian (default 20:00) |
| `/reminder off` | Matikan reminder |
| `/export csv\|xlsx [YYYY-MM]` | Export bulan tertentu |
| `/timezone <IANA>` | Set zona waktu |
| `/currency <CODE>` | Set mata uang |

## Workflow import Excel

1. Ketik `/export xlsx` di chat → bot kirim file `.xlsx`
2. Buka file di Excel/Sheets → edit row apa aja (ubah `jumlah`, `kategori`, `catatan`, atau hapus baris)
3. Kirim file `.xlsx` tersebut kembali ke chat bot
4. Bot kasih preview: berapa baris baru, diubah, dihapus → klik **Apply** atau **Batal**

> Kolom `id` di file Excel dipake bot buat detect mana yang baru vs ada. Jangan hapus kolom `id` kalau gak mau bot bingung.

## Development

```bash
# Lint + format
uv run ruff check .
uv run ruff format .

# Type check
uv run mypy src

# Tests
uv run pytest

# Buat migration baru setelah ubah models
uv run alembic revision --autogenerate -m "describe change"
uv run alembic upgrade head
```

## Struktur kode

```
src/pengelola_keuangan/
├── bot/                     # Telegram glue
│   ├── app.py               # build_application & run()
│   ├── handlers.py          # semua /command handler
│   ├── recurring_wizard.py  # ConversationHandler /recurring_add
│   ├── scheduler.py         # daily reminder & recurring job
│   └── messages.py          # text templates bahasa Indonesia
├── db/
│   ├── models.py            # SQLAlchemy ORM: User, Category, Transaction, Budget, Recurring
│   ├── session.py           # engine + session_scope context manager
│   └── defaults.py          # default kategori awal
├── services/                # business logic, tidak depend ke Telegram
│   ├── parsing.py           # parse_amount, guess_category_name
│   ├── formatting.py        # money/month/percent
│   ├── time_helpers.py      # timezone helpers
│   ├── users.py             # ensure_user, allow-list
│   ├── categories.py        # CRUD kategori
│   ├── transactions.py      # CRUD + summarize_month + trend
│   ├── budgets.py           # set + status
│   ├── recurring.py         # list + run_due_recurring (dipanggil scheduler)
│   ├── exporting.py         # CSV + XLSX
│   ├── importing.py         # parse XLSX + build_import_plan + apply
│   └── charts.py            # matplotlib PNG
├── config.py                # Pydantic Settings dari .env
├── __main__.py              # entry point `python -m pengelola_keuangan`
alembic/                     # migrations
tests/                       # pytest
```

## Lisensi

MIT.
