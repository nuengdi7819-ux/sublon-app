from flask import Flask, render_template_string, request, redirect, url_for, session, send_file
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import os
import io
import csv

app = Flask(__name__)

DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://postgres:[YOUR-PASSWORD]@db.xxxxxxx.supabase.co:5432/postgres')
if DATABASE_URL and DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'your_secret_key_sublon_2026_secure')

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
    "pool_size": 10,
    "max_overflow": 20,
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
    customer_name = db.Column(db.String(100), nullable=False, index=True)
    phone = db.Column(db.String(20), nullable=True)
    sales_name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False, default=get_thai_today)
    last_payment_date = db.Column(db.Date, nullable=True)
    closed_date = db.Column(db.Date, nullable=True)
    original_principal = db.Column(db.Float, nullable=False, default=0.0)
    principal = db.Column(db.Float, nullable=False, default=0.0)                     
    daily_interest = db.Column(db.Float, nullable=False, default=0.0)
    initial_daily_interest = db.Column(db.Float, nullable=False, default=0.0)
    paid_interest = db.Column(db.Float, default=0.0)     
    status = db.Column(db.String(20), default='ปกติ')
    installment_amount = db.Column(db.Float, default=0.0)
    schedule_type = db.Column(db.String(50), nullable=False, default='จ่ายทุกวัน') 
    due_day_of_month = db.Column(db.String(50), nullable=True)
    funding_source = db.Column(db.String(50), default='กรุงศรีอยุธยา')

class PaymentHistory(db.Model):
    __tablename__ = 'payment_history'
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('transactions.id', ondelete='CASCADE'), nullable=True)
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

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return f"""
    <div style="padding: 40px; font-family: Prompt, sans-serif; text-align: center;">
        <h2 style="color: #d9534f;">⚠️ เกิดข้อผิดพลาดภายในระบบ (Server Error)</h2>
        <p>ระบบได้ทำการตัดการเชื่อมต่อเพื่อความปลอดภัย กรุณากลับหน้าหลักครับ</p>
        <a href="/" style="background: #d4af37; color: #fff; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">กลับสู่หน้าหลัก</a>
    </div>
    """, 500

