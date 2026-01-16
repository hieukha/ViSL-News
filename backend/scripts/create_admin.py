"""
Script to create admin user
Run: python scripts/create_admin.py
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.core.config import DATABASE_URL
from app.core.security import get_password_hash
from app.models.user import User

def create_admin():
    # Connect to database
    engine = create_engine(DATABASE_URL)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    
    # Admin credentials
    email = input("Nhập email admin: ").strip()
    if not email:
        email = "admin@visl.com"
        print(f"Sử dụng email mặc định: {email}")
    
    full_name = input("Nhập tên admin: ").strip()
    if not full_name:
        full_name = "Admin"
        print(f"Sử dụng tên mặc định: {full_name}")
    
    password = input("Nhập mật khẩu: ").strip()
    if not password:
        password = "admin123"
        print(f"Sử dụng mật khẩu mặc định: {password}")
    
    try:
        # Check if admin already exists
        existing = db.query(User).filter(User.email == email).first()
        if existing:
            if existing.role == "admin":
                print(f"❌ Admin với email {email} đã tồn tại!")
            else:
                # Update existing user to admin
                existing.role = "admin"
                db.commit()
                print(f"✅ Đã nâng cấp user {email} lên Admin!")
            return
        
        # Create new admin user
        admin = User(
            email=email,
            full_name=full_name,
            password_hash=get_password_hash(password),
            role="admin",
            is_active=True
        )
        db.add(admin)
        db.commit()
        
        print(f"\n✅ Tạo Admin thành công!")
        print(f"   Email: {email}")
        print(f"   Mật khẩu: {password}")
        print(f"   Role: admin")
        
    except Exception as e:
        print(f"❌ Lỗi: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 50)
    print("   TẠO TÀI KHOẢN ADMIN - ViSL Tool")
    print("=" * 50)
    create_admin()


