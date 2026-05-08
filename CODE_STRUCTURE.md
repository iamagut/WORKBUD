# Hướng Dẫn Cấu Trúc Mã Nguồn & Kiến Trúc WorkBuddy

Tài liệu này giải thích cấu trúc mã nguồn để các thành viên trong nhóm có thể hiểu dự án.

## Tổng Quan Dự Án

**WorkBuddy** là một công cụ phân tích thư mục và tổ chức tệp có giao diện GUI. Nó giúp người dùng:

* Quét thư mục và lấy thống kê tệp
* Trực quan hóa dữ liệu bằng biểu đồ (biểu đồ tròn, biểu đồ cột)
* Xuất kết quả sang CSV hoặc SQLite
* Tự động tổ chức tệp vào các thư mục danh mục
* Tìm các tệp trùng lặp
* Quản lý và hoàn tác các thao tác tổ chức
* Cách ly các tệp đáng ngờ/không mong muốn
* So sánh trạng thái thư mục giữa các lần quét đã lưu
* Lên lịch quét tự động và theo dõi thay đổi

## Kiến Trúc Mã Nguồn (3 Module)

```text
app.py          [Điểm Khởi Động]
    ↓
gui.py          [Giao Diện Người Dùng - tkinter]
    ↓
backend.py      [Logic Nghiệp Vụ - quét, cơ sở dữ liệu, tổ chức]
```

### Module 1: `app.py` - Điểm Khởi Động (~40 dòng)

**Mục đích**: Khởi chạy ứng dụng

**Mã chính**:

```python
def main():
    # Thiết lập backend matplotlib để tương thích với tkinter
    matplotlib.use('TkAgg')

    # Tạo cửa sổ chính
    root = tk.Tk()

    # Khởi chạy ứng dụng
    app = FileAnalyzerGUI(root)

    # Bắt đầu vòng lặp GUI
    root.mainloop()
```

**Những gì file này thực hiện**:

1. Thiết lập matplotlib để hoạt động với tkinter
2. Tạo cửa sổ ứng dụng chính
3. Khởi tạo GUI
4. Khởi chạy vòng lặp sự kiện

**Điểm quan trọng**:

* Đây là file mà người dùng chạy (`python app.py`)
* Rất nhỏ vì chỉ có nhiệm vụ khởi động ứng dụng
* Không chứa logic nghiệp vụ

---

### Module 2: `gui.py` - Giao Diện Người Dùng (~1500+ dòng)

**Mục đích**: Xử lý toàn bộ giao diện người dùng

#### Class Chính: `FileAnalyzerGUI`

```python
class FileAnalyzerGUI:
    def __init__(self, root):
        # Khởi tạo GUI
```

### Thành Phần Giao Diện

#### 1. Các Tab Notebook

Ứng dụng có nhiều tab:

```python
self.notebook = ttk.Notebook(root)

# Các tab
self.main_frame      # Tab phân tích chính
self.charts_frame    # Tab biểu đồ
self.organize_frame  # Tab tổ chức tệp
self.duplicates_frame # Tab tệp trùng lặp
self.quarantine_frame # Tab cách ly
self.schedule_frame   # Tab lập lịch
```

**Mục đích của từng tab**:

| Tab              | Chức năng                            |
| ---------------- | ------------------------------------ |
| Main Analyzer    | Quét thư mục, xem thống kê           |
| Charts           | Hiển thị biểu đồ tròn và biểu đồ cột |
| Organize Files   | Tự động sắp xếp tệp                  |
| Duplicate Finder | Tìm và quản lý tệp trùng lặp         |
| Quarantine       | Quản lý tệp đáng ngờ                 |
| Schedule         | Thiết lập quét tự động               |

---

#### 2. Các Widget Giao Diện Chính

##### Chọn Thư Mục

```python
self.folder_path = tk.StringVar()
self.folder_entry = ttk.Entry(...)
self.browse_btn = ttk.Button(...)
```

**Mục đích**: Cho phép người dùng chọn thư mục để quét.

##### Khu Vực Kết Quả

```python
self.results_text = scrolledtext.ScrolledText(...)
```

**Mục đích**: Hiển thị kết quả phân tích dưới dạng văn bản.

##### Thanh Tiến Trình

```python
self.progress = ttk.Progressbar(...)
```

**Mục đích**: Hiển thị tiến trình quét.

##### Treeview

```python
self.tree = ttk.Treeview(...)
```

**Mục đích**: Hiển thị dữ liệu dạng bảng.

---

### Các Hàm GUI Quan Trọng

#### `browse_folder()`

```python
def browse_folder(self):
    folder = filedialog.askdirectory()
```

**Chức năng**:

* Mở hộp thoại chọn thư mục
* Lưu đường dẫn đã chọn
* Cập nhật giao diện

---

#### `analyze_folder()`

```python
def analyze_folder(self):
    # Gọi backend để quét thư mục
    stats = analyze_directory(folder_path)
```

**Quy trình**:

1. Lấy đường dẫn thư mục từ người dùng
2. Gọi hàm backend
3. Nhận kết quả
4. Hiển thị kết quả trên GUI
5. Cập nhật biểu đồ

