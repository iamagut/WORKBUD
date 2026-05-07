## WorkBuddy (Python Tkinter)

**WorkBuddy** là một công cụ desktop đơn giản giúp giải quyết vấn đề thường gặp hằng ngày: thư mục lộn xộn và mất thời gian tìm kiếm tệp.

Ứng dụng có thể:

- **Quét thư mục** và thống kê loại tệp + tổng dung lượng
- **Hiển thị biểu đồ** (biểu đồ tròn theo nhóm + biểu đồ thanh các đuôi tệp phổ biến)
- **Xuất kết quả ra CSV**
- **Lưu lịch sử quét vào SQLite**
- **Tự động sắp xếp tệp** vào các thư mục theo nhóm (Images, Documents, Code, ...)
- **Advanced tools (ẩn trong Advanced dropdown)**:
  - **Filter/Search** (lọc nhanh bảng theo tên/đường dẫn/đuôi/nhóm)
  - **Find duplicates** (phát hiện tệp trùng theo size + SHA-256) + export CSV
  - **Undo last organize** (hoàn tác lần sắp xếp gần nhất)
  - **Compare scans** (so sánh scan hiện tại với 1 scan đã lưu trong SQLite) + export CSV
  - **Insights / Cleanup** (top file lớn nhất, file cũ nhất, empty folders) + export CSV
  - **Right-click menu** trên bảng: mở trong File Explorer, copy full path (double-click để mở nhanh)

### Công nghệ sử dụng

- **Python**
- **tkinter**: giao diện GUI
- **pandas**: xử lý dữ liệu + xuất CSV
- **matplotlib**: vẽ biểu đồ trong GUI
- **sqlite3**: cơ sở dữ liệu lưu lịch sử quét

### Cài đặt

1. Tạo môi trường ảo (khuyến nghị):

```bash
python -m venv .venv
```

2. Kích hoạt môi trường ảo:

- PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

3. Cài thư viện cần thiết:

```bash
pip install pandas matplotlib
```

### Chạy chương trình

```bash
python app.py
```

### Cấu trúc Code (Modular Architecture)

Ứng dụng được tổ chức thành 3 module riêng biệt để dễ bảo trì và mở rộng:

#### `app.py` - Entry Point (Điểm vào chương trình)
- Nhiệm vụ: Khởi tạo và chạy ứng dụng
- Nội dung: Hàm `main()` để thiết lập matplotlib backend và tạo GUI
- Import: `from gui import WorkBuddyApp`

#### `backend.py` - Backend Logic (Xử lý logic chính)
- **Data Models**:
  - `FileRecord`: Lưu thông tin một tệp (tên, đường dẫn, phần mở rộng, nhóm, kích thước, thời gian sửa)
  - `ScanResult`: Lưu kết quả quét một thư mục (thư mục, số tệp, tổng dung lượng, danh sách tệp)
- **Database (`HistoryDB`)**:
  - Quản lý SQLite database lưu lịch sử quét, thao tác sắp xếp, và quản lý thùng quarantine
  - Ghi/đọc dữ liệu từ 3 bảng chính: `scans`, `organize_ops`, `quarantine_ops`
- **Scanner (`FolderScanner`)**:
  - Quét thư mục (đệ quy hoặc không) và thu thập thông tin tệp
  - Phân loại tệp theo nhóm (Images, Documents, Code, ...)
  - Xử lý lỗi tệp bị khóa hoặc không đọc được
- **Organizer (`Organizer`)**:
  - Đề xuất di chuyển tệp dựa trên nhóm hoặc rules
  - Thực hiện di chuyển tệp với xử lý trùng tên
  - Hỗ trợ undo (hoàn tác) thao tác sắp xếp
- **Utility Functions**:
  - `human_bytes()`: Chuyển đổi bytes thành MB/GB/TB
  - `safe_relpath()`: Tính đường dẫn tương đối an toàn
  - `category_for_extension()`: Xác định nhóm tệp từ phần mở rộng

#### `gui.py` - GUI (Giao diện người dùng)
- **Main Class `WorkBuddyApp(tk.Tk)`**:
  - Xây dựng giao diện tkinter hoàn chỉnh
  - Quản lý luồng quét (threading) để UI không bị đơ
  - Hiển thị biểu đồ (pie chart + bar chart) bằng matplotlib
- **Core Features**:
  - Scanning: Quét thư mục với tuỳ chọn recursive và hidden files
  - Organization: Sắp xếp tệp vào thư mục theo nhóm
  - Duplicate Detection: Tìm tệp trùng bằng size + SHA-256
  - History Management: Lưu/so sánh lịch sử quét
  - Advanced Tools: Insights, Quarantine, Undo history, Rules-based organize
- **UI Components**:
  - Header: Chọn thư mục, tuỳ chọn scan, nút Scan
  - Main Area: Bảng tệp + biểu đồ (2-pane layout)
  - Advanced Panel: Các công cụ nâng cao (được ẩn/hiện)
  - Status Bar: Hiển thị thông tin trạng thái

### Key Design Patterns

- **Separation of Concerns**: Logic riêng biệt khỏi UI
- **Threading**: Quét chạy nền để UI mượt mà
- **Database Persistence**: SQLite lưu lịch sử để có thể so sánh/hoàn tác
- **Error Handling**: Xử lý lỗi tệp bị khóa, permissions, ...  

### Cách demo (2–3 phút)

- Chọn một thư mục (ví dụ: `Downloads`)
- Bấm **Scan Folder**
- Trình bày **bảng dữ liệu** và **biểu đồ**
- Bấm **Export CSV…** rồi mở file CSV
- Bấm **Export SQLite (save scan)** và chỉ ra phần “Recent saved scans”
- (Tuỳ chọn) Thử **Apply Organize** với một thư mục test nhỏ
- Mở **Advanced ▸** để demo nhanh các tính năng nâng cao:
  - **Filter** để lọc bảng
  - **Find duplicates…**
  - Chọn 1 dòng trong “Recent saved scans” → **Compare scans…**
  - **Insights / Cleanup…**

### Lưu ý an toàn

Tính năng sắp xếp sẽ **di chuyển tệp**. Để demo an toàn, hãy dùng một thư mục test nhỏ với các bản sao của tệp.