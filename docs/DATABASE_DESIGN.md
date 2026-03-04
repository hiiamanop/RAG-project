# Desain Sistem Database Chat History (NoSQL)

Dokumen ini menjelaskan rancangan sistem database untuk menyimpan history chat menggunakan MongoDB, termasuk alasan pemilihan teknologi, skema, dan API.

## 1. Pemilihan Teknologi: NoSQL (MongoDB) vs SQL

Kami memilih **MongoDB (NoSQL)** dibandingkan SQL (PostgreSQL/MySQL) untuk kasus penggunaan chat history dengan pertimbangan:

### a. Skalabilitas & Performa (Scalability)
- **High Write Throughput:** Chat aplikasi membutuhkan kemampuan menulis pesan dengan sangat cepat dan dalam jumlah besar. MongoDB dioptimalkan untuk insert-heavy workloads.
- **Flexible Schema:** Struktur pesan chat bisa berkembang (misal: menambahkan reactions, attachments, metadata AI) tanpa perlu migrasi skema tabel yang rumit (ALTER TABLE).
- **Horizontal Scaling (Sharding):** MongoDB mendukung sharding secara native, memudahkan scaling jika jumlah pesan mencapai jutaan/milyaran.

### b. Struktur Data (Data Structure)
- Pesan chat secara alami berbentuk dokumen JSON. Menyimpannya sebagai dokumen BSON di MongoDB menghindari overhead "Object-Relational Mapping" (ORM) dan JOIN operation yang mahal saat mengambil history percakapan.

## 2. Skema Database

### Collection: `chat_messages`

| Field | Tipe Data | Deskripsi | Index |
|-------|-----------|-----------|-------|
| `_id` | UUID/ObjectId | Unique Identifier pesan | PK |
| `user_id` | String | ID pengguna | Yes (Asc) |
| `room_id` | String | ID ruang chat/sesi | Yes (Asc) |
| `role` | String | 'user' atau 'assistant' | - |
| `content` | String | Isi pesan | - |
| `timestamp` | Date | Waktu pengiriman (UTC) | Yes (Desc) |
| `is_deleted` | Boolean | Flag soft delete | - |

### Indexing Strategy
1. **`room_id_1_timestamp_-1`**: Compound index ini sangat krusial. Query paling umum adalah "Ambil X pesan terakhir dari Room Y". Index ini memungkinkan database langsung melompat ke room yang tepat dan mengambil pesan terurut waktu tanpa sorting di memori.
2. **`user_id_1`**: Untuk fitur "Lihat semua pesan saya".
3. **`timestamp_-1`**: Untuk keperluan retensi data (TTL) dan analisis global.

## 3. Fitur Utama

### a. Pagination
Menggunakan `limit` dan `skip` (atau cursor-based pagination untuk performa lebih tinggi di data skala besar). API saat ini mengimplementasikan offset-based pagination (`skip/limit`) yang cukup untuk kebutuhan aplikasi ini.

### b. Soft Delete
Pesan tidak langsung dihapus dari disk (`DELETE`), melainkan hanya ditandai dengan flag `is_deleted: true`.
- **Keuntungan:** Audit trail, recovery jika tidak sengaja terhapus, menjaga integritas referensi.
- **Query:** Semua query `read` harus menyertakan filter `{ is_deleted: false }`.

### c. Data Retention Policy
Fungsi `enforce_retention_policy(days=30)` dijalankan secara periodik (cron job) untuk menghapus fisik pesan yang lebih tua dari 30 hari guna menghemat penyimpanan dan menjaga performa index.

## 4. API Endpoints (FastAPI)

Implementasi REST API tersedia di `api.py`.

- **POST /messages/**: Menyimpan pesan baru.
- **GET /messages/{room_id}**: Mengambil history chat (mendukung pagination).
- **DELETE /messages/{message_id}**: Menghapus pesan (soft delete).

## 5. Implementasi Python

File `chat_database.py` mengenkapsulasi logika database menggunakan driver `pymongo`.

```python
# Contoh Penggunaan
db = ChatDatabase(uri="mongodb://localhost:27017")
db.save_message("user123", "session_1", "user", "Halo!")
history = db.get_history("session_1", limit=10)
```
