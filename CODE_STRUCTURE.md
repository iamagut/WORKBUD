# Hướng Dẫn Cấu Trúc Mã Nguồn & Kiến Trúc WorkBuddy

Tài liệu này giải thích cấu trúc mã nguồn để các thành viên trong nhóm hiểu dự án.

---

# Tổng Quan Dự Án

**WorkBuddy** là công cụ phân tích thư mục và sắp xếp tệp có giao diện GUI. Nó giúp người dùng:

- Quét thư mục và lấy thống kê tệp
- Trực quan hóa dữ liệu bằng biểu đồ (biểu đồ tròn, biểu đồ cột)
- Xuất kết quả sang CSV hoặc SQLite
- Tự động sắp xếp tệp vào các thư mục phân loại
- Tìm các tệp trùng lặp
- Quản lý và hoàn tác các thao tác sắp xếp
- Cách ly các tệp đáng ngờ / không mong muốn

---

# Kiến Trúc Mã Nguồn (3 Module)

```text
app.py          [Điểm khởi chạy]
    ↓
gui.py          [Giao diện người dùng - tkinter]
    ↓
backend.py      [Logic xử lý - quét, cơ sở dữ liệu, sắp xếp]
```

---

# Module 1: `app.py` - Điểm Khởi Chạy

## Mục đích
Khởi động ứng dụng.

## Mã chính

```python
def main():
    matplotlib.use("TkAgg")

    app = WorkBuddyApp()
    app.mainloop()
```

## Chức năng

1. Thiết lập backend TkAgg cho matplotlib
2. Tạo cửa sổ GUI chính
3. Khởi chạy vòng lặp sự kiện

---

# Module 2: `gui.py` - Giao Diện Người Dùng

## Mục đích
Quản lý toàn bộ giao diện đồ họa và tương tác người dùng.

## Các Class Chính

### `WorkBuddyApp(tk.Tk)`

- Kế thừa từ `tk.Tk`
- Quản lý toàn bộ thành phần UI
- Chạy quét thư mục bằng luồng nền

## Thuộc tính quan trọng

```python
self._scanner = FolderScanner()
self._organizer = Organizer()
self._db = HistoryDB(...)
self._scan_thread = threading.Thread
self._latest_result = None
```

## Các tính năng chính

- Xây dựng giao diện (`_build_ui`)
- Quét thư mục (`_start_scan`)
- Hiển thị kết quả (`_on_scan_complete`)
- Organize file (`_apply_organize`)
- Vẽ biểu đồ (`_render_charts`)
- Tìm duplicate (`_start_find_duplicates`)
- Export CSV / SQLite

---

# Module 3: `backend.py` - Logic Xử Lý

## Mục đích

Chứa toàn bộ logic:
- Quét thư mục
- Database
- Thao tác file

## Data Models

```python
@dataclass(frozen=True)
class FileRecord:
    name: str
    rel_path: str
    ext: str
    category: str
    size_bytes: int
    modified_iso: str
```

```python
@dataclass(frozen=True)
class ScanResult:
    folder: str
    recursive: bool
    include_hidden: bool
    started_at_iso: str
    finished_at_iso: str
    file_count: int
    total_size_bytes: int
    records: Tuple[FileRecord, ...]
```

---

# FolderScanner

## Chức năng

- Quét recursive hoặc flat
- Detect hidden files
- Xử lý file inaccessible
- Categorize file theo extension

---

# Organizer

## Chức năng

- Đề xuất move file
- Move file thực tế
- Xử lý duplicate filename
- Hỗ trợ undo

## Strategy organize

1. Theo category
2. Theo ngày (YYYY/MM)
3. Theo category + extension

---

# HistoryDB

## Database schema

- scans
- files
- organize_ops
- organize_moves
- quarantine_ops

## Chức năng

- Save scan
- Undo organize
- Compare scans
- Restore quarantine

---

# Data Flow

## Scan Flow

```text
User → Scan Folder
    ↓
_start_scan()
    ↓
FolderScanner.scan()
    ↓
ScanResult
    ↓
_on_scan_complete()
```

## Organize Flow

```text
User → Apply Organize
    ↓
propose_moves()
    ↓
Preview
    ↓
apply_moves()
    ↓
save_organize_op()
```

---

# Design Patterns

## Separation of Concerns
Tách UI và business logic.

## Threading
Tránh freeze UI.

## Immutable Data
Thread-safe và ổn định.

## SQLite History
Lưu lịch sử thao tác.

## Error Handling
Không crash toàn bộ app.

---

# Categories File

```python
FILE_CATEGORIES = {
    "Images": .png, .jpg,
    "Documents": .pdf, .docx,
    "Code": .py, .js,
    "Audio": .mp3,
    "Video": .mp4,
    "Archives": .zip
}
```

Unknown extension → `"Other"`

No extension → `"No Extension"`

---

# Advanced Features

- Compare scans
- Insights / Cleanup
- Quarantine manager
- Rules-based organize
- Auto-scan
- Watch mode
- Right-click context menu

---

# Performance

1. Background threads
2. Hash theo size trước
3. SQLite indexing
4. WAL mode
5. Lazy loading

---

# Dependencies

```text
tkinter
pandas
matplotlib
sqlite3
```

---

# Workflow

## Organize Downloads

1. Browse folder
2. Scan
3. Review
4. Apply organize
5. Undo nếu cần

## Find Duplicates

1. Scan
2. Find duplicates
3. Quarantine duplicate files

## Compare Scans

1. Save scan
2. Scan lại
3. Compare

---

# Demo Folder

Bao gồm:
- 30+ file test
- Duplicate files
- Empty folders
- Nhiều loại file

---

# Code Quality

- Type hints
- Docstrings
- Error handling
- Immutable dataclass
- Tách UI và logic rõ ràng
