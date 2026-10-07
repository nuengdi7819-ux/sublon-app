from flask import Flask, render_template_string, request, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import os
import io
import csv

app = Flask(__name__)

# ตั้งค่า URL ฐานข้อมูลให้รองรับ psycopg2 และ SSL เต็มรูปแบบ
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxx.supabase.co:5432/postgres?sslmode=require')
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
    elif DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
    
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

TH_TIMEZONE = timezone(timedelta(hours=7))

def get_thai_today():
    return datetime.now(TH_TIMEZONE).date()

VALID_USERS = {
    'nueng': '909090',
    'nice': '022540'
}

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    sales_name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False, default=get_thai_today)
    last_payment_date = db.Column(db.Date, nullable=True)
    closed_date = db.Column(db.Date, nullable=True)
    original_principal = db.Column(db.Float, nullable=False, default=0.0)
    principal = db.Column(db.Float, nullable=False)                     
    daily_interest = db.Column(db.Float, nullable=False)
    initial_daily_interest = db.Column(db.Float, nullable=False, default=0.0)
    paid_interest = db.Column(db.Float, default=0.0)     
    status = db.Column(db.String(20), default='ปกติ')
    installment_amount = db.Column(db.Float, default=0.0)
    schedule_type = db.Column(db.String(50), nullable=False, default='จ่ายทุกวัน') 
    due_day_of_month = db.Column(db.String(50), nullable=True)
    funding_source = db.Column(db.String(50), default='กรุงศรีอยุธยา')
    start_next_day = db.Column(db.Boolean, default=False)
    is_locked_interest = db.Column(db.Boolean, default=False)
    locked_interest_amount = db.Column(db.Float, default=0.0)

class PaymentHistory(db.Model):
    __tablename__ = 'payment_history'
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id'), nullable=True)
    payment_date = db.Column(db.Date, nullable=False, default=get_thai_today)
    pay_amount = db.Column(db.Float, default=0.0)
    fine_amount = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    interest_paid = db.Column(db.Float, default=0.0)
    principal_reduced = db.Column(db.Float, default=0.0)
    note = db.Column(db.String(255), nullable=True)
    admin_name = db.Column(db.String(100), nullable=True)
    receiving_account = db.Column(db.String(50), default='กรุงศรีอยุธยา')

    transaction = db.relationship('Transaction', backref=db.backref('histories', lazy=True, cascade='all, delete-orphan'))

class BankAdjustment(db.Model):
    __tablename__ = 'bank_adjustment'
    id = db.Column(db.Integer, primary_key=True)
    account_name = db.Column(db.String(50), unique=True, nullable=False)
    adjustment_amount = db.Column(db.Float, default=0.0)

class BankExpenseLog(db.Model):
    __tablename__ = 'bank_expense_log'
    id = db.Column(db.Integer, primary_key=True)
    expense_date = db.Column(db.Date, nullable=False, default=get_thai_today)
    account_name = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    note = db.Column(db.String(255), nullable=True)
    admin_name = db.Column(db.String(100), nullable=True)

with app.app_context():
    db.create_all()

