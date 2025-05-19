# Hướng dẫn cài đặt Odoo Chatopia

## 1. Cài đặt Docker Desktop
Tải: [https://docs.docker.com/desktop/setup/install/windows-install/]

## 2. Clone source code
git clone https://github.com/subinkhang/odoo-chatopia.git
cd odoo-chatopia

## 3. Chuyển sang nhánh `main`

## 4. Chạy lệnh
docker-compose up -d

## 5. Truy cập Odoo
Mở trình duyệt và vào: [http://localhost:8069/]

## 6. Tạo database
Nhập thông tin như sau:
- Master Password: `odoo123`
- Database Name: `odoo_dev_database`
- Email: (mail trường)
- Password: `odoo123`

## 7. Đăng nhập
Sử dụng Email và Password ở trên để đăng nhập

## 8. Cài đặt các module
Bấm 9 hình vuông góc trên trái → Apps  
Trong ô Search xóa chữ "Apps" → rồi search tiếp:
- Chatopia
- Contact
- Automation Rules *(phải xoá chữ "Apps" trong khung search thì mới thấy)*

## 9. Import dữ liệu
### 9.1. Import Contact
- Bấm 9 hình vuông, Vào **Contact** → Import Records
- Upload file: `db_backups/Contact (res.partner).xlsx`
- Sẽ bị lỗi ở 1 ô Select, thì chọn `name`
- Bấm **Import**

### 9.2. Import Conversation
- Vào **Chatopia** → Import Records
- Upload file: `db_backups/Chat Conversation (chatopia.conversation).xlsx`
- Bấm **Import**

### 9.3. Import Automation Rules
- Vào **Settings** → Scroll xuống dưới → Bấm **Activate the developer mode**
- Vào lại **Settings** → Technical trên thanh header → Automation Rules
- Bấm **Import Records**
- Chọn file: `db_backups/Automation Rule (base.automation).xlsx`

## 10. Cấu hình Automation Rules
### 10.1.
- Bấm vào Contact
- Ở chỗ Target Record đặt thành: model.search([], limit=1)

### 10.2.
- Bấm nút Add an Action → Execute code
- Copy code tương ứng của khúc Contact từ file `automation-rule.txt`:
  - Tương tự với Conversation và Message
    - Conversation → dùng code cho Conversation
    - Message → dùng code cho Message
