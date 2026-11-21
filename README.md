# SmartInsight

Hệ thống **hỏi–đáp tài liệu cá nhân** (RAG — Retrieval-Augmented Generation): upload tài liệu PDF/DOCX/TXT/MD, hệ thống bóc tách – chia nhỏ – embedding – lưu vào vector store, sau đó cho phép đặt câu hỏi và nhận câu trả lời **kèm trích dẫn nguồn**.

> Trạng thái: backend đang trong quá trình hoàn thiện (xem [Roadmap](#roadmap)). Frontend chưa triển khai.

---

## Tính năng

| Nhóm | Chức năng |
|---|---|
| Xác thực | Đăng ký, đăng nhập, refresh token, thông tin cá nhân. JWT access + refresh, mật khẩu hash bcrypt. |
| Tài liệu | Upload (giới hạn loại file & dung lượng, chống trùng theo SHA-256), xử lý RAG chạy nền với trạng thái `pending/processing/ready/failed`, danh sách có phân trang, xem chi tiết, sửa, xoá (kèm file + vector), xử lý lại (reindex). |
| Hỏi–đáp | Hỏi trên toàn bộ tài liệu hoặc giới hạn theo `document_ids`, trả về câu trả lời + danh sách nguồn (file, chunk, similarity). |
| Tóm tắt | Tóm tắt một tài liệu với độ dài tuỳ chọn. |
| Lịch sử | Lưu hội thoại theo `session_id`, xem và xoá phiên chat. |
| Cách ly dữ liệu | Mọi truy vấn vector đều lọc theo `user_id` — người dùng không thấy dữ liệu của nhau. |
| Vận hành | Rate limit theo IP, log có `X-Request-ID` + thời gian xử lý, lỗi JSON nhất quán, `/health` kiểm tra Mongo/vector store/Ollama. |

---

## Kiến trúc

```
backend/
├── main.py                     # FastAPI app, CORS, lifespan, mount routers
├── data/
│   ├── uploads/                # file gốc (chưa dùng - sẽ bật ở Phase 4)
│   └── vectors/                # vector store persist (npy + json)
└── app/
    ├── api/                    # routers: users, documents, chats
    ├── core/                   # config, database (Mongo async), security (JWT)
    ├── schema/                 # Pydantic models
    ├── service/                # business logic: user, document, chat
    ├── engine/
    │   ├── processor.py        # PDF/DOCX/TXT/MD -> text -> chunk
    │   ├── embedding.py        # SentenceTransformer
    │   ├── llm.py              # Ollama client
    │   └── rag.py              # orchestrate: index & retrieve & answer
    └── mini_vector_db/         # vector store tự viết (NumPy, cosine similarity)
```

**Luồng RAG**

```
Upload ──> DocumentProcessor (extract text)
       ──> chunk_text (cắt theo câu, có overlap)
       ──> EmbeddingGenerator (SentenceTransformer)
       ──> MiniVectorBase.add_vectors  ──> data/vectors/*.npy|json
                                        └─> MongoDB.documents (metadata)

Query  ──> embed query
       ──> MiniVectorBase.search(filter: user_id, document_ids)
       ──> ghép context ──> LLM (Ollama) ──> answer + sources
```

---

## Yêu cầu môi trường

| Thành phần | Phiên bản | Ghi chú |
|---|---|---|
| Python | **3.10 – 3.12** | `torch`/`sentence-transformers` chưa hỗ trợ 3.14 |
| MongoDB | >= 6.0 | dùng `mongodb://localhost:27017` |
| Ollama | mới nhất | chạy local, `ollama pull qwen2.5:7b` |
| RAM | >= 8 GB | embedding model + LLM cùng máy |

---

## Cài đặt & chạy

```bash
# 1. Clone
git clone https://github.com/TrungMK12/smartinsight.git
cd smartinsight

# 2. Tạo virtualenv (khuyến nghị Python 3.11)
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

# 3. Cài dependencies
pip install -r requirements.txt

# 4. Cấu hình
cp .env.example backend/.env
# sửa SECRET_KEY, DATABASE_URL, LLM_MODELNAME... nếu cần

# 5. Chạy MongoDB & Ollama
ollama serve
ollama pull qwen2.5:7b

# 6. Khởi động API (chạy từ ROOT repo, vì import là backend.app.*)
uvicorn backend.main:app --reload
```

- Swagger UI: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health> — trả `200` khi Mongo OK, `503` khi mất kết nối; body gồm trạng thái Mongo/vector store/Ollama.

> **Lần chạy đầu tiên** sẽ tải embedding model (~470 MB) nên khởi động chậm.

---

## Biến môi trường

| Biến | Ví dụ | Mô tả |
|---|---|---|
| `LLM_BASEURL` | `http://localhost:11434` | địa chỉ Ollama |
| `LLM_MODELNAME` | `qwen2.5:7b` | model sinh câu trả lời |
| `LLM_SYSTEM_PROMPT` | `Bạn là trợ lý...` | system prompt |
| `VECTOR_MODELNAME` | `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` | model embedding (đa ngôn ngữ) |
| `VECTOR_DIMENSION` | `384` | phải khớp model embedding |
| `VECTOR_DB_PATH` | `backend/data/vectors` | nơi lưu vector store |
| `DATABASE_URL` | `mongodb://localhost:27017` | MongoDB URI |
| `DATABASE_NAME` | `smartinsight` | tên database |
| `MONGO_TIMEOUT_MS` | `5000` | timeout chọn server Mongo (ms) |
| `SECRET_KEY` | chuỗi random dài | ký JWT |
| `ALGORITHM` | `HS256` | thuật toán JWT |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | hạn access token |
| `REFRESH_TOKEN_EXPIRE_DAYS` | `7` | hạn refresh token |
| `ALLOW_ORIGINS` | `["http://localhost:3000"]` | CORS, JSON array |
| `ALLOWED_EXTENSIONS` | `["pdf","docx","txt","md"]` | loại file cho phép |
| `MAX_UPLOAD_SIZE` | `20971520` | bytes (20 MB) |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `500` / `50` | tham số chunking |

---

## API

Tất cả endpoint (trừ auth) yêu cầu header `Authorization: Bearer <access_token>`.

**Định dạng lỗi** (thống nhất cho mọi lỗi nghiệp vụ):

```json
{ "success": false, "detail": "Tài liệu đã tồn tại (id=...)", "error_code": "duplicate" }
```

**Rate limit** (theo IP, cửa sổ 1 phút): register 5, login 10, refresh 20, upload 10, reindex 5, chat query 30, summarize 10. Vượt hạn mức trả `429` với `error_code: "rate_limited"`.

### User — `/api/user`

| Method | Path | Mô tả |
|---|---|---|
| POST | `/register` | Đăng ký (password phải có chữ số + chữ hoa) |
| POST | `/login` | Trả `access_token` + `refresh_token` |
| POST | `/refresh` | Cấp lại token từ refresh token |
| GET | `/me` | Thông tin user hiện tại |

### Document — `/api/document`

| Method | Path | Mô tả |
|---|---|---|
| POST | `/upload` | Upload file, trả **202** ngay và xử lý RAG ở background (`multipart/form-data`) |
| GET | `/` | Danh sách (phân trang `skip`, `limit`) |
| GET | `/{document_id}` | Chi tiết tài liệu (kèm `status`, `chunk_count`, `error_message`) |
| PATCH | `/{document_id}` | Sửa `title` / `description` |
| POST | `/{document_id}/reindex` | Xoá vector cũ và xử lý lại tài liệu (202) |
| DELETE | `/{document_id}` | Xoá tài liệu + file gốc + vector |

Trạng thái tài liệu: `pending` → `processing` → `ready` (hoặc `failed` kèm `error_message`).

### Chat — `/api/chat`

| Method | Path | Mô tả |
|---|---|---|
| POST | `/query` | Hỏi đáp RAG (`query`, `session_id?`, `document_ids?`, `max_docs`) |
| POST | `/summarize` | Tóm tắt tài liệu (`document_id`, `max_length`) |
| GET | `/history` | Lịch sử chat (`session_id?`, `limit`) |
| DELETE | `/history/{session_id}` | Xoá phiên chat |

### Ví dụ

```bash
# Đăng ký
curl -X POST http://localhost:8000/api/user/register \
  -H "Content-Type: application/json" \
  -d '{"username":"demo123","email":"demo@example.com","password":"Demo1234"}'

# Đăng nhập
TOKEN=$(curl -s -X POST http://localhost:8000/api/user/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@example.com","password":"Demo1234"}' | jq -r .access_token)

# Upload
curl -X POST http://localhost:8000/api/document/upload \
  -H "Authorization: Bearer $TOKEN" \
  -F "file=@./sample.pdf" -F "title=Sample"

# Hỏi
curl -X POST http://localhost:8000/api/chat/query \
  -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
  -d '{"query":"Tài liệu nói gì về ...?","max_docs":5}'
```

---

## Giới hạn hiện tại

1. **Vector store chạy in-process** → bắt buộc `uvicorn --workers 1`. Muốn scale ngang phải chuyển sang Qdrant/Chroma.
2. Embedding chạy trên CPU → upload tài liệu lớn sẽ chậm.
3. Câu trả lời phụ thuộc chất lượng model Ollama; prompt đã ràng buộc "chỉ trả lời từ ngữ cảnh".
4. Chưa có rate limiting.

---

## Roadmap

- [x] Phase 0 — Nền tảng repo (deps, env template, README)
- [x] Phase 1 — Sửa lỗi chặn khởi động
- [x] Phase 2 — Vector store hoàn chỉnh + persist
- [x] Phase 3 — RAG + LLM thật
- [x] Phase 4 — Pipeline tài liệu (lưu file, background job, re-index)
- [x] Phase 5 — Hardening API (error handler, rate limit, logging)
- [ ] Phase 6 — Test & CI
- [ ] Phase 7 — Frontend (Next.js)
- [ ] Phase 8 — Docker & deploy
