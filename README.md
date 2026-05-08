## WorkBuddy (Python Tkinter)

**WorkBuddy** là một công cụ desktop mạnh mẽ giúp giải quyết vấn đề quản lý tệp tin hàng ngày: thư mục lộn xộn và mất thời gian tìm kiếm dữ liệu.

### Ứng dụng có thể:
- **Quét thư mục**: Thống kê loại tệp, phần mở rộng và tổng dung lượng một cách chi tiết.
- **Trực quan hoá dữ liệu**: Hiển thị biểu đồ tròn (theo nhóm) và biểu đồ thanh (theo đuôi tệp phổ biến) bằng Matplotlib.
- **Xuất dữ liệu**: Hỗ trợ xuất kết quả ra tệp CSV hoặc lưu trữ lâu dài trong cơ sở dữ liệu SQLite.
- **Tự động sắp xếp**: Phân loại tệp vào các thư mục theo nhóm như Images, Documents, Code, v.v..
- **Công cụ nâng cao (Advanced Tools)**:
  - **Lọc/Tìm kiếm**: Bộ lọc thời gian thực trong bảng danh sách tệp.
  - **Tìm tệp trùng lặp**: Phát hiện dựa trên kích thước và mã băm SHA-256, hỗ trợ cách ly (quarantine) tệp trùng.
  - **Hoàn tác (Undo)**: Đảo ngược các thao tác sắp xếp tệp gần nhất từ lịch sử.
  - **So sánh lần quét**: So sánh trạng thái thư mục hiện tại với các bản lưu trong quá khứ.
  - **Tự động hóa**: Chế độ theo dõi (Watch mode) để tự động cập nhật khi có thay đổi và lên lịch quét định kỳ.

### Công nghệ sử dụng
- **Python**: Ngôn ngữ lập trình chính.
- **tkinter**: Thư viện xây dựng giao diện người dùng (GUI).
- **pandas**: Xử lý và phân tích dữ liệu tệp.
- **matplotlib**: Vẽ biểu đồ thống kê.
- **sqlite3**: Quản lý cơ sở dữ liệu lịch sử và hoàn tác.

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
