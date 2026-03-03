# 🤖 Google Drive RAG Chatbot

Chatbot cerdas yang memungkinkan Anda berinteraksi dengan dokumen di Google Drive menggunakan teknologi RAG (Retrieval-Augmented Generation) dan Google Gemini.

## ✨ Fitur Utama
- **Multi-Format Support:** Mendukung PDF, Google Docs, Word, Excel, CSV, JSON, Markdown, dan Google Slides.
- **Smart Search:** Menggunakan ekstraksi kata kunci cerdas (Gemini) untuk menemukan dokumen relevan di Google Drive.
- **Table Understanding:** Mampu membaca dan memahami data tabel (Excel/CSV) dengan detail.
- **Auto-Summarization:** Fitur ringkasan otomatis untuk dokumen yang diindeks.
- **Secure:** File rahasia (credentials) tidak disimpan di cloud, semua pemrosesan dilakukan secara lokal.

## 🛠️ Prasyarat
- Python 3.9 atau lebih baru.
- Akun Google Cloud Platform (GCP) dengan Google Drive API aktif.
- API Key Google Gemini (AI Studio).

## 🚀 Cara Instalasi

### 1. Clone Repository
```bash
git clone https://github.com/hiiamanop/RAG-project.git
cd RAG-project
```

### 2. Setup Virtual Environment
Disarankan menggunakan virtual environment agar dependencies tidak bentrok.
```bash
python -m venv venv
source venv/bin/activate  # Mac/Linux
# venv\Scripts\activate   # Windows
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Konfigurasi API Key
Buat file `.env` di root folder proyek dan tambahkan API Key Gemini Anda:
```env
GOOGLE_API_KEY=masukkan_api_key_anda_disini
```

### 5. Setup Google Drive Credentials
1. Buka [Google Cloud Console](https://console.cloud.google.com/).
2. Buat proyek baru dan aktifkan **Google Drive API**.
3. Pergi ke **APIs & Services > Credentials**.
4. Buat **OAuth Client ID** (pilih tipe Desktop App).
5. Download file JSON credentials, ubah namanya menjadi `credentials.json`, dan simpan di folder root proyek ini.
6. (Opsional) Tambahkan user email Anda sebagai "Test User" di menu **OAuth consent screen**.

### 6. Jalankan Aplikasi
```bash
streamlit run app.py
```
Aplikasi akan terbuka otomatis di browser (biasanya di `http://localhost:8501`).

## 💡 Cara Menggunakan
1. Klik tombol **Connect to Google Drive** di sidebar.
2. Login dengan akun Google Anda dan berikan izin akses.
3. Ketik pertanyaan Anda di kolom chat (contoh: "Carikan laporan keuangan bulan lalu").
4. Bot akan mencari dokumen yang relevan, mendownloadnya, dan menjawab pertanyaan Anda berdasarkan isi dokumen tersebut.

## 📝 Catatan
- File yang didownload akan disimpan sementara di folder `downloads/` dan otomatis diabaikan oleh Git.
- Token akses Google Drive akan disimpan di `token.pickle` untuk login otomatis berikutnya.