BASE_LAYOUT = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <title>{{ title }} - ทรัพย์ล้น</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Prompt', sans-serif; background-color: #fcf6f0; }
        .sidebar { width: 260px; min-height: 100vh; background: #2c0b0e; border-right: 2px solid #d4af37; position: fixed; top: 0; left: 0; z-index: 1050; transition: transform 0.3s ease-in-out; overflow-y: auto; color: #f8f9fa; }
        .main-content { margin-left: 260px; padding: 25px; transition: margin 0.3s ease-in-out; }
        .nav-link { color: #f1d3b2; font-weight: 500; padding: 10px 15px; border-radius: 6px; margin-bottom: 4px; font-size: 0.95rem; white-space: nowrap; }
        .nav-link:hover, .nav-link.active { background-color: #d4af37; color: #2c0b0e; font-weight: 600; }
        .sub-menu { padding-left: 25px; font-size: 0.9rem; color: #dfb182; }

        .mobile-header { display: none; background: #2c0b0e; border-bottom: 2px solid #d4af37; color: #fff; padding: 12px 15px; position: sticky; top: 0; z-index: 1040; }
        .sidebar-backdrop { display: none; position: fixed; top: 0; left: 0; width: 100vw; height: 100vh; background: rgba(0,0,0,0.5); z-index: 1045; }

        .btn-warning { background-color: #d4af37; border-color: #d4af37; color: #2c0b0e; font-weight: 600; }
        .btn-warning:hover { background-color: #b38f27; border-color: #b38f27; color: #fff; }
        .btn-success-light { background-color: #28a745; border-color: #28a745; color: #fff; font-weight: 600; }
        .btn-success-light:hover { background-color: #218838; border-color: #1e7e34; color: #fff; }

        .modal-dialog { max-height: 90vh; margin: 1.5vh auto; }
        .modal-dialog-scrollable .modal-content { max-height: 88vh; display: flex; flex-direction: column; }
        .modal-body { overflow-y: auto; flex: 1 1 auto; padding: 10px 14px !important; }

        .table-scroll-container { max-height: 600px; overflow-y: auto; position: relative; }
        .table-scroll-container thead th { position: sticky; top: 0; background-color: #212529 !important; color: #fff; z-index: 5; box-shadow: inset 0 -2px 0 rgba(0,0,0,0.2); }

        .table-responsive { overflow-x: auto; -webkit-overflow-scrolling: touch; }
        .table-responsive::-webkit-scrollbar { height: 8px; width: 8px; }
        .table-responsive::-webkit-scrollbar-track { background: #f1f1f1; border-radius: 6px; }
        .table-responsive::-webkit-scrollbar-thumb { background: #d4af37; border-radius: 6px; }

        @media (max-width: 768px) {
            .modal-dialog { margin: 8px; max-width: calc(100% - 16px); max-height: 94vh; }
            .modal-dialog-scrollable .modal-content { max-height: 92vh; }
        }

        @media (max-width: 992px) {
            .sidebar { transform: translateX(-100%); }
            .sidebar.show { transform: translateX(0); }
            .main-content { margin-left: 0; padding: 12px; }
            .mobile-header { display: flex; justify-content: space-between; align-items: center; }
            .sidebar-backdrop.show { display: block; }
        }
    </style>
</head>
<body>
    <div class="mobile-header shadow-sm">
        <div class="d-flex align-items-center gap-2">
            <button class="btn btn-outline-warning btn-sm" onclick="toggleSidebar()">☰ เมนู</button>
            <h5 class="text-warning fw-bold mb-0">🔱 ทรัพย์ล้น.com</h5>
        </div>
        <div class="d-flex align-items-center gap-2">
            <span class="badge bg-warning text-dark">{{ session.get('admin') }}</span>
            <a href="/logout" class="btn btn-outline-danger btn-sm">ออก</a>
        </div>
    </div>

    <div class="sidebar-backdrop" id="sidebarBackdrop" onclick="toggleSidebar()"></div>

    <div class="sidebar p-3 d-flex flex-column shadow" id="sidebarMenu">
        <div class="d-flex justify-content-between align-items-center mb-2">
            <h4 class="text-warning fw-bold d-none d-lg-block">🔱 ทรัพย์ล้น.com</h4>
            <h5 class="text-warning fw-bold d-lg-none">🔱 เมนูหลัก</h5>
            <button class="btn-close btn-close-white d-lg-none" onclick="toggleSidebar()"></button>
        </div>
        <div class="mb-3 px-2 d-none d-lg-block text-warning small border-bottom border-secondary pb-2">ผู้ใช้งาน: <b>{{ session.get('admin') }}</b></div>
        <ul class="nav nav-pills flex-column mb-auto">
            <li class="nav-item"><a href="/" class="nav-link {% if page == 'dashboard' %}active{% endif %}" onclick="toggleSidebar()">📊 Dashboard (รายการวันนี้)</a></li>
            <li><a href="/all_transactions" class="nav-link {% if page == 'all' %}active{% endif %}" onclick="toggleSidebar()">📋 รายการทั้งหมด</a></li>
            <li><a href="/members" class="nav-link {% if page == 'members' %}active{% endif %}" onclick="toggleSidebar()">👥 1. สมาชิกทั้งหมด</a></li>
            <li><a href="/sales_members" class="nav-link {% if page == 'sales' %}active{% endif %}" onclick="toggleSidebar()">📋 2. สมาชิกภายใต้เซลล์</a></li>
            <li><a href="/customer_summary" class="nav-link {% if page == 'customer' %}active{% endif %}" onclick="toggleSidebar()">📂 3. สรุปลูกค้า</a></li>
            <li><a href="/customer_emergency" class="nav-link sub-menu {% if page == 'emergency' %}active{% endif %}" onclick="toggleSidebar()">🔸 3.1 เงินฉุกเฉิน</a></li>
            <li><a href="/customer_gold" class="nav-link sub-menu {% if page == 'gold' %}active{% endif %}" onclick="toggleSidebar()">🔸 3.2 ผ่อนทอง</a></li>
            <li><a href="/customer_debt" class="nav-link sub-menu {% if page == 'debt' %}active{% endif %}" onclick="toggleSidebar()">🔸 3.3 ยอดค้างเก่า</a></li>
            <li><a href="/monthly_summary" class="nav-link sub-menu {% if page == 'monthly' %}active{% endif %}" onclick="toggleSidebar()">📅 4. สรุปยอดรายเดือน</a></li>
        </ul>
        <hr class="border-secondary">
        <div class="d-flex flex-column gap-2 mb-2">
            <a href="/check_orphaned_payments" class="btn btn-outline-danger btn-sm py-1 px-3 text-center rounded-pill" style="font-size: 0.78rem;">
                <span>🗑️ ตรวจสอบประวัติขยะ</span>
            </a>
            <a href="/export_data" class="btn btn-outline-warning btn-sm py-1 px-3 text-center rounded-pill" style="font-size: 0.78rem;">📥 สำรองข้อมูล (Backup)</a>
            <button type="button" class="btn btn-outline-info btn-sm py-1 px-3 text-center rounded-pill" style="font-size: 0.78rem;" data-bs-toggle="modal" data-bs-target="#importModal">📤 นำเข้าข้อมูล (Restore)</button>
        </div>
        <div class="d-flex flex-column gap-2">
            <a href="/logout" class="btn btn-outline-danger btn-sm w-100 d-none d-lg-block py-1 rounded-pill" style="font-size: 0.82rem;">ออกจากระบบ</a>
        </div>
    </div>

    <!-- Modal นำเข้าข้อมูล -->
    <div class="modal fade" id="importModal" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
            <div class="modal-content">
                <form action="/import_data" method="POST" enctype="multipart/form-data">
                    <div class="modal-header bg-info text-dark py-2">
                        <h5 class="modal-title fw-bold fs-6">📤 นำเข้าข้อมูลสำรอง (Restore CSV)</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p class="text-muted small">เลือกไฟล์ CSV ที่เคยสำรองข้อมูลไว้เพื่อดึงข้อมูลกลับเข้าสู่ระบบ</p>
                        <div class="mb-3"><input type="file" name="file" class="form-control form-control-sm" accept=".csv" required></div>
                    </div>
                    <div class="modal-footer py-2">
                        <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ยกเลิก</button>
                        <button type="submit" class="btn btn-info btn-sm fw-bold" onclick="return confirm('ยืนยันการนำเข้าข้อมูล?')">อัปโหลดและกู้คืน</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <div class="main-content">
        <h2 class="mb-4 text-danger fw-bold fs-4">{% block header %}{% endblock %}</h2>
        {% block content %}{% endblock %}
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
    function toggleSidebar() {
        const sidebar = document.getElementById('sidebarMenu');
        const backdrop = document.getElementById('sidebarBackdrop');
        sidebar.classList.toggle('show');
        backdrop.classList.toggle('show');
    }

    function togglePayInput(id) {
        let selectElem = document.getElementById('payType' + id);
        let amountContainer = document.getElementById('amountDiv' + id);
        let adjustContainer = document.getElementById('adjustContainer' + id);

        if (selectElem) {
            if (selectElem.value === 'full') {
                if(amountContainer) amountContainer.style.display = 'none';
                if(adjustContainer) adjustContainer.style.display = 'none';
            } else if (selectElem.value === 'adjust') {
                if(amountContainer) amountContainer.style.display = 'none';
                if(adjustContainer) adjustContainer.style.display = 'block';
            } else {
                if(amountContainer) amountContainer.style.display = 'block';
                if(adjustContainer) adjustContainer.style.display = 'none';
            }
        }
    }

    function handleTypeChange() {
        let typeVal = document.getElementById('txTypeSelect').value;
        let instDiv = document.getElementById('installmentDiv');
        if (typeVal === 'ยอดค้างเก่า') { instDiv.style.display = 'block'; } else { instDiv.style.display = 'none'; }
    }

    function handleScheduleChange() {
        let val = document.getElementById('scheduleTypeSelect').value;
        let dayDiv = document.getElementById('dueDayDiv');
        if (val === 'กำหนดจ่ายประจำเดือน') { dayDiv.style.display = 'block'; } else { dayDiv.style.display = 'none'; }
    }

    function toggleLockInterest() {
        let chk = document.getElementById('isLockedInterestAdd');
        let lockedBox = document.getElementById('lockedInterestBoxAdd');
        let lockedInput = document.getElementById('lockedInterestInput');

        let dailyBox = document.getElementById('dailyInterestBox');
        let dailyInput = document.getElementById('dailyInterestInput');

        if (chk && chk.checked) {
            lockedBox.style.display = 'block';
            if(lockedInput) lockedInput.required = true;

            dailyBox.style.display = 'none';
            if(dailyInput) {
                dailyInput.required = false;
                dailyInput.value = 0;
            }
        } else {
            lockedBox.style.display = 'none';
            if(lockedInput) {
                lockedInput.required = false;
                lockedInput.value = 0;
            }

            dailyBox.style.display = 'block';
            if(dailyInput) {
                dailyInput.required = true;
            }
        }
    }

    function closeAllModals() {
        document.querySelectorAll('.modal').forEach(modal => {
            let bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) { bsModal.hide(); }
        });
        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
        document.body.style.paddingRight = '';
    }

    function updateBillModalCalc(txId, baseAmt, dailyInt) {
        let isAdvance = document.getElementById('advanceChk' + txId).checked;
        let finalAmt = baseAmt;
        let displayTitle = "📄 ใบแจ้งยอดชำระ - ทรัพย์ล้น.com";

        if (isAdvance) {
            finalAmt += dailyInt;
            displayTitle = "ขออนุญาตแจ้งยอดชำระล่วงหน้า สำหรับวันพรุ่งนี้";
        }

        document.getElementById('billTotalDisplay' + txId).innerText = finalAmt.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' บาท';
        document.getElementById('billTitleDisplay' + txId).innerText = displayTitle;
    }

    function copyBillText(customerName, typeName, baseAmt, dailyInt, txId) {
        let isAdvance = document.getElementById('advanceChk' + txId).checked;
        let finalAmt = baseAmt;
        let titleHeader = "📄 ใบแจ้งยอดชำระ - ทรัพย์ล้น.com";
        let advanceNote = "";

        if (isAdvance) {
            finalAmt += dailyInt;
            titleHeader = "ขออนุญาตแจ้งยอดชำระล่วงหน้า สำหรับวันพรุ่งนี้";
            advanceNote = "พรุ่งนี้มีชำระ กรุณาเตรียมเงินตามยอดที่แจ้งด้วยนะครับ\n\n";
        }
        let formattedAmt = finalAmt.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' บาท';

        let textToCopy = `${titleHeader}\n` +
                         `👤 ลูกค้า: ${customerName}\n` +
                         `📋 ประเภท: ${typeName}\n` +
                         `${advanceNote}` +
                         `💰 ยอดที่ต้องชำระ: ${formattedAmt}\n\n` +
                         `📱 ช่องทางโอนเงิน / พร้อมเพย์:\n` +
                         `- กรุงศรีอยุธยา: 803-931-9819\n` +
                         `- ออมสิน: 020-409-437-819\n\n` +
                         `*โอนแล้วรบกวนส่งสลิปหลักฐานทางแชทนี้ได้เลยครับ ขอบคุณครับ 🙏`;

        navigator.clipboard.writeText(textToCopy).then(() => {
            alert('คัดลอกข้อความบิลเรียบร้อย! คุณสามารถกด วาง (Paste) ส่งให้ลูกค้าทาง Facebook ได้เลยครับ');
        }).catch(err => {
            alert('ไม่สามารถคัดลอกอัตโนมัติได้ กรุณาลองใหม่อีกครั้ง');
        });
    }

    function updateSelectedBillsCalc() {
        let checkboxes = document.querySelectorAll('.bill-checkbox:checked');
        let isAdvance = document.getElementById('selectedAdvanceChk').checked;

        let totalAmt = 0;
        let totalDailyInt = 0;

        checkboxes.forEach(chk => {
            totalAmt += parseFloat(chk.getAttribute('data-amount') || 0);
            totalDailyInt += parseFloat(chk.getAttribute('data-daily-int') || 0);
        });

        let finalTotal = totalAmt;
        let titleHeader = "📄 ใบแจ้งยอดชำระ - ทรัพย์ล้น.com";

        if (isAdvance) {
            finalTotal += totalDailyInt;
            titleHeader = "ขออนุญาตแจ้งยอดชำระล่วงหน้า สำหรับวันพรุ่งนี้";
        }

        document.getElementById('selectedBillsCount').innerText = checkboxes.length + ' บิล';
        document.getElementById('selectedBillsTotalAmount').innerText = finalTotal.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' บาท';
        document.getElementById('selectedBillTitleDisplay').innerText = titleHeader;
    }

    function openSelectedBillsModal() {
        let checkboxes = document.querySelectorAll('.bill-checkbox:checked');
        if (checkboxes.length === 0) {
            alert('กรุณาติ๊กเลือกอย่างน้อย 1 รายการที่ต้องการออกบิลรวมครับ');
            return;
        }
        document.getElementById('selectedAdvanceChk').checked = false;
        updateSelectedBillsCalc();

        let myModal = new bootstrap.Modal(document.getElementById('selectedBillsModal'));
        myModal.show();
    }

    function copySelectedBillsText(customerName) {
        let checkboxes = document.querySelectorAll('.bill-checkbox:checked');
        if (checkboxes.length === 0) {
            alert('กรุณาติ๊กเลือกรายการก่อนครับ');
            return;
        }
        let isAdvance = document.getElementById('selectedAdvanceChk').checked;
        let totalAmt = 0;
        let totalDailyInt = 0;
        let typesSet = new Set();

        checkboxes.forEach(chk => {
            totalAmt += parseFloat(chk.getAttribute('data-amount') || 0);
            totalDailyInt += parseFloat(chk.getAttribute('data-daily-int') || 0);
            let tName = chk.getAttribute('data-type');
            if (tName) typesSet.add(tName);
        });

        let finalTotal = totalAmt;
        let titleHeader = "📄 ใบแจ้งยอดชำระ - ทรัพย์ล้น.com";
        let advanceNote = "";

        if (isAdvance) {
            finalTotal += totalDailyInt;
            titleHeader = "ขออนุญาตแจ้งยอดชำระล่วงหน้า สำหรับวันพรุ่งนี้";
            advanceNote = "พรุ่งนี้มีชำระ กรุณาเตรียมเงินตามยอดที่แจ้งด้วยนะครับ\n\n";
        }

        let formattedTotal = finalTotal.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2}) + ' บาท';
        let typesStr = Array.from(typesSet).join(', ');

        let textToCopy = `${titleHeader}\n` +
                         `👤 ลูกค้า: ${customerName}\n` +
                         `📋 ประเภท: ${typesStr} (${checkboxes.length} บิล)\n` +
                         `${advanceNote}` +
                         `💰 ยอดรวมสุทธิ: ${formattedTotal}\n\n` +
                         `📱 ช่องทางโอนเงิน / พร้อมเพย์:\n` +
                         `- กรุงศรีอยุธยา: 803-931-9819\n` +
                         `- ออมสิน: 020-409-437-819\n\n` +
                         `*โอนแล้วรบกวนส่งสลิปหลักฐานทางแชทนี้ได้เลยครับ ขอบคุณครับ 🙏`;

        navigator.clipboard.writeText(textToCopy).then(() => {
            alert('คัดลอกข้อความบิลรวมเรียบร้อย! กด วาง (Paste) ส่งให้ลูกค้าได้ทันทีครับ');
        });
    }
    </script>
</body>
</html>
"""

def calculate_tx_values(tx):
    thai_today = get_thai_today()

    tx_start_date = tx.start_date
    if isinstance(tx_start_date, str):
        try:
            tx_start_date = datetime.strptime(tx_start_date.split()[0], '%Y-%m-%d').date()
        except:
            tx_start_date = thai_today
    elif not tx_start_date:
        tx_start_date = thai_today

    tx_last_pay = tx.last_payment_date
    if isinstance(tx_last_pay, str):
        try:
            tx_last_pay = datetime.strptime(tx_last_pay.split()[0], '%Y-%m-%d').date()
        except:
            tx_last_pay = None

    tx_closed_date = tx.closed_date
    if isinstance(tx_closed_date, str):
        try:
            tx_closed_date = datetime.strptime(tx_closed_date.split()[0], '%Y-%m-%d').date()
        except:
            tx_closed_date = None

    end_date = tx_closed_date if tx_closed_date else thai_today

    start_calc_date = tx_last_pay if tx_last_pay else tx_start_date
    days = (end_date - start_calc_date).days

    if not tx_last_pay and not tx.start_next_day:
        days += 1

    if days < 0: days = 0
    tx.days_passed_val = days

    if tx.original_principal > 0 and tx.initial_daily_interest > 0:
        current_daily_interest = tx.initial_daily_interest * (tx.principal / tx.original_principal)
        tx.daily_interest = current_daily_interest
    else:
        tx.daily_interest = tx.initial_daily_interest if tx.initial_daily_interest > 0 else tx.daily_interest

    if getattr(tx, 'is_locked_interest', False):
        acc = tx.locked_interest_amount - tx.paid_interest
    else:
        acc = (tx.daily_interest * days) - tx.paid_interest

    tx.accumulated_interest = acc if acc > 0 else 0.0

    sum_history_pay = 0.0
    sum_interest_paid = 0.0
    sum_principal_reduced = 0.0
    if tx.histories:
        for h in tx.histories:
            sum_principal_reduced += h.principal_reduced
            sum_interest_paid += h.interest_paid
            sum_history_pay += h.pay_amount if h.pay_amount > 0 else (h.interest_paid + h.principal_reduced)

    if tx.type == 'ยอดค้างเก่า':
        tx.total_paid = sum_history_pay if sum_history_pay > 0 else max(0.0, tx.original_principal - tx.principal)
    else:
        fallback_principal_reduced = max(0.0, tx.original_principal - tx.principal)
        actual_prin_reduced = sum_principal_reduced if sum_principal_reduced > 0 else fallback_principal_reduced
        calculated_paid_total = sum_interest_paid + actual_prin_reduced
        if calculated_paid_total <= 0:
            calculated_paid_total = tx.paid_interest + fallback_principal_reduced
        tx.total_paid = max(sum_history_pay, calculated_paid_total)

@app.route('/')
def root_index():
    if 'admin' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('index'))

@app.route('/dashboard', methods=['GET', 'POST'])
def index():
    if 'admin' not in session: return redirect(url_for('login'))

    if request.method == 'POST':
        try:
            p_val = float(request.form.get('principal', 0))
            custom_start_date = request.form.get('start_date')
            parsed_date = datetime.strptime(custom_start_date, '%Y-%m-%d').date() if custom_start_date else get_thai_today()
            current_sales = session.get('admin', 'unknown')
            d_interest = float(request.form.get('daily_interest', 0))
            tx_type = request.form.get('type')
            funding_source = request.form.get('funding_source', 'กรุงศรีอยุธยา')
            start_next_day_val = True if request.form.get('start_next_day') == 'on' else False

            is_locked_interest_val = True if request.form.get('is_locked_interest') == 'on' else False
            locked_interest_amt = float(request.form.get('locked_interest_amount', 0)) if is_locked_interest_val else 0.0

            schedule_type = request.form.get('schedule_type', 'จ่ายทุกวัน')
            selected_due_days = request.form.getlist('due_day_of_month') if schedule_type == 'กำหนดจ่ายประจำเดือน' else []
            due_day_str = ",".join(selected_due_days) if selected_due_days else None

            inst_amt = 0.0
            if tx_type == 'ยอดค้างเก่า': inst_amt = float(request.form.get('installment_amount', 0))

            new_tx = Transaction(
                type=tx_type, customer_name=request.form.get('customer_name'), phone=request.form.get('phone'),
                sales_name=current_sales, start_date=parsed_date, original_principal=p_val, principal=p_val,
                daily_interest=d_interest, initial_daily_interest=d_interest, installment_amount=inst_amt,
                schedule_type=schedule_type, due_day_of_month=due_day_str, status='ปกติ',
                funding_source=funding_source, start_next_day=start_next_day_val,
                is_locked_interest=is_locked_interest_val,
                locked_interest_amount=locked_interest_amt
            )
            db.session.add(new_tx)

            if p_val > 0 and funding_source in ['กรุงศรีอยุธยา', 'ออมสิน', 'วอลเล็ท']:
                adj = BankAdjustment.query.filter_by(account_name=funding_source).first()
                if adj:
                    adj.adjustment_amount = max(0.0, adj.adjustment_amount - p_val)
                else:
                    db.session.add(BankAdjustment(account_name=funding_source, adjustment_amount=0.0))

                db.session.add(BankExpenseLog(
                    expense_date=parsed_date,
                    account_name=funding_source,
                    amount=p_val,
                    note=f"ปล่อยกู้/เพิ่มทุนลูกค้า: {request.form.get('customer_name')}",
                    admin_name=current_sales
                ))

            db.session.commit()
            db.session.remove()
            return redirect(url_for('index'))
        except Exception as e: 
            print("Error:", e)
            db.session.rollback()
        return redirect(url_for('index'))

    search_query = request.args.get('search', '').strip()
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()
    thai_today = get_thai_today()
    today_day = thai_today.day
    current_year, current_month = thai_today.year, thai_today.month

    try:
        query = Transaction.query.filter(Transaction.principal > 0)
        if search_query:
            search_pattern = f"%{search_query}%"
            query = query.filter((Transaction.customer_name.ilike(search_pattern)) | (Transaction.phone.ilike(search_pattern)))

        if start_date_str and end_date_str:
            s_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            e_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter((Transaction.start_date >= s_date) & (Transaction.start_date <= e_date) | (Transaction.last_payment_date >= s_date) & (Transaction.last_payment_date <= e_date))
        elif start_date_str:
            target_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            query = query.filter((Transaction.start_date == target_date) | (Transaction.last_payment_date == target_date))
        elif not search_query:
            current_match_codes = []
            if 4 <= today_day <= 6: current_match_codes.append("6")
            if 9 <= today_day <= 12: current_match_codes.append("12")
            if 14 <= today_day <= 16: current_match_codes.append("16")
            if 20 <= today_day <= 23: current_match_codes.append("23")
            if 24 <= today_day <= 26: current_match_codes.append("26")
            if today_day >= 29 or today_day <= 2: current_match_codes.append("2")

            all_active_txs = Transaction.query.filter(Transaction.principal > 0).all()
            scheduled_today = []
            for t in all_active_txs:
                if t.schedule_type == 'กำหนดจ่ายประจำเดือน' and t.due_day_of_month:
                    saved_codes = t.due_day_of_month.split(',')
                    if any(code in current_match_codes for code in saved_codes):
                        scheduled_today.append(t)

            other_txs = Transaction.query.filter(
                Transaction.principal > 0,
                db.or_(
                    Transaction.schedule_type == 'จ่ายทุกวัน',
                    Transaction.start_date == thai_today,
                    Transaction.last_payment_date == thai_today
                )
            ).all()

            seen_ids = set()
            transactions = []
            for t in scheduled_today + other_txs:
                if t.id not in seen_ids:
                    seen_ids.add(t.id)
                    transactions.append(t)
        else:
            transactions = query.order_by(Transaction.customer_name.asc()).all()

        for tx in transactions:
            calculate_tx_values(tx)
            tx.days_passed = f"{tx.days_passed_val} วัน"

        all_txs_ever = Transaction.query.all()
        for tx in all_txs_ever: calculate_tx_values(tx)

        customer_active_counts = defaultdict(int)
        for t in all_txs_ever:
            if t.principal > 0 and t.customer_name:
                customer_active_counts[t.customer_name] += 1

        unique_customers = sorted(list(set(t.customer_name for t in all_txs_ever if t.customer_name)))
        datalist_options = "".join([f'<option value="{name}">' for name in unique_customers])

        total_new_investment = sum(tx.original_principal for tx in all_txs_ever if tx.type != 'ยอดค้างเก่า' and tx.start_date and tx.start_date.year == current_year and tx.start_date.month == current_month)

        total_debt_principal = sum(tx.principal for tx in all_txs_ever if tx.type == 'ยอดค้างเก่า')
        total_new_principal = sum(tx.principal for tx in all_txs_ever if tx.type != 'ยอดค้างเก่า' and tx.principal > 0)

        today_new_txs = [tx for tx in all_txs_ever if tx.start_date == thai_today]
        today_new_count = len(today_new_txs)

        today_histories = PaymentHistory.query.filter_by(payment_date=thai_today).all()
        today_collected_cash = sum((h.pay_amount if h.pay_amount > 0 else (h.interest_paid + h.principal_reduced + h.fine_amount - h.discount_amount)) for h in today_histories)

        today_payment_count = len(today_histories)
        total_today_actions = today_new_count + today_payment_count

        account_balances = {
            'กรุงศรีอยุธยา': 0.0,
            'ออมสิน': 0.0,
            'วอลเล็ท': 0.0
        }

        adjustments = BankAdjustment.query.all()
        adj_dict = {adj.account_name: adj.adjustment_amount for adj in adjustments}

        for acc_name in account_balances.keys():
            account_balances[acc_name] = adj_dict.get(acc_name, 0.0)

        expense_logs = BankExpenseLog.query.order_by(BankExpenseLog.expense_date.desc(), BankExpenseLog.id.desc()).all()
        expense_rows = "".join([f"<tr><td>{e.expense_date.strftime('%d/%m/%Y')}</td><td><span class='badge bg-warning text-dark'>{e.account_name}</span></td><td class='text-danger fw-bold'>-{e.amount:,.2f}</td><td>{e.note or '-'}</td><td><span class='badge bg-secondary'>{e.admin_name or '-'}</span></td><td><a href='/delete_expense/{e.id}' class='btn btn-sm btn-danger py-0 px-2' onclick=\"return confirm('ยืนยันลบประวัติการถอนนี้?')\">ลบ</a></td></tr>" for e in expense_logs])

        today_new_rows = ""
        for tx in today_new_txs:
            today_new_rows += f"""
            <tr>
                <td><a href="/customer_details/{tx.customer_name}" class="text-dark fw-bold text-decoration-none">{tx.customer_name}</a></td>
                <td><span class="badge bg-secondary">{tx.type}</span></td>
                <td>{tx.phone or '-'}</td>
                <td class="text-primary fw-bold">{tx.original_principal:,.2f}</td>
                <td><span class="badge bg-warning text-dark">{tx.funding_source or 'กรุงศรีอยุธยา'}</span></td>
                <td><span class="badge bg-danger">{tx.sales_name}</span></td>
            </tr>
            """

        today_history_rows = ""
        for h in today_histories:
            tx_ref = h.transaction
            cust_display = tx_ref.customer_name if tx_ref else "ไม่พบชื่อบัญชี"
            display_pay = h.pay_amount if h.pay_amount > 0 else (h.interest_paid + h.principal_reduced + h.fine_amount - h.discount_amount)
            if display_pay < 0: display_pay = 0.0

            today_history_rows += f"""
            <tr>
                <td><a href="/customer_details/{cust_display}" class="text-dark fw-bold text-decoration-none">{cust_display}</a></td>
                <td class="text-success fw-bold">{display_pay:,.2f}</td>
                <td><span class="badge bg-info text-dark">{h.receiving_account or 'กรุงศรีอยุธยา'}</span></td>
                <td>{h.fine_amount:,.2f}</td>
                <td>{h.discount_amount:,.2f}</td>
                <td>{h.interest_paid:,.2f}</td>
                <td>{h.principal_reduced:,.2f}</td>
                <td>{h.note or '-'}</td>
                <td><span class="badge bg-secondary">{h.admin_name or '-'}</span></td>
            </tr>
            """

        debt_card_txs = [tx for tx in all_txs_ever if tx.type == 'ยอดค้างเก่า' and tx.principal > 0]
        debt_card_rows = "".join([f"<tr><td><a href='/customer_details/{tx.customer_name}' class='text-dark fw-bold text-decoration-none'>{tx.customer_name}</a></td><td>{tx.phone or '-'}</td><td>{tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'}</td><td>{tx.original_principal:,.2f}</td><td class='text-danger fw-bold'>{tx.principal:,.2f}</td></tr>" for tx in debt_card_txs])

        new_principal_txs = [tx for tx in all_txs_ever if tx.type != 'ยอดค้างเก่า' and tx.principal > 0]
        new_principal_rows = "".join([f"<tr><td><a href='/customer_details/{tx.customer_name}' class='text-dark fw-bold text-decoration-none'>{tx.customer_name}</a></td><td><span class='badge bg-secondary'>{tx.type}</span></td><td>{tx.phone or '-'}</td><td>{tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'}</td><td>{tx.original_principal:,.2f}</td><td class='text-danger fw-bold'>{tx.principal:,.2f}</td></tr>" for tx in new_principal_txs])

        current_month_profit = 0.0
        all_histories_for_dash = PaymentHistory.query.all()
        tx_profit_map = defaultdict(lambda: {'net_earned': 0.0, 'fine': 0.0, 'discount': 0.0, 'latest_date': None})

        for h in all_histories_for_dash:
            if h.payment_date and h.payment_date.year == current_year and h.payment_date.month == current_month:
                if h.transaction_id and h.transaction:
                    earned = h.principal_reduced + h.interest_paid if h.transaction.type == 'ยอดค้างเก่า' else h.interest_paid
                    h_profit = earned + h.fine_amount 
                    current_month_profit += h_profit

                    tx_profit_map[h.transaction_id]['net_earned'] += earned
                    tx_profit_map[h.transaction_id]['fine'] += h.fine_amount
                    tx_profit_map[h.transaction_id]['discount'] += h.discount_amount
                    if not tx_profit_map[h.transaction_id]['latest_date'] or h.payment_date > tx_profit_map[h.transaction_id]['latest_date']:
                        tx_profit_map[h.transaction_id]['latest_date'] = h.payment_date

        profit_items = []
        for tx_id, p_data in tx_profit_map.items():
            tx_ref = Transaction.query.get(tx_id)
            if tx_ref:
                total_item_profit = p_data['net_earned'] + p_data['fine']
                profit_items.append({
                    'customer_name': tx_ref.customer_name,
                    'type': tx_ref.type,
                    'net_earned': p_data['net_earned'],
                    'fine_amount': p_data['fine'],
                    'discount_amount': p_data['discount'],
                    'total_item_profit': total_item_profit,
                    'latest_date': p_data['latest_date']
                })

        profit_items.sort(key=lambda x: x['latest_date'] if x['latest_date'] else thai_today, reverse=True)

        profit_card_rows = ""
        for item in profit_items:
            profit_card_rows += f"""
            <tr>
                <td><a href="/customer_details/{item['customer_name']}" class="text-dark fw-bold text-decoration-none">{item['customer_name']}</a></td>
                <td><span class="badge bg-secondary">{item['type']}</span></td>
                <td class="text-success fw-bold">{item['net_earned']:,.2f} บาท</td>
                <td class="text-warning text-dark fw-bold">{item['fine_amount']:,.2f} บาท</td>
                <td class="text-danger fw-bold">-{item['discount_amount']:,.2f} บาท</td>
                <td class="text-primary fw-bold">{item['total_item_profit']:,.2f} บาท</td>
                <td><small class="text-muted">{item['latest_date'].strftime('%d/%m/%Y') if item['latest_date'] else '-'}</small></td>
            </tr>
            """

        sum_modal_actual_profit = sum(item['total_item_profit'] for item in profit_items)

        profit_card_rows += f"""
        <tr class="table-warning fw-bold">
            <td colspan="5" class="text-end">รวมกำไรสะสมทั้งระบบ (อิงจากยอดจริง):</td>
            <td colspan="2" class="text-success">{sum_modal_actual_profit:,.2f} บาท</td>
        </tr>
        """

        rows, modals_html = "", ""
        for tx in transactions:
            badge_color = 'bg-success'
            if tx.status == 'ตัดยอดบางส่วน': badge_color = 'bg-info text-dark'
            elif tx.status == 'คืนแล้ว': badge_color = 'bg-danger'

            start_date_str = tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'
            last_pay_str = tx.last_payment_date.strftime('%d/%m/%Y') if tx.last_payment_date else '-'
            closed_date_str = tx.closed_date.strftime('%Y-%m-%d') if tx.closed_date else ''

            schedule_badge = f'<span class="badge bg-dark">{tx.schedule_type}</span>'
            if tx.schedule_type == 'กำหนดจ่ายประจำเดือน' and tx.due_day_of_month:
                code_map = {"2": "29-2", "6": "4-6", "12": "9-12", "16": "14-16", "23": "20-23", "26": "24-26"}
                labels = [code_map.get(c, c) for c in tx.due_day_of_month.split(',')]
                schedule_badge = f'<span class="badge bg-primary">รอบ: {", ".join(labels)}</span>'

            active_cnt = customer_active_counts.get(tx.customer_name, 1)
            count_badge = f' <a href="/customer_details/{tx.customer_name}" class="badge bg-danger text-decoration-none" title="คลิกเพื่อดูทุกรายการของลูกค้ารายนี้">🔥 {active_cnt} รายการ</a>'

            rows += f"""
            <tr>
                <td style="position: sticky; left: 0; background-color: #fff; z-index: 2; font-weight: 500; box-shadow: 2px 0 5px rgba(0,0,0,0.05);">
                    <a href="/customer_details/{tx.customer_name}" class="text-dark fw-bold text-decoration-none">{tx.customer_name}</a>{count_badge}
                </td>
                <td>{tx.phone or '-'}</td>
                <td><span class="badge bg-secondary">{tx.type}</span> {schedule_badge}</td>
                <td><span class="badge bg-warning text-dark">{tx.funding_source or 'กรุงศรีอยุธยา'}</span></td>
                <td>{start_date_str}</td>
                <td>{last_pay_str}</td>
                <td>{tx.original_principal:,.2f}</td>
                <td>{tx.principal:,.2f}</td>
                <td><strong class="text-primary">{tx.total_paid:,.2f}</strong></td>
                <td>{tx.daily_interest:,.2f}</td>
                <td>{tx.days_passed}</td>
                <td>{tx.accumulated_interest:,.2f}</td>
                <td><span class="badge {badge_color}">{tx.status}</span></td>
                <td style="position: sticky; right: 0; background-color: #fff; z-index: 2; text-align: center; box-shadow: -2px 0 5px rgba(0,0,0,0.05);">
                    <div class="d-flex flex-column gap-2" style="width: 90px; margin: 0 auto;">
                        <button type="button" class="btn btn-sm btn-success-light w-100" data-bs-toggle="modal" data-bs-target="#payModal{tx.id}">จัดการยอด</button>
                        <a href="/delete_tx/{tx.id}" class="btn btn-sm btn-danger w-100" onclick="return confirm('ยืนยันการลบ?')">ลบ</a>
                    </div>
                </td>
            </tr>
            """

            modals_html += f"""
            <div class="modal fade" id="payModal{tx.id}" tabindex="-1">
                <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
                    <div class="modal-content border-warning">
                        <form action="/update_payment/{tx.id}" method="POST">
                            <div class="modal-header bg-danger text-white py-2">
                                <h5 class="modal-title fs-6">จัดการยอด: {tx.customer_name}</h5>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body py-2">
                                <div class="p-2 mb-2 bg-light rounded border d-flex justify-content-between align-items-center">
                                    <div><small class="text-muted d-block" style="font-size: 0.75rem;">เงินต้นคงเหลือ</small><b>{tx.principal:,.2f} บาท</b></div>
                                    <div class="text-end"><small class="text-muted d-block" style="font-size: 0.75rem;">ดอกเบี้ยสะสม</small><b class="text-danger">{tx.accumulated_interest:,.2f} บาท</b></div>
                                </div>
                                <div class="mb-2 p-2 bg-warning bg-opacity-10 rounded border border-warning">
                                    <label class="form-label text-dark fw-bold mb-1" style="font-size: 0.85rem;">📅 วันที่ปิดยอด / วันที่คืนยอด</label>
                                    <input type="date" name="closed_date" class="form-control form-control-sm border-warning bg-white" value="{closed_date_str}">
                                </div>

                                <div class="mb-2 p-2 bg-success bg-opacity-10 rounded border border-success">
                                    <label class="form-label text-success fw-bold mb-1" style="font-size: 0.85rem;">📥 ลูกค้าโอนเข้าบัญชี / ช่องทางไหน:</label>
                                    <select name="receiving_account" class="form-select form-select-sm border-success">
                                        <option value="กรุงศรีอยุธยา">🟢 กรุงศรีอยุธยา (803-931-9819)</option>
                                        <option value="ออมสิน">🩷 ออมสิน (020-409-437-819)</option>
                                        <option value="วอลเล็ท">🟠 TrueMoney Wallet (092-923-7819)</option>
                                    </select>
                                </div>

                                <div class="p-2 mb-2 rounded border border-primary bg-primary bg-opacity-10">
                                    <div class="mb-2">
                                        <label class="form-label fw-bold text-primary mb-1" style="font-size: 0.85rem;">💳 เลือกประเภทการชำระ</label>
                                        <select name="payment_type" class="form-select form-select-sm border-primary shadow-sm" id="payType{tx.id}" onchange="togglePayInput({tx.id})" required>
                                            <option value="" disabled selected>-- กรุณาเลือกประเภทการชำระ --</option>
                                            <option value="partial">จ่ายบางส่วน</option>
                                            <option value="full">คืนครบทั้งหมด</option>
                                            <option value="adjust">ปรับปรุงยอด (เพิ่ม/ลดต้นโดยไม่อ้างอิงเงินสด)</option>
                                        </select>
                                    </div>
                                    <div class="mb-1" id="amountDiv{tx.id}">
                                        <label class="form-label fw-bold text-primary mb-1" style="font-size: 0.85rem;">💵 จำนวนเงินที่รับชำระจริง (บาท)</label>
                                        <input type="number" step="any" name="pay_amount" class="form-control form-control-sm border-primary shadow-sm bg-white" placeholder="กรอกจำนวนเงินสดที่รับจริง">
                                    </div>

                                    <div class="mb-1" id="adjustContainer{tx.id}" style="display: none;">
                                        <label class="form-label fw-bold text-dark mb-1" style="font-size: 0.85rem;">⚙ จำนวนเงินปรับปรุงต้น (บาท)</label>
                                        <input type="number" step="any" name="adjust_amount" class="form-control form-control-sm mb-1" placeholder="เช่น 500 หรือ -200">
                                    </div>
                                </div>

                                <div class="row g-2 mb-2">
                                    <div class="col-6"><label class="form-label text-danger small fw-bold mb-1">ส่วนลด</label><input type="number" step="any" name="discount_amount" class="form-control form-control-sm" value="0"></div>
                                    <div class="col-6"><label class="form-label text-warning text-dark small fw-bold mb-1">ค่าปรับ</label><input type="number" step="any" name="fine_amount" class="form-control form-control-sm" value="0"></div>
                                </div>
                                <div class="mb-1"><label class="form-label text-dark fw-bold mb-1">หมายเหตุ</label><input type="text" name="note" class="form-control form-control-sm"></div>
                            </div>
                            <div class="modal-footer bg-light py-2 justify-content-between">
                                <a href="/history/{tx.id}" class="btn btn-outline-info btn-sm" target="_blank">📜 ประวัติ</a>
                                <div>
                                    <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ยกเลิก</button>
                                    <button type="submit" class="btn btn-success-light btn-sm fw-bold px-3" onclick="closeAllModals()">บันทึก</button>
                                </div>
                            </div>
                        </form>
                    </div>
                </div>
            </div>
            """

        if start_date_str and end_date_str:
            table_title = f"📋 รายการช่วงวันที่: {start_date_str} ถึง {end_date_str}"
            view_today_btn = '<a href="/" class="btn btn-sm btn-success fw-bold">🟢 แสดงรายการแจ้งเตือนวันนี้</a>'
        elif start_date_str:
            table_title = f"📋 รายการความเคลื่อนไหววันที่: {start_date_str}"
            view_today_btn = '<a href="/" class="btn btn-sm btn-success fw-bold">🟢 แสดงรายการแจ้งเตือนวันนี้</a>'
        elif search_query:
            table_title = f'📋 ผลการค้นหา: "{search_query}"'
            view_today_btn = '<a href="/" class="btn btn-sm btn-success fw-bold">🟢 แสดงรายการแจ้งเตือนวันนี้</a>'
        else:
            table_title = f"🔔 รายการที่ต้องทวงวันนี้ (ประจำวันที่ {today_day})"
            view_today_btn = '<a href="/all_transactions" class="btn btn-sm btn-outline-danger fw-bold">📂 ดูรายการทั้งหมด</a>'

        content = f"""
        <div class="row mb-4">
            <div class="col-md-3 mb-3 mb-md-0">
                <div class="card p-3 shadow-sm text-white h-100" style="background: linear-gradient(135deg, #d97706, #f59e0b); cursor: pointer;" data-bs-toggle="modal" data-bs-target="#debtModal">
                    <div style="font-size: 0.9rem;" class="mb-1">📂 ยอดค้างเก่าคงเหลือ</div>
                    <h5 class="fw-bold mb-0">{total_debt_principal:,.2f} บ.</h5>
                </div>
            </div>
            <div class="col-md-3 mb-3 mb-md-0">
                <div class="card p-3 shadow-sm text-white h-100" style="background: linear-gradient(135deg, #b30000, #ff4d4d); cursor: pointer;" data-bs-toggle="modal" data-bs-target="#principalModal">
                    <div style="font-size: 0.9rem;" class="mb-1">💼 เงินต้นคงค้าง</div>
                    <h5 class="fw-bold mb-0">{total_new_principal:,.2f} บ.</h5>
                </div>
            </div>
            <div class="col-md-3 mb-3 mb-md-0">
                <div class="card p-3 shadow-sm text-white h-100" style="background: linear-gradient(135deg, #004d99, #3399ff);">
                    <div style="font-size: 0.9rem;" class="mb-1">🔱 เงินลงทุนใหม่ (เดือนนี้)</div>
                    <h5 class="fw-bold mb-0">{total_new_investment:,.2f} บ.</h5>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card p-3 shadow-sm text-white h-100" style="background: linear-gradient(135deg, #006622, #00b33c); cursor: pointer;" data-bs-toggle="modal" data-bs-target="#profitModal">
                    <div style="font-size: 0.9rem;" class="mb-1">💰 กำไรสะสม (เดือนนี้)</div>
                    <h5 class="fw-bold mb-0">{current_month_profit:,.2f} บ.</h5>
                </div>
            </div>
        </div>

        <div class="card p-3 mb-4 shadow-sm border-warning bg-white">
            <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
                <h5 class="text-danger fw-bold mb-0">🏦 สถานะกระเป๋าเงินจริงในมือถือ</h5>
                <div class="d-flex gap-2 flex-wrap">
                    <button type="button" class="btn btn-outline-primary btn-sm fw-bold" data-bs-toggle="modal" data-bs-target="#transferBankModal">🔄 โยกเงิน</button>
                    <button type="button" class="btn btn-outline-danger btn-sm fw-bold" data-bs-toggle="modal" data-bs-target="#adjustBankModal">⚙ ตั้งค่า/ปรับยอด</button>
                    <button type="button" class="btn btn-danger btn-sm fw-bold" data-bs-toggle="modal" data-bs-target="#withdrawModal">💸 ถอนเงินออก</button>
                </div>
            </div>
            <div class="row g-3">
                <div class="col-md-4">
                    <div class="p-3 rounded border border-warning bg-warning bg-opacity-15">
                        <h6 class="text-dark fw-bold mb-1">🟡 กรุงศรีอยุธยา</h6>
                        <small class="text-muted d-block mb-1">803-xxx-9819</small>
                        <h3 class="text-dark fw-bold mb-0">{account_balances['กรุงศรีอยุธยา']:,.2f} บาท</h3>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="p-3 rounded border border-danger bg-danger bg-opacity-10">
                        <h6 class="text-danger fw-bold mb-1">🩷 ออมสิน</h6>
                        <small class="text-muted d-block mb-1">020-xxx-437-819</small>
                        <h3 class="text-danger fw-bold mb-0">{account_balances['ออมสิน']:,.2f} บาท</h3>
                    </div>
                </div>
                <div class="col-md-4">
                    <div class="p-3 rounded border border-info bg-info bg-opacity-10">
                        <h6 class="text-dark fw-bold mb-1">🟠 TrueMoney Wallet</h6>
                        <small class="text-muted d-block mb-1">092-xxx-7819</small>
                        <h3 class="text-dark fw-bold mb-0">{account_balances['วอลเล็ท']:,.2f} บาท</h3>
                    </div>
                </div>
            </div>

            <div class="mt-3 pt-3 border-top">
                <button class="btn btn-outline-secondary btn-sm mb-2" type="button" data-bs-toggle="collapse" data-bs-target="#expenseLogCollapse">
                    📜 ดูประวัติการโยกเงิน / ถอนเงิน / ค่าใช้จ่าย (คลิกเพื่อเปิด/ปิด)
                </button>
                <div class="collapse" id="expenseLogCollapse">
                    <div class="table-responsive bg-light p-2 rounded">
                        <table class="table table-sm table-striped align-middle text-nowrap mb-0">
                            <thead>
                                <tr><th>วันที่</th><th>บัญชี</th><th>จำนวนเงิน</th><th>หมายเหตุ</th><th>ผู้ทำรายการ</th><th>จัดการ</th></tr>
                            </thead>
                            <tbody>
                                {expense_rows if expense_rows else "<tr><td colspan='6' class='text-center text-muted'>ยังไม่มีประวัติการโยก/ถอนเงินออก</td></tr>"}
                            </tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>

        <div class="modal fade" id="transferBankModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
                <div class="modal-content border-primary">
                    <form action="/transfer_bank_money" method="POST">
                        <div class="modal-header bg-primary text-white py-2">
                            <h5 class="modal-title fw-bold fs-6">🔄 โยกเงินระหว่างบัญชี</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <label class="form-label fw-bold text-danger">📤 จากบัญชีต้นทาง</label>
                                <select name="from_account" class="form-select border-danger" required>
                                    <option value="กรุงศรีอยุธยา">🟡 กรุงศรีอยุธยา (803-931-9819)</option>
                                    <option value="ออมสิน">🩷 ออมสิน (020-409-437-819)</option>
                                    <option value="วอลเล็ท">🟠 TrueMoney Wallet (092-923-7819)</option>
                                </select>
                            </div>
                            <div class="mb-3">
                                <label class="form-label fw-bold text-success">📥 ไปยังบัญชีปลายทาง</label>
                                <select name="to_account" class="form-select border-success" required>
                                    <option value="ออมสิน">🩷 ออมสิน (020-409-437-819)</option>
                                    <option value="กรุงศรีอยุธยา">🟡 กรุงศรีอยุธยา (803-931-9819)</option>
                                    <option value="วอลเล็ท">🟠 TrueMoney Wallet (092-923-7819)</option>
                                </select>
                            </div>
                            <div class="mb-3">
                                <label class="form-label fw-bold text-primary">💵 จำนวนเงินที่ต้องการโยก (บาท)</label>
                                <input type="number" step="any" name="transfer_amount" class="form-control" placeholder="เช่น 10000" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label fw-bold text-dark">📝 หมายเหตุ</label>
                                <input type="text" name="note" class="form-control" placeholder="เช่น โยกไปพักไว้บัญชีออมสิน" required>
                            </div>
                        </div>
                        <div class="modal-footer py-2">
                            <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ยกเลิก</button>
                            <button type="submit" class="btn btn-primary btn-sm fw-bold px-3">ยืนยันการโยกเงิน</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>

        <div class="modal fade" id="adjustBankModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
                <div class="modal-content border-danger">
                    <form action="/update_bank_adjustment" method="POST">
                        <div class="modal-header bg-danger text-white py-2">
                            <h5 class="modal-title fw-bold fs-6">⚙ ตั้งค่าปรับยอดเงินตั้งต้นกระเป๋าจริง</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <label class="form-label fw-bold text-dark">🟡 กรุงศรีอยุธยา</label>
                                <input type="number" step="any" name="krungsri" class="form-control" value="{adj_dict.get('กรุงศรีอยุธยา', 0.0)}" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label fw-bold text-danger">🩷 ออมสิน</label>
                                <input type="number" step="any" name="gsb" class="form-control" value="{adj_dict.get('ออมสิน', 0.0)}" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label fw-bold text-primary">🟠 TrueMoney Wallet</label>
                                <input type="number" step="any" name="wallet" class="form-control" value="{adj_dict.get('วอลเล็ท', 0.0)}" required>
                            </div>
                        </div>
                        <div class="modal-footer py-2">
                            <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ยกเลิก</button>
                            <button type="submit" class="btn btn-danger btn-sm fw-bold px-3">บันทึกยอดตั้งต้น</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>

        <div class="modal fade" id="withdrawModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
                <div class="modal-content border-danger">
                    <form action="/withdraw_bank_money" method="POST">
                        <div class="modal-header bg-danger text-white py-2">
                            <h5 class="modal-title fw-bold fs-6">💸 ถอนเงินออกจากบัญชี</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <div class="mb-3">
                                <label class="form-label fw-bold text-success">💳 เลือกบัญชี</label>
                                <select name="account_name" class="form-select border-success" required>
                                    <option value="กรุงศรีอยุธยา">🟡 กรุงศรีอยุธยา (803-931-9819)</option>
                                    <option value="ออมสิน">🩷 ออมสิน (020-409-437-819)</option>
                                    <option value="วอลเล็ท">🟠 TrueMoney Wallet (092-923-7819)</option>
                                </select>
                            </div>
                            <div class="mb-3">
                                <label class="form-label fw-bold text-danger">💵 จำนวนเงินที่ถอนออก (บาท)</label>
                                <input type="number" step="any" name="withdraw_amount" class="form-control" placeholder="เช่น 5000" required>
                            </div>
                            <div class="mb-3">
                                <label class="form-label fw-bold text-dark">📝 หมายเหตุ</label>
                                <input type="text" name="note" class="form-control" placeholder="เช่น จ่ายเงินเดือนพนักงาน" required>
                            </div>
                        </div>
                        <div class="modal-footer py-2">
                            <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ยกเลิก</button>
                            <button type="submit" class="btn btn-danger btn-sm fw-bold px-3">ยืนยันการถอนเงิน</button>
                        </div>
                    </form>
                </div>
            </div>
        </div>

        <div class="card p-4 shadow-sm border-warning mb-4">
            <h4 class="mb-3 fs-5 text-danger fw-bold">➕ เพิ่มรายการใหม่ (ผู้ดูแล: <span class="text-dark">{session.get('admin')}</span>)</h4>
            <form method="POST" class="row g-3">
                <div class="col-md-3">
                    <label class="form-label">ประเภทรายการ</label>
                    <select name="type" class="form-select" id="txTypeSelect" onchange="handleTypeChange()" required>
                        <option value="เงินฉุกเฉิน">เงินฉุกเฉิน (ลูกค้าใหม่)</option>
                        <option value="ผ่อนทอง">ผ่อนทอง (ลูกค้าใหม่)</option>
                        <option value="ยอดค้างเก่า">ยอดค้างเก่า (ลูกค้าเก่า)</option>
                    </select>
                </div>
                <div class="col-md-3">
                    <label class="form-label">ชื่อลูกค้า</label>
                    <input type="text" name="customer_name" class="form-control" list="customerList" autocomplete="off" required>
                    <datalist id="customerList">{datalist_options}</datalist>
                </div>
                <div class="col-md-3">
                    <label class="form-label">เบอร์โทร</label>
                    <input type="text" name="phone" class="form-control" autocomplete="tel">
                </div>
                <div class="col-md-3">
                    <label class="form-label">วันที่กู้/วันที่เริ่ม</label>
                    <input type="date" name="start_date" class="form-control" value="{thai_today.strftime('%Y-%m-%d')}" required>
                </div>

                <div class="col-md-4">
                    <label class="form-label text-success fw-bold">💳 โอนเงินออกจากบัญชี / แหล่งทุน:</label>
                    <select name="funding_source" class="form-select border-success" required>
                        <option value="กรุงศรีอยุธยา">🟡 กรุงศรีอยุธยา (803-931-9819)</option>
                        <option value="ออมสิน">🩷 ออมสิน (020-409-437-819)</option>
                        <option value="วอลเล็ท">🟠 TrueMoney Wallet (092-923-7819)</option>
                    </select>
                </div>

                <div class="col-md-3">
                    <label class="form-label text-danger fw-bold">ประเภทกำหนดจ่าย</label>
                    <select name="schedule_type" class="form-select border-danger" id="scheduleTypeSelect" onchange="handleScheduleChange()" required>
                        <option value="จ่ายทุกวัน">จ่ายทุกวัน (ทวงทุกวัน)</option>
                        <option value="กำหนดจ่ายประจำเดือน">กำหนดจ่ายประจำเดือน (เลือกได้หลายรอบ)</option>
                        <option value="ยังไม่มีกำหนดจ่าย">ยังไม่มีกำหนดจ่าย</option>
                    </select>
                </div>
                <div class="col-md-5" id="dueDayDiv" style="display: none;">
                    <label class="form-label text-primary fw-bold">รอบช่วงวันที่ต้องจ่าย</label>
                    <div class="p-2 border rounded bg-white d-flex flex-wrap gap-3">
                        <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="2" id="chk_d2"><label class="form-check-label small" for="chk_d2">29-2</label></div>
                        <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="6" id="chk_d6"><label class="form-check-label small" for="chk_d6">4-6</label></div>
                        <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="12" id
