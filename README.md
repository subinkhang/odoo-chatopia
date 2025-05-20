# Hướng dẫn cài đặt Odoo Chatopia
## 1. Cài đặt Docker Desktop
Tải: [https://docs.docker.com/desktop/setup/install/windows-install/]

## 2. Clone source code
git clone https://github.com/subinkhang/odoo-chatopia.git

## 3. Chuyển sang nhánh `main`, mở VScode chưa file docker-compose.yml

## 4. Mở terminal chạy lệnh
docker-compose up -d

## 5. Truy cập Odoo
Mở trình duyệt và vào: [http://localhost:8069/]

## 6. Bấm link Restore database
Nhập thông tin như sau:
- Master Password: `odoo123`  <!-- Mỗi máy khác nhau -->
- Choose file: .zip
- Database Name: `odoo_dev_database`

## 7. Đăng nhập
- Email: `22520622@gm.uit.edu.vn`
- Password: `odoo123`