**Đây là cầu nối giữa GUI và backend.**

---

#### `display_results()`

```python
def display_results(self, stats):
    # Hiển thị thống kê trong vùng văn bản
```

**Chức năng**:

* Định dạng dữ liệu
* Hiển thị thống kê
* Cập nhật bảng

---

#### `create_charts()`

```python
def create_charts(self, data):
    # Tạo biểu đồ matplotlib
```

**Chức năng**:

* Tạo biểu đồ tròn
* Tạo biểu đồ cột
* Nhúng biểu đồ vào tkinter

---

### Thiết Kế GUI Quan Trọng

#### Mô Hình Event-Driven

GUI hoạt động dựa trên sự kiện:

```python
button = ttk.Button(command=self.analyze_folder)
```

Khi người dùng nhấn nút:

1. Sự kiện xảy ra
2. Hàm callback chạy
3. Backend được gọi
4. GUI cập nhật

---

#### Threading (Đa Luồng)

Để tránh GUI bị treo:

```python
threading.Thread(target=self.run_analysis).start()
```

**Tại sao cần thiết**:

* Quét thư mục lớn mất thời gian
* Nếu không dùng thread, GUI sẽ bị đơ
* Thread giúp GUI vẫn phản hồi

---

#### Quản Lý Trạng Thái

GUI lưu trạng thái bằng biến:

```python
self.current_stats
self.selected_folder
self.scan_history
```

---

### Module 3: `backend.py` - Logic Nghiệp Vụ (~2000+ dòng)

**Mục đích**: Chứa toàn bộ logic xử lý thực tế.

Đây là nơi diễn ra các công việc chính.

---

## Các Chức Năng Backend Chính

### 1. Phân Tích Thư Mục

#### Hàm: `analyze_directory()`

```python
def analyze_directory(path):
```

**Chức năng**:

* Duyệt qua tất cả tệp trong thư mục
* Thu thập thống kê
* Tính tổng dung lượng
* Đếm loại tệp
* Tìm thư mục lớn

**Quy trình**:

```text
Bắt đầu
  ↓
Kiểm tra thư mục
  ↓
Duyệt tệp bằng os.walk()
  ↓
Xử lý từng tệp
  ↓
Thu thập thống kê
  ↓
Trả kết quả
```

---

#### Cách Quét Hoạt Động

```python
for root, dirs, files in os.walk(path):
    for file in files:
        file_path = os.path.join(root, file)
```

**`os.walk()` thực hiện**:

* Đi qua tất cả thư mục con
* Trả về:

  * `root` = thư mục hiện tại
  * `dirs` = danh sách thư mục con
  * `files` = danh sách tệp

Ví dụ:

```text
Documents/
├── file1.txt
├── Images/
│   └── pic.jpg
```

`os.walk()` sẽ truy cập:

1. `Documents/`
2. `Documents/Images/`

---

### 2. Thống Kê Tệp

#### Lấy Kích Thước Tệp

```python
size = os.path.getsize(file_path)
```

#### Lấy Phần Mở Rộng Tệp

```python
extension = os.path.splitext(file)[1]
```

Ví dụ:

```python
"photo.jpg" → ".jpg"
```

---

### 3. Tổ Chức Tệp

#### Hàm: `organize_files()`

```python
def organize_files(path, rules):
```

**Chức năng**:

* Phân loại tệp theo loại
* Di chuyển tệp vào thư mục tương ứng
* Tạo thư mục nếu chưa tồn tại

Ví dụ:

```text
Before:
Downloads/
    photo.jpg
    music.mp3

After:
Downloads/
    Images/photo.jpg
    Audio/music.mp3
```

---

#### Logic Phân Loại

```python
categories = {
    'Images': ['.jpg', '.png'],
    'Audio': ['.mp3', '.wav'],
}
```

---

### 4. Tìm Tệp Trùng Lặp

#### Hàm: `find_duplicates()`

```python
def find_duplicates(path):
```

**Cách hoạt động**:

1. Đọc nội dung tệp
2. Tạo hash
3. So sánh hash
4. Nếu hash giống nhau → tệp trùng lặp

---

#### Hashing

```python
hashlib.md5(file_content).hexdigest()
```

**Ví dụ**:

```text
file1.txt → abc123
file2.txt → abc123
```

=> Trùng lặp

---

### 5. Cơ Sở Dữ Liệu SQLite

#### Kết Nối Database

```python
conn = sqlite3.connect('workbuddy.db')
```

**Database lưu**:

* Lịch sử quét
* Nhật ký tổ chức
* Thông tin cách ly
* Dữ liệu lịch trình

---

#### Ví Dụ SQL

```sql
CREATE TABLE scans (
    id INTEGER PRIMARY KEY,
    folder TEXT,
    scan_date TEXT
)
```

---

### 6. Xuất CSV

```python
with open('results.csv', 'w') as file:
```

**Chức năng**:

* Xuất dữ liệu phân tích
* Tạo báo cáo
* Chia sẻ kết quả

---

### 7. Quarantine (Cách Ly)

