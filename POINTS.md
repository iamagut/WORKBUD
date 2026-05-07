## WorkBuddy — Công cụ phân tích & sắp xếp thư mục (Python)

### 1 — Vấn đề
- Trong công việc hằng ngày, các thư mục như Downloads/Desktop rất dễ bị lộn xộn.
- Mất thời gian để tìm kiếm, phân loại và biết tệp nào đang chiếm dung lượng.
- Sắp xếp thủ công thường chậm và không đồng nhất.

### 2 — Giải pháp
**WorkBuddy** là ứng dụng desktop viết bằng Python có thể:
- Quét thư mục người dùng chọn
- Tạo thống kê dựa trên dữ liệu (số lượng + dung lượng)
- Trực quan hoá bằng biểu đồ
- Xuất kết quả ra CSV
- Lưu lịch sử quét vào SQLite
- Tự động sắp xếp tệp theo nhóm thư mục
- Có **Advanced dropdown** (ẩn các tính năng nâng cao để UI gọn hơn)

### 3 — Tính năng (Luồng demo)
- Chọn thư mục → **Scan Folder**
- Xem:
  - Summary (số tệp, tổng dung lượng, top nhóm/đuôi tệp)
  - Bảng danh sách tệp (đã sắp xếp)
  - Biểu đồ (tròn + thanh)
- Xuất dữ liệu:
  - **Export CSV**
  - **Export SQLite**
- Tự động hoá:
  - **Apply Organize** (di chuyển tệp vào các thư mục như Images/Documents/Code)
- Nâng cao (mở **Advanced ▸**):
  - **Filter/Search** trong bảng
  - **Find duplicates** (size + SHA-256) + export CSV
  - **Undo last organize**
  - **Compare scans** (scan hiện tại vs scan đã lưu) + export CSV
  - **Insights / Cleanup** (top file lớn nhất/cũ nhất, empty folders) + export CSV
  - **Right-click menu**: mở trong File Explorer, copy full path

### 4 — Công cụ & công nghệ
- Python 3
- tkinter (GUI)
- pandas (xử lý dữ liệu + xuất CSV)
- matplotlib (biểu đồ)
- sqlite3 (cơ sở dữ liệu lưu lịch sử)

**Cấu trúc Code (Modular Architecture)**:
- `app.py`: Entry point — khởi tạo matplotlib backend và chạy ứng dụng
- `backend.py`: Backend logic — quét, sắp xếp, database (HistoryDB, FolderScanner, Organizer)
- `gui.py`: GUI — giao diện tkinter hoàn chỉnh với tất cả tính năng

### 5 — Vì sao đây là “data-driven”
- Mỗi lần quét tạo ra một bộ dữ liệu gồm:
  - tên tệp, đuôi tệp, nhóm, dung lượng, thời gian sửa gần nhất, đường dẫn
- Biểu đồ được cập nhật dựa trên dữ liệu quét thực tế
- Dữ liệu xuất ra có thể tái sử dụng (Excel/Google Sheets/Database)

### 6 — Khó khăn & cách giải quyết
- **Không bị đơ giao diện**: quét chạy ở luồng nền (background thread) để GUI vẫn mượt.
- **Tệp bị khoá / lỗi quyền truy cập**: bỏ qua tệp không đọc được thay vì làm app bị crash.
- **Trùng tên khi di chuyển**: tự đổi tên dạng `file (1).txt`.

### 7 — Hạn chế & hướng phát triển
- (Gợi ý mở rộng tiếp) Lịch quét tự động + báo cáo định kỳ
- (Gợi ý mở rộng tiếp) Rule-based organize (theo project/date/owner) + dry-run preview chi tiết hơn
- (Gợi ý mở rộng tiếp) Quản lý duplicate: chọn giữ/xoá/di chuyển an toàn
- (Gợi ý mở rộng tiếp) Phân quyền/ignore list (.gitignore style) cho scan

### 8 — Kết luận
WorkBuddy giúp tiết kiệm thời gian bằng cách biến một thư mục lộn xộn thành:
- Thông tin rõ ràng (summary + biểu đồ)
- Dữ liệu có thể dùng lại (CSV + SQLite)
- Sắp xếp tự động (một lần bấm)
- Công cụ nâng cao vẫn sẵn sàng khi cần (Advanced dropdown)

