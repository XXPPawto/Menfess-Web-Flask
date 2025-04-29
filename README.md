# Menfess Web Flask

Aplikasi web berbasis Flask untuk mengirim dan membaca menfess secara anonim, lengkap dengan sistem login, register, admin panel, dan pagination.

## 🚀 Fitur
- Login & Register (Flask-Login)
- Admin panel: kelola user, kategori, laporan, menfess
- Pagination menfess (Flask-Paginate)
- Sistem komentar dan laporan
- Database SQLite

## 🧑‍💻 Teknologi
- Python + Flask
- SQLite + SQLAlchemy
- Flask-Login
- HTML/CSS (Bootstrap)
- Flask-Paginate

---

## 🔧 Cara Menjalankan Aplikasi

### 1. Clone Repository
```bash
git clone https://github.com/XXPawto/Menfess-Web-Flask.git
cd Menfess-Web-Flask

# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate

pip install -r requirements.txt

create file name requirements.txt fill the file with
Flask==2.2.3
Flask-SQLAlchemy==3.0.3
Flask-Login==0.6.2
Flask-Paginate==2022.1.8
Werkzeug==2.2.3

Start application
python app.py
