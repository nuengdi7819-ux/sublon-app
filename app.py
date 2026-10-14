from flask import Flask, render_template_string, request, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import os
import io
import csv

app = Flask(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxx.supabase.co:5432/postgres?sslmode=require')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL and DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'your_secret_key_sublon_2026'

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 180,
    "pool_size": 5,
    "max_overflow": 10,
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
    is_fixed_daily = db.Column(db.Boolean, default=False)

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
                <span>🗑 ตรวจสอบประวัติขยะ</span>
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

    function handleLockInterestChange() {
        let chk = document.getElementById('isLockedInterestAdd');
        let box = document.getElementById('lockedInterestBoxAdd');
        if (chk && box) {
            box.style.display = chk.checked ? 'block' : 'none';
        }
    }

    function handleModalLockInterestChange(txId) {
        let chk = document.getElementById('isLockedInterest' + txId);
        let box = document.getElementById('lockedInterestBox' + txId);
        if (chk && box) {
            box.style.display = chk.checked ? 'block' : 'none';
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
        let displayTitle = "ใบแจ้งยอดชำระ";
        
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
        let titleHeader = "ใบแจ้งยอดชำระ";
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
        let typesSet = new Set();
        
        checkboxes.forEach(chk => {
            totalAmt += parseFloat(chk.getAttribute('data-amount') || 0);
            totalDailyInt += parseFloat(chk.getAttribute('data-daily-int') || 0);
            let tName = chk.getAttribute('data-type');
            if (tName) typesSet.add(tName);
        });

        let finalTotal = totalAmt;
        let titleHeader = "ใบแจ้งยอดชำระรวม";
        
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
        let titleHeader = "ใบแจ้งยอดชำระรวม";
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
                         `*โอนแล้วรบกวนส่งสลิปทางแชทนี้ได้เลยครับ ขอบคุณครับ 🙏`;

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
    end_date = tx.closed_date if tx.closed_date else thai_today
    
    days = (end_date - tx.start_date).days + 1
    if tx.start_next_day:
        days -= 1
    if days < 0: days = 0
    tx.days_passed_val = days
    
    if tx.is_locked_interest:
        tx.daily_interest = 0.0
        acc = tx.locked_interest_amount - tx.paid_interest
    elif tx.is_fixed_daily:
        tx.daily_interest = tx.initial_daily_interest
        acc = (tx.daily_interest * days) - tx.paid_interest
    else:
        if tx.original_principal > 0 and tx.initial_daily_interest > 0:
            current_daily_interest = tx.initial_daily_interest * (tx.principal / tx.original_principal)
            tx.daily_interest = current_daily_interest
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
        tx.total_paid = sum_
