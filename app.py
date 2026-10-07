import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)

# ดึง URL และปรับแต่งให้รองรับ psycopg2 และ SSL เต็มรูปแบบ
DATABASE_URL = os.environ.get('DATABASE_URL', '')
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
    
    # ตัดพารามิเตอร์เก่าออกแล้วใส่ใหม่ให้ถูกต้องป้องกัน SSL Error
    if "?" in DATABASE_URL:
        DATABASE_URL = DATABASE_URL.split("?")[0]
    
    DATABASE_URL += "?sslmode=require"

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key_sublon_2026'

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_size": 3,
    "max_overflow": 5,
    "connect_args": {
        "sslmode": "require",
        "keepalives": 1,
        "keepalives_idle": 30,
        "keepalives_interval": 10,
        "keepalives_count": 5
    }
}

db = SQLAlchemy(app)