@app.errorhandler(404)
def not_found_error(error):
    return redirect(url_for('index'))

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
        .table-responsive { overflow-x: auto; -webkit-overflow-scrolling: touch; }
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
            <li><a href="/monthly_summary" class="nav-link sub-menu {% if page == 'monthly' %}active{% endif %}" onclick="toggleSidebar()">📁 4. กล่องแฟ้มรายเดือน</a></li>
        </ul>
        <hr class="border-secondary">
        <div class="d-flex flex-column gap-2">
            <a href="/logout" class="btn btn-outline-danger w-100">ออกจากระบบ</a>
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
        let statusElem = document.getElementById('newStatus' + id);
        if (selectElem) {
            if (selectElem.value === 'full') {
                if(amountContainer) amountContainer.style.display = 'none';
                if(adjustContainer) adjustContainer.style.display = 'none';
                if (statusElem) { statusElem.value = 'คืนแล้ว'; }
            } else if (selectElem.value === 'adjust') {
                if(amountContainer) amountContainer.style.display = 'none';
                if(adjustContainer) adjustContainer.style.display = 'block';
            } else {
                if(amountContainer) amountContainer.style.display = 'block';
                if(adjustContainer) adjustContainer.style.display = 'none';
                if (statusElem) { statusElem.value = 'ตัดยอดบางส่วน'; }
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
    function closeAllModals() {
        document.querySelectorAll('.modal').forEach(modal => {
            let bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) { bsModal.hide(); }
        });
        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
    }
    </script>
</body>
</html>
"""

def calculate_tx_values(tx):
    thai_today = get_thai_today()
    end_date = tx.closed_date if tx.closed_date else thai_today
    days = (end_date - tx.start_date).days + 1
    if days < 1: days = 1
    tx.days_passed_val = days
    
    if tx.original_principal > 0 and tx.initial_daily_interest > 0:
        tx.daily_interest = tx.initial_daily_interest * (tx.principal / tx.original_principal)
    
    acc = (tx.daily_interest * days) - tx.paid_interest
    tx.accumulated_interest = acc if acc > 0 else 0.0
    
    total_history_pay = 0.0
    if tx.histories:
        for h in tx.histories:
            p_item = h.pay_amount if h.pay_amount > 0 else (h.interest_paid + h.principal_reduced)
            total_history_pay += p_item

    if tx.type == 'ยอดค้างเก่า':
        principal_paid_calc = max(0.0, tx.original_principal - tx.principal)
        tx.total_paid = max(total_history_pay, principal_paid_calc)
    else:
        tx.total_paid = total_history_pay if total_history_pay > 0 else tx.paid_interest

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'admin' not in session: return redirect(url_for('login'))
        
    if request.method == 'POST':
        try:
            p_val = float(request.form.get('principal', 0) or 0)
            custom_start_date = request.form.get('start_date')
            parsed_date = datetime.strptime(custom_start_date, '%Y-%m-%d').date() if custom_start_date else get_thai_today()
            current_sales = session.get('admin', 'unknown')
            d_interest = float(request.form.get('daily_interest', 0) or 0)
            tx_type = request.form.get('type')
            funding_source = request.form.get('funding_source', 'กรุงศรีอยุธยา')
            
            schedule_type = request.form.get('schedule_type', 'จ่ายทุกวัน')
            selected_due_days = request.form.getlist('due_day_of_month') if schedule_type == 'กำหนดจ่ายประจำเดือน' else []
            due_day_str = ",".join(selected_due_days) if selected_due_days else None

            inst_amt = float(request.form.get('installment_amount', 0) or 0) if tx_type == 'ยอดค้างเก่า' else 0.0

            new_tx = Transaction(
                type=tx_type, customer_name=request.form.get('customer_name'), phone=request.form.get('phone'),
                sales_name=current_sales, start_date=parsed_date, original_principal=p_val, principal=p_val,
                daily_interest=d_interest, initial_daily_interest=d_interest, installment_amount=inst_amt,
                schedule_type=schedule_type, due_day_of_month=due_day_str, status='ปกติ',
                funding_source=funding_source
            )
            db.session.add(new_tx)

            if p_val > 0 and funding_source in ['กรุงศรีอยุธยา', 'ออมสิน', 'วอลเล็ท']:
                adj = BankAdjustment.query.filter_by(account_name=funding_source).first()
                if adj:
                    adj.adjustment_amount = max(0.0, adj.adjustment_amount - p_val)
                else:
                    db.session.add(BankAdjustment(account_name=funding_source, adjustment_amount=0.0))
                
                db.session.add(BankExpenseLog(
                    expense_date=parsed_date, account_name=funding_source, amount=p_val,
                    note=f"ปล่อยกู้/เพิ่มทุนลูกค้า: {request.form.get('customer_name')}", admin_name=current_sales
                ))

            db.session.commit()
        except Exception as e:
            db.session.rollback()
            print("Post error:", e)
        finally:
            db.session.remove()
        return redirect(url_for('index'))

    thai_today = get_thai_today()
    today_day = thai_today.day

    try:
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
                Transaction.last_payment_date == thai_today,
                Transaction.type == 'ยอดค้างเก่า' # ยอดค้างเก่าให้แสดงค้างไว้จนกว่าจะชำระหมด
            )
        ).all()

        seen_ids = set()
        transactions = []
        for t in scheduled_today + other_txs:
            if t.id not in seen_ids:
                seen_ids.add(t.id)
                transactions.append(t)

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

        current_year, current_month = thai_today.year, thai_today.month
        
        # คำนวณกำไรสะสมประจำเดือนนี้ (หักส่วนลดและบวกค่าปรับแล้ว)
        current_month_profit = 0.0
        for tx in all_txs_ever:
            latest_date = tx.start_date
            if tx.histories:
                max_h_date = max((h.payment_date for h in tx.histories if h.payment_date), default=None)
                if max_h_date and max_h_date > latest_date: latest_date = max_h_date
            if tx.last_payment_date and tx.last_payment_date > latest_date:
                latest_date = tx.last_payment_date
                
            if latest_date and latest_date.year == current_year and latest_date.month == current_month:
                if tx.type == 'ยอดค้างเก่า':
                    net_earned = max(0.0, (tx.original_principal - tx.principal))
                else:
                    hist_sum = sum(h.interest_paid for h in tx.histories) if tx.histories else 0.0
                    net_earned = max(tx.paid_interest, hist_sum)
                    
                tx_fine_sum = sum(h.fine_amount for h in tx.histories) if tx.histories else 0.0
                tx_discount_sum = sum(h.discount_amount for h in tx.histories) if tx.histories else 0.0
                current_month_profit += (net_earned + tx_fine_sum - tx_discount_sum)

        today_histories = PaymentHistory.query.filter_by(payment_date=thai_today).all()
        today_collected_cash = sum((h.pay_amount if h.pay_amount > 0 else (h.interest_paid + h.principal_reduced + h.fine_amount - h.discount_amount)) for h in today_histories)
        
        today_new_txs = [tx for tx in all_txs_ever if tx.start_date == thai_today]
        total_today_actions = len(today_new_txs) + len(today_histories)

        rows, modals_html = "", ""
        for tx in transactions:
            badge_color = 'bg-success' if tx.status == 'ปกติ' else ('bg-info text-dark' if tx.status == 'ตัดยอดบางส่วน' else 'bg-danger')
            start_date_str_fmt = tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'
            last_pay_str = tx.last_payment_date.strftime('%d/%m/%Y') if tx.last_payment_date else '-'
            closed_date_str = tx.closed_date.strftime('%Y-%m-%d') if tx.closed_date else ''
            
            selected_normal = "selected" if tx.status == "ปกติ" else ""
            selected_partial = "selected" if tx.status == "ตัดยอดบางส่วน" else ""

            schedule_badge = f'<span class="badge bg-dark">{tx.schedule_type}</span>'
            if tx.schedule_type == 'กำหนดจ่ายประจำเดือน' and tx.due_day_of_month:
                code_map = {"2": "29-2", "6": "4-6", "12": "9-12", "16": "14-16", "23": "20-23", "26": "24-26"}
                labels = [code_map.get(c, c) for c in tx.due_day_of_month.split(',')]
                schedule_badge = f'<span class="badge bg-primary">รอบ: {", ".join(labels)}</span>'

            active_cnt = customer_active_counts.get(tx.customer_name, 1)
            count_badge = f' <span class="badge bg-danger">🔥 {active_cnt} รายการ</span>'

            rows += f"""
            <tr>
                <td><b>{tx.customer_name}</b>{count_badge}</td>
                <td>{tx.phone or '-'}</td>
                <td><span class="badge bg-secondary">{tx.type}</span> {schedule_badge}</td>
                <td><span class="badge bg-warning text-dark">{tx.funding_source or 'กรุงศรีอยุธยา'}</span></td>
                <td>{start_date_str_fmt}</td>
                <td>{last_pay_str}</td>
                <td>{tx.original_principal:,.2f}</td>
                <td>{tx.principal:,.2f}</td>
                <td><strong class="text-primary">{tx.total_paid:,.2f}</strong></td>
                <td>{tx.daily_interest:,.2f}</td>
                <td>{tx.days_passed}</td>
                <td>{tx.accumulated_interest:,.2f}</td>
                <td><span class="badge {badge_color}">{tx.status}</span></td>
                <td class="text-center">
                    <button type="button" class="btn btn-sm btn-success-light" data-bs-toggle="modal" data-bs-target="#payModal{tx.id}">จัดการยอด</button>
                    <a href="/delete_tx/{tx.id}" class="btn btn-sm btn-danger" onclick="return confirm('ยืนยันการลบ?')">ลบ</a>
                </td>
            </tr>
            """

            modals_html += f"""
            <div class="modal fade" id="payModal{tx.id}" tabindex="-1">
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content border-warning">
                        <form action="/update_payment/{tx.id}" method="POST">
                            <div class="modal-header bg-danger text-white py-2">
                                <h5 class="modal-title fs-6">จัดการยอด: {tx.customer_name}</h5>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body py-2">
                                <div class="p-2 mb-2 bg-light rounded border d-flex justify-content-between align-items-center">
                                    <div><small class="text-muted d-block">เงินต้นคงเหลือ</small><b>{tx.principal:,.2f} บาท</b></div>
                                    <div class="text-end"><small class="text-muted d-block">ดอกเบี้ยสะสม</small><b class="text-danger">{tx.accumulated_interest:,.2f} บาท</b></div>
                                </div>
                                <div class="mb-2 p-2 bg-warning bg-opacity-10 rounded border border-warning">
                                    <label class="form-label text-dark fw-bold mb-1">📅 วันที่ปิดยอด / วันที่คืนยอด</label>
                                    <input type="date" name="closed_date" class="form-control form-control-sm bg-white" value="{closed_date_str}">
                                </div>
                                <div class="mb-2 p-2 bg-success bg-opacity-10 rounded border border-success">
                                    <label class="form-label text-success fw-bold mb-1">📥 ช่องทางรับเงิน:</label>
                                    <select name="receiving_account" class="form-select form-select-sm">
                                        <option value="กรุงศรีอยุธยา">🟡 กรุงศรีอยุธยา (803-xxx-9819)</option>
                                        <option value="ออมสิน">🩷 ออมสิน (020-xxx-437-819)</option>
                                        <option value="วอลเล็ท">🟠 TrueMoney Wallet (092-xxx-7819)</option>
                                    </select>
                                </div>
                                <div class="p-2 mb-2 rounded border border-primary bg-primary bg-opacity-10">
                                    <div class="mb-2">
                                        <label class="form-label fw-bold text-primary mb-1">💳 เลือกประเภทการชำระ</label>
                                        <select name="payment_type" class="form-select form-select-sm" id="payType{tx.id}" onchange="togglePayInput({tx.id})" required>
                                            <option value="" disabled selected>-- กรุณาเลือก --</option>
                                            <option value="partial">จ่ายบางส่วน</option>
                                            <option value="full">คืนครบทั้งหมด</option>
                                            <option value="adjust">ปรับปรุงยอด</option>
                                        </select>
                                    </div>
                                    <div class="mb-1" id="amountDiv{tx.id}">
                                        <label class="form-label fw-bold text-primary mb-1">💵 จำนวนเงินรับจริง (บาท)</label>
                                        <input type="number" step="any" name="pay_amount" class="form-control form-control-sm bg-white" placeholder="กรอกจำนวนเงิน">
                                    </div>
                                    <div class="mb-1" id="adjustContainer{tx.id}" style="display: none;">
                                        <label class="form-label fw-bold text-dark mb-1">⚙️ จำนวนเงินปรับปรุงต้น (บาท)</label>
                                        <input type="number" step="any" name="adjust_amount" class="form-control form-control-sm" placeholder="เช่น 500 หรือ -200">
                                    </div>
                                </div>
                                <div class="row g-2 mb-2">
                                    <div class="col-6">
                                        <label class="form-label text-danger small fw-bold mb-1">ส่วนลด (บาท)</label>
                                        <input type="number" step="any" name="discount_amount" class="form-control form-control-sm" value="0">
                                    </div>
                                    <div class="col-6">
                                        <label class="form-label text-warning text-dark small fw-bold mb-1">เบี้ยค่าปรับ (บาท)</label>
                                        <input type="number" step="any" name="fine_amount" class="form-control form-control-sm" value="0">
                                    </div>
                                </div>
                                <div class="mb-2">
                                    <label class="form-label text-dark fw-bold mb-1">📝 หมายเหตุ</label>
                                    <input type="text" name="note" class="form-control form-control-sm" placeholder="เช่น โอนผ่าน KTB">
                                </div>
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

        content = f"""
        <div class="row mb-4">
            <div class="col-md-4 mb-3">
                <div class="card p-3 shadow-sm text-white border-success" style="background: linear-gradient(135deg, #198754, #20c997);">
                    <h6 class="mb-1 text-white-50">💵 ยอดเก็บสดวันนี้</h6>
                    <h3 class="fw-bold mb-0">{today_collected_cash:,.2f} บาท</h3>
                </div>
            </div>
            <div class="col-md-4 mb-3">
                <div class="card p-3 shadow-sm text-white border-info" style="background: linear-gradient(135deg, #0dcaf0, #6610f2);">
                    <h6 class="mb-1 text-white-50">⚡ ธุรกรรมทั้งหมดวันนี้</h6>
                    <h3 class="fw-bold mb-0">{total_today_actions} รายการ</h3>
                </div>
            </div>
            <div class="col-md-4 mb-3">
                <div class="card p-3 shadow-sm text-white border-warning" style="background: linear-gradient(135deg, #ffc107, #fd7e14);">
                    <h6 class="mb-1 text-dark fw-bold">📈 กำไรสะสมเดือนนี้ (สุทธิ)</h6>
                    <h3 class="fw-bold text-dark mb-0">{current_month_profit:,.2f} บาท</h3>
                </div>
            </div>
        </div>

        <div class="card p-4 shadow-sm border-warning mb-4">
            <h4 class="mb-3 fs-5 text-danger fw-bold">➕ เพิ่มรายการใหม่ (ผู้ดูแล: <span class="text-dark">{session.get('admin')}</span>)</h4>
            <form method="POST" class="row g-3">
                <div class="col-md-3">
                    <label class="form-label">ประเภทรายการ</label>
                    <select name="type" class="form-select" id="txTypeSelect" onchange="handleTypeChange()" required>
                        <option value="เงินฉุกเฉิน">เงินฉุกเฉิน</option>
                        <option value="ผ่อนทอง">ผ่อนทอง</option>
                        <option value="ยอดค้างเก่า">ยอดค้างเก่า</option>
                    </select>
                </div>
                <div class="col-md-3">
                    <label class="form-label">ชื่อลูกค้า</label>
                    <input type="text" name="customer_name" class="form-control" list="customerList" autocomplete="off" required>
                    <datalist id="customerList">{datalist_options}</datalist>
                </div>
                <div class="col-md-3">
                    <label class="form-label">เบอร์โทร</label>
                    <input type="text" name="phone" class="form-control">
                </div>
                <div class="col-md-3">
                    <label class="form-label">วันที่กู้/เริ่ม</label>
                    <input type="date" name="start_date" class="form-control" value="{thai_today.strftime('%Y-%m-%d')}" required>
                </div>
                <div class="col-md-4">
                    <label class="form-label text-success fw-bold">💳 แหล่งทุน:</label>
                    <select name="funding_source" class="form-select border-success" required>
                        <option value="กรุงศรีอยุธยา">กรุงศรีอยุธยา</option>
                        <option value="ออมสิน">ออมสิน</option>
                        <option value="วอลเล็ท">TrueMoney Wallet</option>
                    </select>
                </div>
                <div class="col-md-3">
                    <label class="form-label text-danger fw-bold">ประเภทกำหนดจ่าย</label>
                    <select name="schedule_type" class="form-select border-danger" id="scheduleTypeSelect" onchange="handleScheduleChange()" required>
                        <option value="จ่ายทุกวัน">จ่ายทุกวัน</option>
                        <option value="กำหนดจ่ายประจำเดือน">กำหนดจ่ายประจำเดือน</option>
                        <option value="ยังไม่มีกำหนดจ่าย">ยังไม่มีกำหนดจ่าย</option>
                    </select>
                </div>
                <div class="col-md-5" id="dueDayDiv" style="display: none;">
                    <label class="form-label text-primary fw-bold">รอบช่วงวันที่</label>
                    <div class="p-2 border rounded bg-white d-flex flex-wrap gap-3">
                        <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="2" id="chk_d2"><label class="form-check-label small" for="chk_d2">29-2</label></div>
                        <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="6" id="chk_d6"><label class="form-check-label small" for="chk_d6">4-6</label></div>
                        <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="12" id="chk_d12"><label class="form-check-label small" for="chk_d12">9-12</label></div>
                        <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="16" id="chk_d16"><label class="form-check-label small" for="chk_d16">14-16</label></div>
                        <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="23" id="chk_d23"><label class="form-check-label small" for="chk_d23">20-23</label></div>
                        <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="26" id="chk_d26"><label class="form-check-label small" for="chk_d26">24-26</label></div>
                    </div>
                </div>
                <div class="col-md-3">
                    <label class="form-label">เงินต้น/ยอดค้าง (บาท)</label>
                    <input type="number" step="any" name="principal" class="form-control" required>
                </div>
                <div class="col-md-3" id="installmentDiv" style="display: none;">
                    <label class="form-label text-danger fw-bold">ยอดชำระต่องวด</label>
                    <input type="number" step="any" name="installment_amount" class="form-control" value="0">
                </div>
                <div class="col-md-3">
                    <label class="form-label">ดอกเบี้ย/วัน</label>
                    <input type="number" step="any" name="daily_interest" class="form-control" value="0" required>
                </div>
                <div class="col-md-3 d-flex align-items-end">
                    <button type="submit" class="btn btn-success w-100 fw-bold" onclick="closeAllModals()">บันทึกข้อมูล</button>
                </div>
            </form>
        </div>

        <div class="card p-4 shadow-sm border-warning mb-4">
            <h4 class="mb-3 fs-5 text-danger fw-bold">🔔 รายการที่ต้องทวงวันนี้ (ประจำวันที่ {today_day})</h4>
            <div class="table-responsive">
                <table class="table table-striped align-middle text-nowrap">
                    <thead class="table-dark">
                        <tr>
                            <th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>ประเภท</th><th>บัญชีปล่อย</th><th>วันที่กู้</th>
                            <th>ชำระล่าสุด</th><th>เงินลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th>
                            <th>ดอก/วัน</th><th>เวลาผ่าน</th><th>ดอกสะสม</th><th>สถานะ</th><th class="text-center">จัดการ</th>
                        </tr>
                    </thead>
                    <tbody>{rows if rows else "<tr><td colspan='14' class='text-center text-muted'>ไม่มีรายการที่ต้องทวงในวันนี้</td></tr>"}</tbody>
                </table>
            </div>
        </div>
        {modals_html}
        """
        html = BASE_LAYOUT.replace('{% block header %}Dashboard{% endblock %}', '🔱 Dashboard บริหารจัดการระบบ')
        return render_template_string(html.replace('{% block content %}{% endblock %}', content), title="Dashboard", page="dashboard")
    except Exception as e:
        db.session.rollback()
        print("Index route error:", e)
        return f"<h3>⚠️ เกิดข้อผิดพลาด: {str(e)}</h3><a href='/'>รีเฟรช</a>"
    finally:
        db.session.remove()

@app.route('/monthly_summary')
def monthly_summary():
    if 'admin' not in session: return redirect(url_for('login'))
    try:
        all_txs = Transaction.query.all()
        for tx in all_txs: calculate_tx_values(tx)
        
        months_data = defaultdict(lambda: {'invest': 0.0, 'count': 0})
        for tx in all_txs:
            if tx.start_date:
                m_key = tx.start_date.strftime('%Y-%m')
                if tx.type != 'ยอดค้างเก่า':
                    months_data[m_key]['invest'] += tx.original_principal
                months_data[m_key]['count'] += 1

        sorted_months = sorted(months_data.keys(), reverse=True)
        cards_html = ""
        for m in sorted_months:
            parts = m.split('-')
            thai_months = {"01": "มกราคม", "02": "กุมภาพันธ์", "03": "มีนาคม", "04": "เมษายน", "05": "พฤษภาคม", "06": "มิถุนายน", "07": "กรกฎาคม", "08": "สิงหาคม", "09": "กันยายน", "10": "ตุลาคม", "11": "พฤศจิกายน", "12": "ธันวาคม"}
            m_label = f"{thai_months.get(parts[1], parts[1])} {int(parts[0])+543}"
            
            cards_html += f"""
            <div class="col-md-4 mb-3">
                <div class="card p-3 shadow-sm border-warning">
                    <h5 class="text-danger fw-bold">📁 ประจำเดือน {m_label}</h5>
                    <p class="mb-1 text-muted">จำนวนรายการ: <b>{months_data[m]['count']}</b> รายการ</p>
                    <p class="mb-3 text-muted">ยอดปล่อยกู้: <b>{months_data[m]['invest']:,.2f}</b> บาท</p>
                    <a href="/monthly_detail/{m}" class="btn btn-warning btn-sm fw-bold">🔍 เปิดแฟ้มดูรายละเอียด</a>
                </div>
            </div>
            """

        content = f"""<div class="row">{cards_html if cards_html else "<p class='text-center text-muted'>ยังไม่มีข้อมูลในกล่องแฟ้ม</p>"}</div>"""
        html = BASE_LAYOUT.replace('{% block header %}กล่องแฟ้มรายเดือน{% endblock %}', '📁 กล่องแฟ้มรายเดือน (Monthly Summary)').replace('{% block content %}{% endblock %}', content)
        return render_template_string(html, title="กล่องแฟ้มรายเดือน", page="monthly")
    finally:
        db.session.remove()

@app.route('/monthly_detail/<string:year_month>')
def monthly_detail(year_month):
    if 'admin' not in session: return redirect(url_for('login'))
    try:
        parts = year_month.split('-')
        y, m = int(parts[0]), int(parts[1])
        all_txs = Transaction.query.all()
        for tx in all_txs: calculate_tx_values(tx)
        
        filtered = [tx for tx in all_txs if tx.start_date and tx.start_date.year == y and tx.start_date.month == m]
        rows = "".join([f"<tr><td>{tx.customer_name}</td><td><span class='badge bg-secondary'>{tx.type}</span></td><td>{tx.start_date.strftime('%d/%m/%Y')}</td><td class='text-primary fw-bold'>{tx.original_principal:,.2f}</td><td class='text-danger fw-bold'>{tx.principal:,.2f}</td></tr>" for tx in filtered])

        content = f"""
        <div class="card p-4 shadow-sm border-warning">
            <div class="d-flex justify-content-between align-items-center mb-3">
                <h4 class="text-danger fw-bold">รายละเอียดแฟ้มประจำเดือน: {year_month}</h4>
                <a href="/monthly_summary" class="btn btn-secondary btn-sm">⬅️ กลับหน้ากล่องแฟ้ม</a>
            </div>
            <div class="table-responsive">
                <table class="table table-striped align-middle">
                    <thead class="table-dark">
                        <tr><th>ชื่อลูกค้า</th><th>ประเภท</th><th>วันที่กู้</th><th>ยอดลงทุน</th><th>ต้นคงค้าง</th></tr>
                    </thead>
                    <tbody>{rows if rows else "<tr><td colspan='5' class='text-center text-muted'>ไม่มีข้อมูลในเดือนนี้</td></tr>"}</tbody>
                </table>
            </div>
        </div>
        """
        html = BASE_LAYOUT.replace('{% block header %}รายละเอียดแฟ้มรายเดือน{% endblock %}', f'📁 แฟ้มเดือน {year_month}').replace('{% block content %}{% endblock %}', content)
        return render_template_string(html, title=f"แฟ้ม {year_month}", page="monthly")
    finally:
        db.session.remove()

@app.route('/all_transactions')
def all_transactions():
    if 'admin' not in session: return redirect(url_for('login'))
    try:
        txs = Transaction.query.order_by(Transaction.start_date.desc()).all()
        for tx in txs: calculate_tx_values(tx)
        rows = "".join([f"<tr><td>{tx.customer_name}</td><td>{tx.phone or '-'}</td><td><span class='badge bg-secondary'>{tx.type}</span></td><td>{tx.start_date.strftime('%d/%m/%Y')}</td><td>{tx.original_principal:,.2f}</td><td class='text-danger fw-bold'>{tx.principal:,.2f}</td><td><span class='badge bg-success'>{tx.status}</span></td></tr>" for tx in txs])
        content = f"""
        <div class="card p-4 shadow-sm border-warning">
            <h4 class="text-danger fw-bold mb-3">📋 รายการทั้งหมดในระบบ</h4>
            <div class="table-responsive">
                <table class="table table-striped align-middle">
                    <thead class="table-dark"><tr><th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>ประเภท</th><th>วันที่กู้</th><th>ยอดกู้</th><th>ต้นคงค้าง</th><th>สถานะ</th></tr></thead>
                    <tbody>{rows if rows else "<tr><td colspan='7' class='text-center text-muted'>ยังไม่มีรายการ</td></tr>"}</tbody>
                </table>
            </div>
        </div>
        """
        html = BASE_LAYOUT.replace('{% block header %}รายการทั้งหมด{% endblock %}', '📋 รายการทั้งหมด').replace('{% block content %}{% endblock %}', content)
        return render_template_string(html, title="รายการทั้งหมด", page="all")
    finally:
        db.session.remove()

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username, password = request.form.get('username', '').strip(), request.form.get('password', '').strip()
        if username in VALID_USERS and VALID_USERS[username] == password:
            session['admin'] = username
            return redirect(url_for('index'))
        else: error = 'ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง!'
    login_html = """<!DOCTYPE html><html lang="th"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>เข้าสู่ระบบ - ทรัพย์ล้น</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><link href="https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600&display=swap" rel="stylesheet"><style>body{font-family:'Prompt',sans-serif;background:linear-gradient(135deg,#2c0b0e,#1a0507);color:#fff}.card{background:#fff;color:#333;border:2px solid #d4af37}</style></head><body class="d-flex align-items-center justify-content-center vh-100 p-3"><div class="card p-4 shadow-lg w-100" style="max-width:380px;"><h3 class="text-center mb-1 text-danger fw-bold">🔱 ทรัพย์ล้น</h3><p class="text-center text-muted small mb-4">ระบบบริหารจัดการการเงิน</p>{% if error %}<div class="alert alert-danger py-2 text-center">{{ error }}</div>{% endif %}<form method="POST"><div class="mb-3"><label class="form-label">ชื่อผู้ใช้งาน:</label><input type="text" name="username" class="form-control" required></div><div class="mb-3"><label class="form-label">รหัสผ่าน:</label><input type="password" name="password" class="form-control" required></div><button type="submit" class="btn btn-warning w-100 fw-bold">เข้าสู่ระบบ</button></form></div></body></html>"""
    return render_template_string(login_html, error=error)

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