#### Mục đích

Di chuyển các tệp đáng ngờ đến nơi an toàn.

```python
shutil.move(file_path, quarantine_path)
```

---

### 8. Lập Lịch & Theo Dõi

#### Scheduler

```python
schedule.every(1).hours.do(scan)
```

**Chức năng**:

* Quét tự động
* Theo dõi thay đổi thư mục
* Chạy nền

---

## Luồng Dữ Liệu Hoàn Chỉnh

```text
Người dùng nhấn “Analyze”
        ↓
GUI nhận sự kiện
        ↓
GUI gọi backend.analyze_directory()
        ↓
Backend quét thư mục
        ↓
Backend trả dữ liệu
        ↓
GUI hiển thị kết quả
        ↓
GUI tạo biểu đồ
```

---

## Mẫu Thiết Kế (Design Patterns)

### 1. Separation of Concerns

| Module     | Trách nhiệm          |
| ---------- | -------------------- |
| app.py     | Khởi động ứng dụng   |
| gui.py     | Giao diện người dùng |
| backend.py | Logic xử lý          |

**Lợi ích**:

* Dễ bảo trì
* Dễ debug
* Dễ mở rộng

---

### 2. MVC-Like Structure

| Thành phần     | Vai trò    |
| -------------- | ---------- |
| GUI            | View       |
| Backend        | Model      |
| Event handlers | Controller |

---

## Thư Viện Được Sử Dụng

| Library    | Mục đích               |
| ---------- | ---------------------- |
| tkinter    | GUI                    |
| matplotlib | Biểu đồ                |
| os         | Thao tác hệ thống tệp  |
| shutil     | Di chuyển/sao chép tệp |
| sqlite3    | Cơ sở dữ liệu          |
| hashlib    | Tạo hash               |
| threading  | Đa luồng               |
| schedule   | Lập lịch               |
| pandas     | Xử lý dữ liệu          |

---

## Quy Trình Khi Người Dùng Sử Dụng Ứng Dụng

### Ví dụ: Người dùng quét thư mục

### Bước 1: Người dùng chọn thư mục

GUI:

```python
filedialog.askdirectory()
```

---

### Bước 2: Người dùng nhấn Analyze

GUI gọi:

```python
analyze_directory(path)
```

---

### Bước 3: Backend quét tệp

Backend:

```python
os.walk(path)
```

---

### Bước 4: Backend thu thập dữ liệu

Ví dụ:

```python
{
    'total_files': 100,
    'total_size': '2 GB'
}
```

---

### Bước 5: GUI hiển thị dữ liệu

```python
results_text.insert()
```

---

## Các Điểm Quan Trọng Cho Thành Viên Nhóm

### Nếu bạn muốn chỉnh sửa giao diện:

➡ Làm việc trong `gui.py`

Ví dụ:

* Thêm nút
* Đổi màu
* Tạo tab mới
* Cập nhật layout

---

### Nếu bạn muốn thay đổi logic:

➡ Làm việc trong `backend.py`

Ví dụ:

* Thuật toán quét mới
* Quy tắc tổ chức mới
* Tìm trùng lặp tốt hơn
* Xuất dữ liệu mới

---

### Nếu bạn muốn khởi chạy ứng dụng:

➡ Chạy:

```bash
python app.py
```

---

## Những Khái Niệm Python Quan Trọng Được Sử Dụng

### 1. Classes

```python
class FileAnalyzerGUI:
```

Dùng để tổ chức mã.

---

### 2. Functions

```python
def analyze_directory():
```

Dùng để tái sử dụng logic.

---

### 3. Dictionaries

```python
stats = {
    'files': 10
}
```

Lưu dữ liệu theo cặp key-value.

---

### 4. Lists

```python
files = []
```

Lưu nhiều giá trị.

---

### 5. Loops

```python
for file in files:
```

Lặp qua dữ liệu.

---

### 6. Exception Handling

```python
try:
    pass
except Exception as e:
    pass
```

Ngăn ứng dụng bị crash.

---

## Cách Mở Rộng Dự Án

### Thêm Tính Năng Mới

Ví dụ: Thêm “AI file categorization”

### Bước 1

Thêm logic vào `backend.py`

### Bước 2

Thêm nút/tab vào `gui.py`

### Bước 3

Kết nối GUI với backend

---

## Tổng Kết

### `app.py`

* Khởi động ứng dụng
* Nhỏ và đơn giản

### `gui.py`

* Toàn bộ giao diện người dùng
* Nút, tab, biểu đồ, bảng
* Xử lý tương tác người dùng

### `backend.py`

* Toàn bộ logic chính
* Quét tệp
* Tổ chức tệp
* Database
* Trùng lặp
* Xuất dữ liệu

---

## Tư Duy Quan Trọng

Dự án hoạt động theo nguyên tắc:

```text
GUI = những gì người dùng nhìn thấy
Backend = công việc thực tế được thực hiện
```

GUI chỉ:

* Nhận input
* Hiển thị output

Backend:

* Xử lý dữ liệu
* Thực hiện công việc
* Trả kết quả
