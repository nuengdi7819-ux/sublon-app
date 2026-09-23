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
app.config['SECRET_KEY'] = 'your_secret_key_sublon_2026'

app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
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

        .table-responsive { overflow-x: auto; -webkit-overflow-scrolling: touch; }
        .table-responsive::-webkit-scrollbar { height: 10px; }
        .table-responsive::-webkit-scrollbar-track { background: #f1f1f1; border-radius: 6px; }
        .table-responsive::-webkit-scrollbar-thumb { background: #d4af37; border-radius: 6px; }

        @media (max-width: 768px) {
            .modal-dialog { margin: 10px; max-width: calc(100% - 20px); }
            .modal-body { max-height: 70vh; overflow-y: auto; }
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
        <div class="modal-dialog">
            <div class="modal-content">
                <form action="/import_data" method="POST" enctype="multipart/form-data">
                    <div class="modal-header bg-info text-dark">
                        <h5 class="modal-title fw-bold">📤 นำเข้าข้อมูลสำรอง (Restore CSV)</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p class="text-muted small">เลือกไฟล์ CSV ที่เคยสำรองข้อมูลไว้เพื่อดึงข้อมูลกลับเข้าสู่ระบบ</p>
                        <div class="mb-3"><input type="file" name="file" class="form-control" accept=".csv" required></div>
                    </div>
                    <div class="modal-footer">
                        <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">ยกเลิก</button>
                        <button type="submit" class="btn btn-info fw-bold" onclick="return confirm('ยืนยันการนำเข้าข้อมูล?')">อัปโหลดและกู้คืน</button>
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
    
    if tx.original_principal > 0 and tx.initial_daily_interest > 0:
        current_daily_interest = tx.initial_daily_interest * (tx.principal / tx.original_principal)
        tx.daily_interest = current_daily_interest
    
    acc = (tx.daily_interest * days) - tx.paid_interest
    tx.accumulated_interest = acc if acc > 0 else 0.0
    
    fallback_principal_reduced = max(0.0, tx.original_principal - tx.principal)
    
    if tx.type == 'ยอดค้างเก่า':
        tx.total_paid = fallback_principal_reduced
    else:
        sum_history_pay = 0.0
        sum_interest_paid = 0.0
        sum_principal_reduced = 0.0
        if tx.histories:
            for h in tx.histories:
                sum_principal_reduced += h.principal_reduced
                sum_interest_paid += h.interest_paid
                sum_history_pay += h.pay_amount if h.pay_amount > 0 else (h.interest_paid + h.principal_reduced)
        
        actual_prin_reduced = sum_principal_reduced if sum_principal_reduced > 0 else fallback_principal_reduced
        calculated_paid_total = sum_interest_paid + actual_prin_reduced
        if calculated_paid_total <= 0:
            calculated_paid_total = tx.paid_interest + fallback_principal_reduced
        tx.total_paid = max(sum_history_pay, calculated_paid_total)

@app.route('/', methods=['GET', 'POST'])
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
                funding_source=funding_source, start_next_day=start_next_day_val
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
        
        total_debt_principal = sum(tx.principal for tx in all_txs_ever if tx.type == 'ยอดค้างเก่า' and tx.principal > 0)
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

        profit_items = []
        current_month_profit = 0.0
        
        all_txs_for_profit = Transaction.query.all()
        for tx in all_txs_for_profit:
            calculate_tx_values(tx)
            # เช็คว่ามีประวัติหรือมีการชำระในเดือนปัจจุบันไหม หรือถ้าเป็นยอดค้างเก่าให้ดูจากยอดที่ชำระแล้ว (total_paid)
            if tx.type == 'ยอดค้างเก่า':
                if tx.total_paid > 0:
                    # สำหรับยอดค้างเก่า กำไร/ยอดสะสมจริงคือยอดที่ชำระแล้ว (เงินต้นที่ลดลงจริง)
                    item_profit = tx.total_paid
                    profit_items.append({
                        'customer_name': tx.customer_name,
                        'type': tx.type,
                        'net_earned': item_profit,
                        'fine_amount': 0.0,
                        'discount_amount': 0.0,
                        'total_item_profit': item_profit,
                        'latest_date': tx.last_payment_date if tx.last_payment_date else tx.start_date
                    })
                    current_month_profit += item_profit
            else:
                # สำหรับลูกค้าใหม่ คำนวณจากประวัติการชำระในเดือนปัจจุบัน
                tx_net_earned = 0.0
                tx_fine = 0.0
                tx_discount = 0.0
                latest_d = None
                has_history_this_month = False
                
                if tx.histories:
                    for h in tx.histories:
                        if h.payment_date and h.payment_date.year == current_year and h.payment_date.month == current_month:
                            has_history_this_month = True
                            tx_net_earned += h.interest_paid
                            tx_fine += h.fine_amount
                            tx_discount += h.discount_amount
                            if not latest_d or h.payment_date > latest_d:
                                latest_d = h.payment_date
                
                if has_history_this_month or tx.paid_interest > 0:
                    total_item_profit = tx_net_earned + tx_fine - tx_discount
                    if total_item_profit > 0 or tx_net_earned > 0:
                        profit_items.append({
                            'customer_name': tx.customer_name,
                            'type': tx.type,
                            'net_earned': tx_net_earned,
                            'fine_amount': tx_fine,
                            'discount_amount': tx_discount,
                            'total_item_profit': total_item_profit,
                            'latest_date': latest_d if latest_d else tx.start_date
                        })
                        current_month_profit += total_item_profit

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
            <td colspan="5" class="text-end">รวมกำไรสะสมทั้งระบบ (หักส่วนลดแล้ว):</td>
            <td colspan="2" class="text-success">{sum_modal_actual_profit:,.2f} บาท</td>
        </tr>
        """

        rows, cards, modals_html = "", "", ""
        for tx in transactions:
            badge_color = 'bg-success'
            if tx.status == 'ตัดยอดบางส่วน': badge_color = 'bg-info text-dark'
            elif tx.status == 'คืนแล้ว': badge_color = 'bg-danger'

            start_date_str_fmt = tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'
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
                <td>{start_date_str_fmt}</td>
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
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content border-warning">
                        <form action="/update_payment/{tx.id}" method="POST">
                            <div class="modal-header bg-danger text-white py-2">
                                <h5 class="modal-title fs-6">จัดการยอด: {tx.customer_name}</h5>
                                <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                            </div>
                            <div class="modal-body py-2">
                                <div class="p-2 mb-2 bg-light rounded border d-flex justify-content-between align-items-center">
                                    <div><small class="text-muted d-block" style="font-size: 0.75rem;">เงินต้นคงเหลือ</small><b>{tx.principal:,.2f} บาท</b></div>
                                    <div class="text-end"><small class="text-muted d-block" style="font-size: 0.75rem;">ดอกเบี้ยสะสม</small><b class="text-danger" id="accInterestDisplay{tx.id}">{tx.accumulated_interest:,.2f} บาท</b></div>
                                </div>
                                <div class="mb-2 p-2 bg-warning bg-opacity-10 rounded border border-warning">
                                    <label class="form-label text-dark fw-bold mb-1" style="font-size: 0.85rem;">📅 วันที่ปิดยอด / วันที่คืนยอด</label>
                                    <input type="date" name="closed_date" class="form-control form-control-sm border-warning bg-white" id="closedDate{tx.id}" value="{closed_date_str}">
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
                                            <option value="adjust">ปรับปรุงยอด</option>
                                        </select>
                                    </div>
                                    <div class="mb-1" id="amountDiv{tx.id}">
                                        <label class="form-label fw-bold text-primary mb-1" style="font-size: 0.85rem;">💵 จำนวนเงินที่รับชำระจริง (บาท)</label>
                                        <input type="number" step="any" name="pay_amount" class="form-control form-control-sm border-primary shadow-sm bg-white" placeholder="กรอกจำนวนเงินสดที่รับจริง">
                                    </div>

                                    <div class="mb-1" id="adjustContainer{tx.id}" style="display: none;">
                                        <label class="form-label fw-bold text-dark mb-1" style="font-size: 0.85rem;">⚙️ จำนวนเงินปรับปรุงต้น (บาท)</label>
                                        <input type="number" step="any" name="adjust_amount" class="form-control form-control-sm mb-1" placeholder="เช่น 500 หรือ -200">
                                        <small class="text-muted d-block" style="font-size: 0.72rem;">* (+) เพิ่มยอดต้น | (-) ลด/แก้ชื่อยอดผิด</small>
                                    </div>
                                </div>

                                <div class="row g-2 mb-2">
                                    <div class="col-6">
                                        <label class="form-label text-danger small fw-bold mb-1" style="font-size: 0.75rem;">ส่วนลด (บาท)</label>
                                        <input type="number" step="any" name="discount_amount" class="form-control form-control-sm" value="0" placeholder="0">
                                    </div>
                                    <div class="col-6">
                                        <label class="form-label text-warning text-dark small fw-bold mb-1" style="font-size: 0.75rem;">เบี้ยค่าปรับ (บาท)</label>
                                        <input type="number" step="any" name="fine_amount" class="form-control form-control-sm" value="0" placeholder="0">
                                    </div>
                                </div>
                                <div class="mb-1">
                                    <label class="form-label text-dark fw-bold mb-1" style="font-size: 0.85rem;">📝 หมายเหตุการชำระ</label>
                                    <input type="text" name="note" class="form-control form-control-sm" placeholder="เช่น จ่ายเฉพาะค่าปรับ, โอนผ่าน KTB">
                                </div>
                            </div>
                            <div class="modal-footer bg-light py-2 justify-content-between">
                                <a href="/history/{tx.id}" class="btn btn-outline-info btn-sm" target="_blank">📜 ดูประวัติการจ่าย</a>
                                <div>
                                    <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ยกเลิก</button>
                                    <button type="submit" class="btn btn-success-light btn-sm fw-bold px-3" onclick="closeAllModals()">บันทึกการชำระ</button>
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
            table_title = f"📋 ผลการค้นหา: \"{search_query}\""
            view_today_btn = '<a href="/" class="btn btn-sm btn-success fw-bold">🟢 แสดงรายการแจ้งเตือนวันนี้</a>'
        else:
            table_title = f"🔔 รายการที่ต้องทวงวันนี้ (ประจำวันที่ {today_day})"
            view_today_btn = '<a href="/all_transactions" class="btn btn-sm btn-outline-danger fw-bold">📂 ดูรายการทั้งหมด</a>'

        content = f"""
        <!-- 4 กล่องสรุป -->
        <div class="row mb-4">
            <div class="col-md-3 mb-3 mb-md-0">
                <div class="card p-3 shadow-sm text-white h-100" style="background: linear-gradient(135deg, #d97706, #f59e0b); cursor: pointer;" data-bs-toggle="modal" data-bs-target="#debtModal" title="คลิกเพื่อเช็กรายละเอียด">
                    <div style="font-size: 0.9rem;" class="mb-1">📂 ยอดค้างเก่าคงเหลือ</div>
                    <h5 class="fw-bold mb-0">{total_debt_principal:,.2f} บ.</h5>
                </div>
            </div>
            <div class="col-md-3 mb-3 mb-md-0">
                <div class="card p-3 shadow-sm text-white h-100" style="background: linear-gradient(135deg, #b30000, #ff4d4d); cursor: pointer;" data-bs-toggle="modal" data-bs-target="#principalModal" title="คลิกเพื่อเช็กรายละเอียด">
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
                <div class="card p-3 shadow-sm text-white h-100" style="background: linear-gradient(135deg, #006622, #00b33c); cursor: pointer;" data-bs-toggle="modal" data-bs-target="#profitModal" title="คลิกเพื่อเช็กรายละเอียด">
                    <div style="font-size: 0.9rem;" class="mb-1">💰 กำไรสะสม (เดือนนี้)</div>
                    <h5 class="fw-bold mb-0">{current_month_profit:,.2f} บ.</h5>
                </div>
            </div>
        </div>

        <!-- สถานะกระเป๋าเงินจริงในมือถือ -->
        <div class="card p-3 mb-4 shadow-sm border-warning bg-white">
            <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
                <h5 class="text-danger fw-bold mb-0">🏦 สถานะกระเป๋าเงินจริงในมือถือ</h5>
                <div class="d-flex gap-2 flex-wrap">
                    <button type="button" class="btn btn-outline-primary btn-sm fw-bold" data-bs-toggle="modal" data-bs-target="#transferBankModal">🔄 โยกเงิน</button>
                    <button type="button" class="btn btn-outline-danger btn-sm fw-bold" data-bs-toggle="modal" data-bs-target="#adjustBankModal">⚙️ ตั้งค่า/ปรับยอด</button>
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

        <!-- Modal โยกเงิน -->
        <div class="modal fade" id="transferBankModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered">
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

        <!-- Modal ปรับยอดเงิน -->
        <div class="modal fade" id="adjustBankModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered">
                <div class="modal-content border-danger">
                    <form action="/update_bank_adjustment" method="POST">
                        <div class="modal-header bg-danger text-white py-2">
                            <h5 class="modal-title fw-bold fs-6">⚙️ ตั้งค่าปรับยอดเงินตั้งต้นกระเป๋าจริง</h5>
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

        <!-- Modal ถอนเงิน -->
        <div class="modal fade" id="withdrawModal" tabindex="-1">
            <div class="modal-dialog modal-dialog-centered">
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

        <!-- ฟอร์มเพิ่มรายการใหม่ -->
        <div class="card p-4 shadow-sm mb-4 border-warning">
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
                        <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="12" id="chk_d12"><label class="form-check-label small" for="chk_d12">9-12</label></div>
                        <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="16" id="chk_d16"><label class="form-check-label small" for="chk_d16">14-16</label></div>
                        <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="23" id="chk_d23"><label class="form-check-label small" for="chk_d23">20-23</label></div>
                        <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="26" id="chk_d26"><label class="form-check-label small" for="chk_d26">24-26</label></div>
                    </div>
                </div>
                <div class="col-md-3">
                    <label class="form-label">ยอดเงินต้น/ยอดค้างทั้งหมด (บาท)</label>
                    <input type="number" step="any" name="principal" class="form-control" required>
                </div>
                <div class="col-md-3" id="installmentDiv" style="display: none;">
                    <label class="form-label text-danger fw-bold">ยอดชำระต่องวด (บาท)</label>
                    <input type="number" step="any" name="installment_amount" class="form-control" value="0" placeholder="เช่น 150">
                </div>
                <div class="col-md-3">
                    <label class="form-label">ดอกเบี้ย/วัน (บาท)</label>
                    <input type="number" step="any" name="daily_interest" class="form-control" value="0" required>
                </div>

                <div class="col-md-6 d-flex align-items-center">
                    <div class="form-check">
                        <input class="form-check-input border-warning" type="checkbox" name="start_next_day" id="startNextDayChk">
                        <label class="form-check-label fw-bold text-dark" for="startNextDayChk">
                            ⌛ เริ่มคิดดอกเบี้ยวันถัดไป (พรุ่งนี้)
                        </label>
                    </div>
                </div>

                <div class="col-md-3 d-flex align-items-end">
                    <button type="submit" class="btn btn-success w-100 fw-bold" onclick="closeAllModals()">บันทึกข้อมูล</button>
                </div>
            </form>
        </div>

        <!-- สรุปผลงานวันนี้ -->
        <div class="row mb-4">
            <div class="col-md-6 mb-3">
                <div class="card p-3 shadow-sm text-white border-success" style="background: linear-gradient(135deg, #198754, #20c997); cursor: pointer;" data-bs-toggle="modal" data-bs-target="#todayHistoryModal" title="คลิกเพื่อดูรายละเอียด">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-1 text-white-50">💵 ยอดเก็บสดวันนี้ (คลิกเพื่อดู)</h6>
                            <h3 class="fw-bold mb-0">{today_collected_cash:,.2f} บาท</h3>
                        </div>
                        <div class="fs-1 opacity-50">📥</div>
                    </div>
                </div>
            </div>
            <div class="col-md-6 mb-3">
                <div class="card p-3 shadow-sm text-white border-info" style="background: linear-gradient(135deg, #0dcaf0, #6610f2); cursor: pointer;" data-bs-toggle="modal" data-bs-target="#todayActionsModal" title="คลิกเพื่อดูรายละเอียด">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="mb-1 text-white-50">⚡ ธุรกรรมทั้งหมดวันนี้ (คลิกเพื่อดู)</h6>
                            <h3 class="fw-bold mb-0">{total_today_actions} รายการ</h3>
                        </div>
                        <div class="fs-1 opacity-50">⚡</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- Modal ยอดเก็บสด -->
        <div class="modal fade" id="todayHistoryModal" tabindex="-1">
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content border-success">
                    <div class="modal-header bg-success text-white py-2">
                        <h5 class="modal-title fs-6 fw-bold">📋 รายละเอียดการเก็บเงิน ประจำวันนี้ ({thai_today.strftime('%d/%m/%Y')})</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body" style="max-height: 65vh; overflow-y: auto;">
                        <div class="table-responsive">
                            <table class="table table-striped align-middle text-nowrap">
                                <thead class="table-dark">
                                    <tr><th>ชื่อลูกค้า</th><th>ยอดจ่ายจริง</th><th>เข้าบัญชี</th><th>ค่าปรับ</th><th>ส่วนลด</th><th>ตัดดอกเบี้ย</th><th>ตัดเงินต้น</th><th>หมายเหตุ</th><th>ผู้ทำรายการ</th></tr>
                                </thead>
                                <tbody>{today_history_rows if today_history_rows else "<tr><td colspan='9' class='text-center text-muted'>ยังไม่มีการเก็บเงินในวันนี้</td></tr>"}</tbody>
                            </table>
                        </div>
                    </div>
                    <div class="modal-footer py-2"><button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ปิดหน้าต่าง</button></div>
                </div>
            </div>
        </div>

        <!-- Modal ธุรกรรมวันนี้ -->
        <div class="modal fade" id="todayActionsModal" tabindex="-1">
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content border-info">
                    <div class="modal-header bg-info text-dark py-2">
                        <h5 class="modal-title fs-6 fw-bold">⚡ สรุปธุรกรรมและความเคลื่อนไหวทั้งหมด ประจำวันนี้ ({thai_today.strftime('%d/%m/%Y')})</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body" style="max-height: 65vh; overflow-y: auto;">
                        <div class="mb-4">
                            <h6 class="text-primary fw-bold border-bottom pb-2">➕ หมวดที่ 1: รายการเพิ่มเงินลงทุนใหม่วันนี้ ({today_new_count} รายการ)</h6>
                            <div class="table-responsive">
                                <table class="table table-sm table-striped align-middle text-nowrap">
                                    <thead class="table-dark"><tr><th>ชื่อลูกค้า</th><th>ประเภท</th><th>เบอร์โทร</th><th>ยอดลงทุน</th><th>บัญชีที่ใช้ปล่อย</th><th>เซลล์ผู้ดูแล</th></tr></thead>
                                    <tbody>{today_new_rows if today_new_rows else "<tr><td colspan='6' class='text-center text-muted'>ไม่มีการเพิ่มเงินลงทุนใหม่ในวันนี้</td></tr>"}</tbody>
                                </table>
                            </div>
                        </div>
                        <div>
                            <h6 class="text-success fw-bold border-bottom pb-2">💵 หมวดที่ 2: รายการรับชำระ / เก็บยอด / ปรับปรุงยอดวันนี้ ({today_payment_count} รายการ)</h6>
                            <div class="table-responsive">
                                <table class="table table-sm table-striped align-middle text-nowrap">
                                    <thead class="table-dark"><tr><th>ชื่อลูกค้า</th><th>ยอดจ่ายจริง</th><th>เข้าบัญชี</th><th>ค่าปรับ</th><th>ส่วนลด</th><th>ตัดดอกเบี้ย</th><th>ตัดเงินต้น</th><th>หมายเหตุ</th><th>ผู้ทำรายการ</th></tr></thead>
                                    <tbody>{today_history_rows if today_history_rows else "<tr><td colspan='9' class='text-center text-muted'>ยังไม่มีการทำธุรกรรมรับชำระในวันนี้</td></tr>"}</tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer py-2"><button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ปิดหน้าต่าง</button></div>
                </div>
            </div>
        </div>

        <!-- ตารางรายการทวงวันนี้ -->
        <div class="card p-4 shadow-sm border-warning mb-4">
            <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
                <div class="d-flex align-items-center gap-3 flex-wrap">
                    <h4 class="mb-0 fs-5 text-danger fw-bold">{table_title}</h4>
                    {view_today_btn}
                </div>
                <form method="GET" class="d-flex align-items-center gap-2 flex-wrap">
                    <div class="d-flex align-items-center gap-1"><small class="text-muted">จาก:</small><input type="date" name="start_date" class="form-control form-control-sm" value="{start_date_str}"></div>
                    <div class="d-flex align-items-center gap-1"><small class="text-muted">ถึง:</small><input type="date" name="end_date" class="form-control form-control-sm" value="{end_date_str}"></div>
                    <div class="d-flex align-items-center gap-1"><input type="text" name="search" class="form-control form-control-sm" placeholder="ค้นหาชื่อ หรือเบอร์โทร..." value="{search_query}"></div>
                    <button type="submit" class="btn btn-sm btn-outline-danger">ค้นหา / เช็กยอด</button>
                </form>
            </div>
            
            <div class="table-responsive">
                <table class="table table-striped align-middle text-nowrap">
                    <thead class="table-dark">
                        <tr>
                            <th style="position: sticky; left: 0; background-color: #212529; z-index: 3; box-shadow: 2px 0 5px rgba(0,0,0,0.2);">ชื่อลูกค้า</th>
                            <th>เบอร์โทร</th>
                            <th>ประเภทการชำระ</th>
                            <th>บัญชีปล่อยกู้</th>
                            <th>วันที่กู้</th>
                            <th>ชำระล่าสุด</th>
                            <th>เงินลงทุน</th>
                            <th>ต้นคงค้าง</th>
                            <th>ยอดที่ชำระมาแล้ว</th>
                            <th>ดอกเบี้ย/วัน</th>
                            <th>เวลาผ่านไป</th>
                            <th>ดอกเบี้ยสะสม</th>
                            <th>สถานะ</th>
                            <th style="position: sticky; right: 0; background-color: #212529; z-index: 3; text-align: center; box-shadow: -2px 0 5px rgba(0,0,0,0.2);">จัดการ</th>
                        </tr>
                    </thead>
                    <tbody>{rows if rows else "<tr><td colspan='14' class='text-center text-muted'>ไม่มีรายการที่ต้องทวงในวันนี้</td></tr>"}</tbody>
                </table>
            </div>
        </div>

        <!-- Modal ยอดค้างเก่า -->
        <div class="modal fade" id="debtModal" tabindex="-1">
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content border-warning">
                    <div class="modal-header bg-warning text-dark py-2">
                        <h5 class="modal-title fw-bold fs-6">📂 รายละเอียด: ยอดค้างเก่าคงเหลือทั้งหมด ({total_debt_principal:,.2f} บาท)</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body" style="max-height: 65vh; overflow-y: auto;">
                        <div class="table-responsive">
                            <table class="table table-striped align-middle text-nowrap">
                                <thead class="table-dark"><tr><th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>วันที่ตั้งต้น</th><th>ยอดตั้งต้น</th><th>ยอดคงเหลือ</th></tr></thead>
                                <tbody>{debt_card_rows if debt_card_rows else "<tr><td colspan='5' class='text-center text-muted'>ไม่มีรายการยอดค้างเก่าที่ค้างอยู่</td></tr>"}</tbody>
                            </table>
                        </div>
                    </div>
                    <div class="modal-footer py-2"><button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ปิดหน้าต่าง</button></div>
                </div>
            </div>
        </div>

        <!-- Modal เงินต้นคงค้าง -->
        <div class="modal fade" id="principalModal" tabindex="-1">
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content border-danger">
                    <div class="modal-header bg-danger text-white py-2">
                        <h5 class="modal-title fw-bold fs-6">💼 รายละเอียด: เงินต้นคงค้างทั้งหมด ({total_new_principal:,.2f} บาท)</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body" style="max-height: 65vh; overflow-y: auto;">
                        <div class="table-responsive">
                            <table class="table table-striped align-middle text-nowrap">
                                <thead class="table-dark"><tr><th>ชื่อลูกค้า</th><th>ประเภท</th><th>เบอร์โทร</th><th>วันที่กู้</th><th>เงินลงทุน</th><th>ต้นคงค้าง</th></tr></thead>
                                <tbody>{new_principal_rows if new_principal_rows else "<tr><td colspan='6' class='text-center text-muted'>ไม่มีรายการเงินต้นคงค้างที่ค้างอยู่</td></tr>"}</tbody>
                            </table>
                        </div>
                    </div>
                    <div class="modal-footer py-2"><button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ปิดหน้าต่าง</button></div>
                </div>
            </div>
        </div>

        <!-- Modal กำไรสะสม -->
        <div class="modal fade" id="profitModal" tabindex="-1">
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content border-success">
                    <div class="modal-header bg-success text-white py-2">
                        <h5 class="modal-title fw-bold fs-6">💰 รายละเอียด: กำไรสะสมทั้งหมด เดือนปัจจุบัน ({current_month_profit:,.2f} บาท)</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body" style="max-height: 65vh; overflow-y: auto;">
                        <div class="table-responsive">
                            <table class="table table-striped align-middle text-nowrap">
                                <thead class="table-dark"><tr><th>ชื่อลูกค้า</th><th>ประเภท</th><th>กำไร/ดอกเบี้ย</th><th>ค่าปรับจริง</th><th>ส่วนลด</th><th>รวมสุทธิ</th><th>วันที่ชำระล่าสุด</th></tr></thead>
                                <tbody>{profit_card_rows if profit_card_rows else "<tr><td colspan='7' class='text-center text-muted'>ยังไม่มีกำไรสะสมในเดือนนี้</td></tr>"}</tbody>
                            </table>
                        </div>
                    </div>
                    <div class="modal-footer py-2"><button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ปิดหน้าต่าง</button></div>
                </div>
            </div>
        </div>
        {modals_html}
        """
        html = BASE_LAYOUT.replace('{% block header %}Dashboard{% endblock %}', '🔱 Dashboard บริหารจัดการระบบ')
        return render_template_string(html.replace('{% block content %}{% endblock %}', content), title="Dashboard", page="dashboard")
    except Exception as e:
        print("Index route error:", e)
        return f"""
        <div style="padding: 30px; font-family: Prompt, sans-serif;">
            <h3 style="color: #d9534f;">⚠️ เกิดข้อผิดพลาดในการโหลดหน้า Dashboard</h3>
            <p>ระบบกำลังพยายามสร้างตารางฐานข้อมูลอัตโนมัติ กรุณารีเฟรชหน้าเว็บอีกครั้ง (Error: {str(e)})</p>
            <a href="/" style="background: #d4af37; color: #fff; padding: 10px 20px; text-decoration: none; border-radius: 5px; font-weight: bold;">รีเฟรชหน้าเว็บ</a>
        </div>
        """

@app.route('/transfer_bank_money', methods=['POST'])
def transfer_bank_money():
    if 'admin' not in session: return redirect(url_for('login'))
    try:
        from_acc = request.form.get('from_account')
        to_acc = request.form.get('to_account')
        transfer_amt = float(request.form.get('transfer_amount', 0))
        note_text = request.form.get('note', '').strip()

        if from_acc == to_acc: return redirect(url_for('index'))

        if transfer_amt > 0:
            adj_from = BankAdjustment.query.filter_by(account_name=from_acc).first()
            if adj_from: adj_from.adjustment_amount = max(0.0, adj_from.adjustment_amount - transfer_amt)
            else: db.session.add(BankAdjustment(account_name=from_acc, adjustment_amount=0.0))

            adj_to = BankAdjustment.query.filter_by(account_name=to_acc).first()
            if adj_to: adj_to.adjustment_amount += transfer_amt
            else: db.session.add(BankAdjustment(account_name=to_acc, adjustment_amount=transfer_amt))

            db.session.add(BankExpenseLog(
                expense_date=get_thai_today(), account_name=f"{from_acc} ➡️ {to_acc}",
                amount=transfer_amt, note=f"[โยกเงินพักบัญชี] {note_text}", admin_name=session.get('admin')
            ))
            db.session.commit()
    except Exception as e:
        print("Transfer error:", e)
        db.session.rollback()
    db.session.remove()
    return redirect(url_for('index'))

@app.route('/update_bank_adjustment', methods=['POST'])
def update_bank_adjustment():
    if 'admin' not in session: return redirect(url_for('login'))
    try:
        krungsri_val = float(request.form.get('krungsri', 0))
        gsb_val = float(request.form.get('gsb', 0))
        wallet_val = float(request.form.get('wallet', 0))

        for acc_name, val in [('กรุงศรีอยุธยา', krungsri_val), ('ออมสิน', gsb_val), ('วอลเล็ท', wallet_val)]:
            adj = BankAdjustment.query.filter_by(account_name=acc_name).first()
            if adj: adj.adjustment_amount = val
            else: db.session.add(BankAdjustment(account_name=acc_name, adjustment_amount=val))
        db.session.commit()
    except Exception as e: print("Adjustment error:", e)
    db.session.remove()
    return redirect(url_for('index'))

@app.route('/withdraw_bank_money', methods=['POST'])
def withdraw_bank_money():
    if 'admin' not in session: return redirect(url_for('login'))
    try:
        acc_name = request.form.get('account_name', 'กรุงศรีอยุธยา')
        withdraw_amt = float(request.form.get('withdraw_amount', 0))
        note_text = request.form.get('note', '').strip()

        if withdraw_amt > 0:
            db.session.add(BankExpenseLog(
                expense_date=get_thai_today(), account_name=acc_name, amount=withdraw_amt, note=note_text, admin_name=session.get('admin')
            ))
            adj = BankAdjustment.query.filter_by(account_name=acc_name).first()
            if adj: adj.adjustment_amount = max(0.0, adj.adjustment_amount - withdraw_amt)
            else: db.session.add(BankAdjustment(account_name=acc_name, adjustment_amount=0.0))
            db.session.commit()
    except Exception as e: print("Withdraw error:", e)
    db.session.remove()
    return redirect(url_for('index'))

@app.route('/delete_expense/<int:exp_id>')
def delete_expense(exp_id):
    if 'admin' not in session: return redirect(url_for('login'))
    exp = BankExpenseLog.query.get_or_404(exp_id)
    if "➡️" in exp.account_name:
        parts = exp.account_name.split(" ➡️ ")
        if len(parts) == 2:
            from_acc, to_acc = parts[0], parts[1]
            adj_from = BankAdjustment.query.filter_by(account_name=from_acc).first()
            if adj_from: adj_from.adjustment_amount += exp.amount
            adj_to = BankAdjustment.query.filter_by(account_name=to_acc).first()
            if adj_to: adj_to.adjustment_amount = max(0.0, adj_to.adjustment_amount - exp.amount)
    else:
        adj = BankAdjustment.query.filter_by(account_name=exp.account_name).first()
        if adj: adj.adjustment_amount += exp.amount
    db.session.delete(exp)
    db.session.commit()
    db.session.remove()
    return redirect(url_for('index'))

@app.route('/customer_details/<path:cust_name>')
def customer_details(cust_name):
    if 'admin' not in session: return redirect(url_for('login'))
    txs = Transaction.query.filter_by(customer_name=cust_name).order_by(Transaction.start_date.desc()).all()
    for tx in txs: calculate_tx_values(tx)

    rows, modals_html = "", ""
    for tx in txs:
        badge_color = 'bg-success' if tx.principal <= 0 else ('bg-info text-dark' if tx.status == 'ตัดยอดบางส่วน' else 'bg-success')
        if tx.principal <= 0 or tx.status == 'คืนแล้ว': badge_color = 'bg-danger'
        start_date_str = tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'
        last_pay_str = tx.last_payment_date.strftime('%d/%m/%Y') if tx.last_payment_date else '-'
        closed_date_str = tx.closed_date.strftime('%Y-%m-%d') if tx.closed_date else ''

        rows += f"""
        <tr>
            <td><span class="badge bg-secondary">{tx.type}</span></td>
            <td><span class="badge bg-warning text-dark">{tx.funding_source or 'กรุงศรีอยุธยา'}</span></td>
            <td>{start_date_str}</td>
            <td>{last_pay_str}</td>
            <td>{tx.original_principal:,.2f}</td>
            <td>{tx.principal:,.2f}</td>
            <td><strong class="text-primary">{tx.total_paid:,.2f}</strong></td>
            <td>{tx.daily_interest:,.2f}</td>
            <td class="text-danger fw-bold">{tx.accumulated_interest:,.2f}</td>
            <td><span class="badge {badge_color}">{'คืนแล้ว' if tx.principal <= 0 else tx.status}</span></td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-2">
                    <button type="button" class="btn btn-sm btn-success-light fw-bold px-2" data-bs-toggle="modal" data-bs-target="#payModal{tx.id}">จัดการยอด</button>
                    <a href="/delete_tx/{tx.id}" class="btn btn-sm btn-danger fw-bold px-2" onclick="return confirm('ยืนยันการลบบิลนี้?')">ลบ</a>
                </div>
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
                                        <option value="adjust">ปรับปรุงยอด</option>
                                    </select>
                                </div>
                                <div class="mb-1" id="amountDiv{tx.id}">
                                    <label class="form-label fw-bold text-primary mb-1" style="font-size: 0.85rem;">💵 จำนวนเงินที่รับชำระจริง (บาท)</label>
                                    <input type="number" step="any" name="pay_amount" class="form-control form-control-sm border-primary shadow-sm bg-white" placeholder="กรอกจำนวนเงินสดที่รับจริง">
                                </div>
                                <div class="mb-1" id="adjustContainer{tx.id}" style="display: none;">
                                    <label class="form-label fw-bold text-dark mb-1" style="font-size: 0.85rem;">⚙️ จำนวนเงินปรับปรุงต้น (บาท)</label>
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
                                <button type="submit" class="btn btn-success-light btn-sm fw-bold px-3">บันทึก</button>
                            </div>
                        </div>
                    </form>
                </div>
            </div>
        </div>
        """

    content = f"""
    <div class="card p-4 shadow-sm border-warning">
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <div>
                <h4 class="mb-0 fs-5 text-danger fw-bold">👤 รายละเอียดบัญชีทั้งหมดของ: {cust_name}</h4>
                <small class="text-muted">ลูกค้ารายนี้มีทั้งหมด <b>{len(txs)}</b> รายการในระบบ</small>
            </div>
            <a href="/" class="btn btn-sm btn-secondary fw-bold">⬅️ กลับหน้าหลัก</a>
        </div>
        <div class="table-responsive">
            <table class="table table-striped align-middle text-nowrap">
                <thead class="table-dark">
                    <tr><th>ประเภทบัญชี</th><th>บัญชีปล่อยกู้</th><th>วันที่กู้</th><th>ชำระล่าสุด</th><th>เงินลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th><th>ดอก/วัน</th><th>ดอกเบี้ยสะสม</th><th>สถานะ</th><th class="text-center">จัดการ</th></tr>
                </thead>
                <tbody>{rows if rows else "<tr><td colspan='11' class='text-center text-muted'>ไม่พบข้อมูลรายการของลูกค้ารายนี้</td></tr>"}</tbody>
            </table>
        </div>
    </div>
    {modals_html}
    """
    html = BASE_LAYOUT.replace('{% block header %}รายละเอียดลูกค้า {cust_name}{% endblock %}', f'รายละเอียดลูกค้า {cust_name}').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title=f"ลูกค้า: {cust_name}", page="dashboard")

@app.route('/monthly_summary')
def monthly_summary():
    if 'admin' not in session: return redirect(url_for('login'))
    
    all_txs_ever = Transaction.query.all()
    all_histories = PaymentHistory.query.all()
    
    monthly_data = defaultdict(lambda: {'count_tx': set(), 'new_investment': 0.0, 'month_profit': 0.0})
    
    for h in all_histories:
        if h.payment_date and h.transaction_id and h.transaction:
            ym = h.payment_date.strftime('%Y-%m')
            h_interest = h.interest_paid if h.transaction.type != 'ยอดค้างเก่า' else (h.interest_paid if h.interest_paid > 0 else 0.0)
            h_profit = h_interest + h.fine_amount - h.discount_amount
            monthly_data[ym]['month_profit'] += h_profit
            monthly_data[ym]['count_tx'].add(h.transaction_id)

    for tx in all_txs_ever:
        if tx.start_date:
            ym_start = tx.start_date.strftime('%Y-%m')
            if tx.type != 'ยอดค้างเก่า':
                monthly_data[ym_start]['new_investment'] += tx.original_principal
            monthly_data[ym_start]['count_tx'].add(tx.id)

    cards_html = ""
    thai_months = {"01": "มกราคม", "02": "กุมภาพันธ์", "03": "มีนาคม", "04": "เมษายน", "05": "พฤษภาคม", "06": "มิถุนายน", "07": "กรกฎาคม", "08": "สิงหาคม", "09": "กันยายน", "10": "ตุลาคม", "11": "พฤศจิกายน", "12": "ธันวาคม"}
    
    for ym, d in sorted(monthly_data.items(), reverse=True):
        if d['new_investment'] > 0 or d['month_profit'] > 0:
            parts = ym.split('-')
            m_label = f"{thai_months.get(parts[1], parts[1])} {int(parts[0])+543}"
            num_items = len(d['count_tx'])
            cards_html += f"""
            <div class="col-md-4 mb-3">
                <div class="card p-3 shadow-sm border-warning bg-white">
                    <h5 class="text-danger fw-bold mb-2">📁 ประจำเดือน {m_label}</h5>
                    <p class="mb-1 text-muted">จำนวนรายการที่เกี่ยวข้อง: <b class="text-dark">{num_items} รายการ</b></p>
                    <p class="mb-1 text-muted">ยอดปล่อยกู้ (เดือนนี้): <b class="text-primary">{d['new_investment']:,.2f} บาท</b></p>
                    <p class="mb-3 text-muted">กำไรสุทธิ (ตามวันชำระ): <b class="text-success">{d['month_profit']:,.2f} บาท</b></p>
                    <a href="/monthly_details/{ym}/profit" class="btn btn-warning btn-sm fw-bold">🔍 เปิดแฟ้มดูรายละเอียด</a>
                </div>
            </div>
            """
    content = f"""<div class="row">{cards_html if cards_html else "<p class='text-center text-muted'>ยังไม่มีข้อมูลในกล่องแฟ้ม</p>"}</div>"""
    html = BASE_LAYOUT.replace('{% block header %}4. สรุปยอดผลประกอบการรายเดือน{% endblock %}', '📁 กล่องแฟ้มรายเดือน (Monthly Summary)').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="สรุปยอดรายเดือน", page="monthly")

@app.route('/monthly_details/<ym>/<category>')
def monthly_details(ym, category):
    if 'admin' not in session: return redirect(url_for('login'))
    try:
        year_val, month_val = ym.split('-')
        year_i, month_i = int(year_val), int(month_val)
    except: return redirect(url_for('monthly_summary'))

    all_histories = PaymentHistory.query.all()
    target_tx_ids = set()

    for h in all_histories:
        if h.payment_date and h.payment_date.year == year_i and h.payment_date.month == month_i:
            if h.transaction_id and h.transaction:
                target_tx_ids.add(h.transaction_id)

    for tx in Transaction.query.all():
        if tx.start_date and tx.start_date.year == year_i and tx.start_date.month == month_i:
            target_tx_ids.add(tx.id)

    txs = Transaction.query.filter(Transaction.id.in_(list(target_tx_ids))).all() if target_tx_ids else []
    thai_months = {"01": "มกราคม", "02": "กุมภาพันธ์", "03": "มีนาคม", "04": "มิถุนายน", "05": "พฤษภาคม", "06": "มิถุนายน", "07": "กรกฎาคม", "08": "สิงหาคม", "09": "กันยายน", "10": "ตุลาคม", "11": "พฤศจิกายน", "12": "ธันวาคม"}
    m_label = f"{thai_months.get(month_val, month_val)} {year_i+543}"
    title_str = f"แฟ้มรายละเอียด ประจำเดือน {m_label}"

    rows, total_actual_paid_sum, total_inv_sum, total_prin_sum = "", 0.0, 0.0, 0.0
    for tx in txs:
        calculate_tx_values(tx)
        badge_color = 'bg-success' if tx.principal <= 0 else ('bg-info text-dark' if tx.status == 'ตัดยอดบางส่วน' else 'bg-success')
        if tx.principal <= 0 or tx.status == 'คืนแล้ว': badge_color = 'bg-danger'
        start_date_str = tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'
        closed_date_str = tx.closed_date.strftime('%d/%m/%Y') if tx.closed_date else '-'
        
        actual_paid_total = sum((h.pay_amount if h.pay_amount > 0 else (h.interest_paid + h.principal_reduced + h.fine_amount - h.discount_amount)) for h in tx.histories if h.payment_date and h.payment_date.year == year_i and h.payment_date.month == month_i) if tx.histories else 0.0
        total_actual_paid_sum += actual_paid_total
        total_inv_sum += tx.original_principal if (tx.start_date and tx.start_date.year == year_i and tx.start_date.month == month_i) else 0.0
        total_prin_sum += tx.principal

        rows += f"""
        <tr>
            <td style="font-weight: 500;"><a href="/customer_details/{tx.customer_name}" class="text-dark text-decoration-none fw-bold">{tx.customer_name}</a></td>
            <td>{tx.phone or '-'}</td>
            <td><span class="badge bg-secondary">{tx.type}</span></td>
            <td><span class="badge bg-warning text-dark">{tx.funding_source or 'กรุงศรีอยุธยา'}</span></td>
            <td>{start_date_str}</td>
            <td>{closed_date_str}</td>
            <td>{tx.original_principal:,.2f}</td>
            <td>{tx.principal:,.2f}</td>
            <td><strong class="text-primary">{tx.total_paid:,.2f}</strong></td>
            <td><strong class="text-success">{actual_paid_total:,.2f}</strong></td>
            <td><span class="badge {badge_color}">{'คืนแล้ว' if tx.principal <= 0 else tx.status}</span></td>
            <td class="text-center"><a href="/customer_details/{tx.customer_name}" class="btn btn-sm btn-success-light">ดูประวัติ</a></td>
        </tr>
        """
    rows += f"""<tr class="table-dark fw-bold"><td colspan="6" class="text-end">รวมทั้งสิ้น:</td><td>{total_inv_sum:,.2f}</td><td>{total_prin_sum:,.2f}</td><td>-</td><td class="text-success">{total_actual_paid_sum:,.2f}</td><td colspan="2"></td></tr>"""

    content = f"""
    <div class="card p-4 shadow-sm border-warning">
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <h4 class="mb-0 fs-5 text-danger fw-bold">📋 {title_str}</h4>
            <a href="/monthly_summary" class="btn btn-sm btn-secondary fw-bold">⬅️ กลับไปหน้ากล่องแฟ้มรายเดือน</a>
        </div>
        <div class="table-responsive">
            <table class="table table-striped align-middle text-nowrap">
                <thead class="table-dark">
                    <tr><th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>ประเภท</th><th>บัญชีปล่อยกู้</th><th>วันที่กู้</th><th>วันที่ปิด/ชำระ</th><th>เงินลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว (ระบบ)</th><th>ยอดจ่ายจริงทั้งหมด</th><th>สถานะ</th><th class="text-center">จัดการ</th></tr>
                </thead>
                <tbody>{rows if txs else "<tr><td colspan='12' class='text-center text-muted'>ไม่มีรายการในหมวดนี้สำหรับเดือนนี้</td></tr>"}</tbody>
            </table>
        </div>
    </div>
    """
    html = BASE_LAYOUT.replace('{% block header %}รายละเอียดประจำเดือน{% endblock %}', title_str).replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title=title_str, page="monthly")

@app.route('/check_orphaned_payments')
def check_orphaned_payments():
    if 'admin' not in session: return redirect(url_for('login'))
    
    all_histories = PaymentHistory.query.all()
    orphaned_rows = ""
    
    for h in all_histories:
        if not h.transaction_id or not h.transaction:
            h_interest = h.interest_paid
            h_profit = h_interest + h.fine_amount - h.discount_amount
            p_date_str = h.payment_date.strftime('%d/%m/%Y') if h.payment_date else '-'
            
            orphaned_rows += f"""
            <tr>
                <td>{h.id}</td>
                <td>{h.transaction_id or 'ไม่มี ID บิล'}</td>
                <td>{p_date_str}</td>
                <td class="text-danger fw-bold">{h_profit:,.2f} บาท</td>
                <td>{h.note or '-'}</td>
                <td><span class="badge bg-secondary">{h.admin_name or '-'}</span></td>
                <td><a href="/delete_orphaned_history/{h.id}" class="btn btn-sm btn-danger" onclick="return confirm('ยืนยันลบประวัติค้างนี้ทิ้ง?')">ลบประวัติขยะนี้</a></td>
            </tr>
            """

    content = f"""
    <div class="card p-4 shadow-sm border-danger">
        <h4 class="mb-3 text-danger fw-bold">🗑️ ตรวจสอบประวัติการชำระเงินที่ตกค้าง (ไม่มีบิลหลักรองรับ)</h4>
        <p class="text-muted">รายการเหล่านี้คือประวัติการจ่ายเงินที่ตัวบิลหลักถูกลบออกจากระบบไปแล้ว แต่ประวัติด้านในยังค้างอยู่</p>
        <div class="table-responsive">
            <table class="table table-striped align-middle text-nowrap">
                <thead class="table-dark">
                    <tr><th>ID ประวัติ</th><th>ID บิลเดิม</th><th>วันที่ทำรายการ</th><th>ยอดเงินสุทธิ (กำไร/ค่าปรับ)</th><th>หมายเหตุ</th><th>ผู้บันทึก</th><th>จัดการ</th></tr>
                </thead>
                <tbody>
                    {orphaned_rows if orphaned_rows else "<tr><td colspan='7' class='text-center text-success fw-bold'>ยอดเยี่ยม! ไม่พบประวัติการชำระเงินตกค้างในระบบ ทุกอย่างสะอาดเรียบร้อยดี</td></tr>"}
                </tbody>
            </table>
        </div>
        <div class="mt-3">
            <a href="/" class="btn btn-secondary btn-sm fw-bold">⬅️ กลับหน้าหลัก</a>
        </div>
    </div>
    """
    html = BASE_LAYOUT.replace('{% block header %}ตรวจสอบประวัติค้าง{% endblock %}', 'ตรวจสอบประวัติค้าง').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="ตรวจสอบประวัติค้าง", page="dashboard")

@app.route('/delete_orphaned_history/<int:hid>')
def delete_orphaned_history(hid):
    if 'admin' not in session: return redirect(url_for('login'))
    h_item = PaymentHistory.query.get_or_404(hid)
    db.session.delete(h_item)
    db.session.commit()
    db.session.remove()
    return redirect(url_for('check_orphaned_payments'))

@app.route('/members')
def members():
    if 'admin' not in session: return redirect(url_for('login'))
    txs = Transaction.query.filter(Transaction.principal > 0).order_by(Transaction.customer_name.asc()).all()
    rows = ""
    for t in txs:
        calculate_tx_values(t)
        s_date = t.start_date.strftime('%d/%m/%Y') if t.start_date else '-'
        sched_badge = f'<span class="badge bg-dark">{t.schedule_type}</span>'
        status_color = 'bg-success' if t.status == 'ปกติ' else ('bg-danger' if t.status == 'คืนแล้ว' else 'bg-secondary')
        rows += f"<tr><td><a href='/customer_details/{t.customer_name}' class='text-dark text-decoration-none fw-bold'>{t.customer_name}</a></td><td>{t.phone or '-'}</td><td><span class='badge bg-danger'>{t.sales_name}</span></td><td><span class='badge bg-warning text-dark'>{t.funding_source or 'กรุงศรีอยุธยา'}</span></td><td>{sched_badge}</td><td>{s_date}</td><td>{t.original_principal:,.2f}</td><td>{t.principal:,.2f}</td><td><strong>{t.total_paid:,.2f}</strong></td><td><span class='badge {status_color}'>{t.status}</span></td></tr>"
    content = f"""<div class="card p-4 shadow-sm border-warning"><h4 class="mb-3 fs-5 text-danger fw-bold">👥 สมาชิกทั้งหมดในระบบ (ยังไม่ปิดบัญชี)</h4><div class="table-responsive"><table class="table table-striped text-nowrap align-middle"><thead class="table-dark"><tr><th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>เซลล์</th><th>บัญชีปล่อย</th><th>ประเภท</th><th>วันที่กู้</th><th>ลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th><th>สถานะ</th></tr></thead><tbody>{rows if rows else "<tr><td colspan='10' class='text-center text-muted'>ยังไม่มีข้อมูลสมาชิก</td></tr>"}</tbody></table></div></div>"""
    html = BASE_LAYOUT.replace('{% block header %}สมาชิกทั้งหมด{% endblock %}', 'สมาชิกทั้งหมด').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="สมาชิกทั้งหมด", page="members")

@app.route('/all_transactions')
def all_transactions():
    if 'admin' not in session: return redirect(url_for('login'))
    search_query = request.args.get('search', '').strip()
    active_tab = request.args.get('tab', 'daily')
    
    query = Transaction.query
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter((Transaction.customer_name.ilike(search_pattern)) | (Transaction.phone.ilike(search_pattern)))
    
    transactions = query.all()
    for tx in transactions: calculate_tx_values(tx)

    daily_txs = [t for t in transactions if t.principal > 0 and t.schedule_type == 'จ่ายทุกวัน']
    unscheduled_txs = [t for t in transactions if t.principal > 0 and t.schedule_type == 'ยังไม่มีกำหนดจ่าย']
    monthly_txs = [t for t in transactions if t.principal > 0 and t.schedule_type == 'กำหนดจ่ายประจำเดือน']
    closed_txs = [t for t in transactions if t.principal <= 0]

    def build_rows(tx_list, is_closed=False):
        res = ""
        for tx in tx_list:
            badge_color = 'bg-danger' if is_closed else ('bg-success' if tx.status == 'ปกติ' else ('bg-info text-dark' if tx.status == 'ตัดยอดบางส่วน' else 'bg-danger'))
            start_date_str = tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'
            last_pay_str = tx.last_payment_date.strftime('%d/%m/%Y') if tx.last_payment_date else '-'
            
            schedule_badge = f'<span class="badge bg-dark">{tx.schedule_type}</span>'
            if tx.schedule_type == 'กำหนดจ่ายประจำเดือน' and tx.due_day_of_month:
                code_map = {"2": "29-2", "6": "4-6", "12": "9-12", "16": "14-16", "23": "20-23", "26": "24-26"}
                labels = [code_map.get(c, c) for c in tx.due_day_of_month.split(',')]
                schedule_badge = f'<span class="badge bg-primary">รอบ: {", ".join(labels)}</span>'

            res += f"""
            <tr>
                <td style="position: sticky; left: 0; background-color: #fff; z-index: 2; font-weight: 500; box-shadow: 2px 0 5px rgba(0,0,0,0.05);">
                    <a href="/customer_details/{tx.customer_name}" class="text-dark text-decoration-none fw-bold">{tx.customer_name}</a>
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
                <td>{tx.accumulated_interest:,.2f}</td>
                <td><span class="badge {badge_color}">{'คืนแล้ว' if is_closed else tx.status}</span></td>
                <td><a href="/" class="btn btn-sm btn-success-light">จัดการ</a></td>
            </tr>
            """
        return res

    daily_rows = build_rows(daily_txs, False)
    unscheduled_rows = build_rows(unscheduled_txs, False)
    monthly_rows = build_rows(monthly_txs, False)
    closed_rows = build_rows(closed_txs, True)

    daily_active_cls = "active bg-warning text-dark" if active_tab == 'daily' else "text-dark"
    unscheduled_active_cls = "active bg-warning text-dark" if active_tab == 'unscheduled' else "text-dark"
    monthly_active_cls = "active bg-warning text-dark" if active_tab == 'monthly' else "text-dark"
    closed_active_cls = "active bg-secondary text-white" if active_tab == 'closed' else "text-dark"

    daily_div_cls = "" if active_tab == 'daily' else "d-none"
    unscheduled_div_cls = "" if active_tab == 'unscheduled' else "d-none"
    monthly_div_cls = "" if active_tab == 'monthly' else "d-none"
    closed_div_cls = "" if active_tab == 'closed' else "d-none"

    content = f"""
    <div class="card p-4 shadow-sm border-warning mb-4">
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <h4 class="mb-0 fs-5 text-danger fw-bold">📋 รายการทั้งหมด (แบ่งตามประเภทการจ่าย)</h4>
            <form method="GET" class="d-flex align-items-center gap-1">
                <input type="hidden" name="tab" value="{active_tab}">
                <input type="text" name="search" class="form-control form-control-sm" placeholder="ค้นหาชื่อ หรือเบอร์โทร..." value="{search_query}">
                <button type="submit" class="btn btn-sm btn-outline-danger">ค้นหา</button>
            </form>
        </div>

        <ul class="nav nav-tabs mb-3">
            <li class="nav-item">
                <a class="nav-link fw-bold {daily_active_cls}" href="/all_transactions?tab=daily">🔸 1.1 จ่ายทุกวัน ({len(daily_txs)})</a>
            </li>
            <li class="nav-item">
                <a class="nav-link fw-bold {unscheduled_active_cls}" href="/all_transactions?tab=unscheduled">🔸 1.2 ยังไม่มีกำหนดจ่าย ({len(unscheduled_txs)})</a>
            </li>
            <li class="nav-item">
                <a class="nav-link fw-bold {monthly_active_cls}" href="/all_transactions?tab=monthly">🔸 1.3 กำหนดจ่ายประจำเดือน ({len(monthly_txs)})</a>
            </li>
            <li class="nav-item">
                <a class="nav-link fw-bold {closed_active_cls}" href="/all_transactions?tab=closed">📁 ประวัติปิดบัญชีแล้ว ({len(closed_txs)})</a>
            </li>
        </ul>

        <div class="tab-content">
            <div class="table-responsive {daily_div_cls}">
                <h6 class="text-danger fw-bold mb-2">🔸 รายการประเภท: จ่ายทุกวัน (ทวงทุกวัน)</h6>
                <table class="table table-striped align-middle text-nowrap">
                    <thead class="table-dark">
                        <tr>
                            <th style="position: sticky; left: 0; background-color: #212529; z-index: 3;">ชื่อลูกค้า</th>
                            <th>เบอร์โทร</th><th>ประเภท</th><th>บัญชีปล่อย</th><th>วันที่กู้</th><th>ชำระล่าสุด</th><th>เงินลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th><th>ดอก/วัน</th><th>ดอกสะสม</th><th>สถานะ</th><th>จัดการ</th>
                        </tr>
                    </thead>
                    <tbody>{daily_rows if daily_rows else "<tr><td colspan='13' class='text-center text-muted'>ไม่มีรายการในหมวดนี้</td></tr>"}</tbody>
                </table>
            </div>

            <div class="table-responsive {unscheduled_div_cls}">
                <h6 class="text-danger fw-bold mb-2">🔸 รายการประเภท: ยังไม่มีกำหนดจ่าย</h6>
                <table class="table table-striped align-middle text-nowrap">
                    <thead class="table-dark">
                        <tr>
                            <th style="position: sticky; left: 0; background-color: #212529; z-index: 3;">ชื่อลูกค้า</th>
                            <th>เบอร์โทร</th><th>ประเภท</th><th>บัญชีปล่อย</th><th>วันที่กู้</th><th>ชำระล่าสุด</th><th>เงินลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th><th>ดอก/วัน</th><th>ดอกสะสม</th><th>สถานะ</th><th>จัดการ</th>
                        </tr>
                    </thead>
                    <tbody>{unscheduled_rows if unscheduled_rows else "<tr><td colspan='13' class='text-center text-muted'>ไม่มีรายการในหมวดนี้</td></tr>"}</tbody>
                </table>
            </div>

            <div class="table-responsive {monthly_div_cls}">
                <h6 class="text-danger fw-bold mb-2">🔸 รายการประเภท: กำหนดจ่ายประจำเดือน</h6>
                <table class="table table-striped align-middle text-nowrap">
                    <thead class="table-dark">
                        <tr>
                            <th style="position: sticky; left: 0; background-color: #212529; z-index: 3;">ชื่อลูกค้า</th>
                            <th>เบอร์โทร</th><th>ประเภท</th><th>บัญชีปล่อย</th><th>วันที่กู้</th><th>ชำระล่าสุด</th><th>เงินลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th><th>ดอก/วัน</th><th>ดอกสะสม</th><th>สถานะ</th><th>จัดการ</th>
                        </tr>
                    </thead>
                    <tbody>{monthly_rows if monthly_rows else "<tr><td colspan='13' class='text-center text-muted'>ไม่มีรายการในหมวดนี้</td></tr>"}</tbody>
                </table>
            </div>

            <div class="table-responsive {closed_div_cls}">
                <h6 class="text-secondary fw-bold mb-2">📁 ประวัติบัญชีที่ปิดแล้ว (คืนครบทั้งหมด)</h6>
                <table class="table table-striped align-middle text-nowrap">
                    <thead class="table-secondary">
                        <tr>
                            <th style="position: sticky; left: 0; background-color: #e2e3e5; z-index: 3;">ชื่อลูกค้า</th>
                            <th>เบอร์โทร</th><th>ประเภท</th><th>บัญชีปล่อย</th><th>วันที่กู้</th><th>ชำระล่าสุด</th><th>เงินลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th><th>ดอก/วัน</th><th>ดอกสะสม</th><th>สถานะ</th><th>จัดการ</th>
                        </tr>
                    </thead>
                    <tbody>{closed_rows if closed_rows else "<tr><td colspan='13' class='text-center text-muted'>ยังไม่มีบัญชีที่ปิดแล้ว</td></tr>"}</tbody>
                </table>
            </div>
        </div>
    </div>
    """
    html = BASE_LAYOUT.replace('{% block header %}รายการทั้งหมด{% endblock %}', 'รายการทั้งหมด').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="รายการทั้งหมด", page="all")

@app.route('/export_data')
def export_data():
    if 'admin' not in session: return redirect(url_for('login'))
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Type', 'CustomerName', 'Phone', 'SalesName', 'StartDate', 'ClosedDate', 'OriginalPrincipal', 'Principal', 'DailyInterest', 'PaidInterest', 'Status', 'InstallmentAmount', 'TotalPaid', 'ScheduleType', 'DueDayOfMonth', 'TotalFine', 'TotalDiscount', 'FundingSource', 'StartNextDay'])
    
    for t in Transaction.query.order_by(Transaction.customer_name.asc()).all():
        total_paid = (t.original_principal - t.principal) if t.type == 'ยอดค้างเก่า' else t.paid_interest
        tx_fine_sum = sum(h.fine_amount for h in t.histories) if t.histories else 0.0
        tx_discount_sum = sum(h.discount_amount for h in t.histories) if t.histories else 0.0
        
        cw.writerow([
            t.id, t.type, t.customer_name, t.phone, t.sales_name, 
            t.start_date, t.closed_date, t.original_principal, t.principal, 
            t.daily_interest, t.paid_interest, t.status, t.installment_amount, 
            total_paid, t.schedule_type, t.due_day_of_month, 
            tx_fine_sum, tx_discount_sum, t.funding_source, t.start_next_day
        ])
        
    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name=f"sublon_backup_{get_thai_today().strftime('%Y%m%d_%H%M%S')}.csv")

@app.route('/import_data', methods=['POST'])
def import_data():
    if 'admin' not in session: return redirect(url_for('login'))
    file = request.files.get('file')
    if file and file.filename.endswith('.csv'):
        try:
            stream = io.TextIOWrapper(file.stream, encoding='utf-8-sig')
            reader = csv.DictReader(stream)
            for row in reader:
                s_date = get_thai_today()
                if row.get('StartDate'):
                    try: s_date = datetime.strptime(row['StartDate'].split()[0], '%Y-%m-%d').date()
                    except: 
                        try: s_date = datetime.strptime(row['StartDate'].split()[0], '%d/%m/%Y').date()
                        except: pass
                c_date = None
                if row.get('ClosedDate'):
                    try: c_date = datetime.strptime(row['ClosedDate'].split()[0], '%Y-%m-%d').date()
                    except: pass
                
                day_val = row.get('DueDayOfMonth') if row.get('DueDayOfMonth') and row.get('DueDayOfMonth') != 'None' else None
                funding = row.get('FundingSource', 'กรุงศรีอยุธยา')
                s_next_day = True if str(row.get('StartNextDay', '')).lower() in ['true', '1', 'yes'] else False

                new_t = Transaction(
                    type=row.get('Type', 'เงินฉุกเฉิน'), customer_name=row.get('CustomerName', 'ไม่ระบุ'),
                    phone=row.get('Phone', ''), sales_name=row.get('SalesName', session.get('admin')),
                    start_date=s_date, closed_date=c_date, original_principal=float(row.get('OriginalPrincipal', 0)),
                    principal=float(row.get('Principal', 0)), daily_interest=float(row.get('DailyInterest', 0)),
                    initial_daily_interest=float(row.get('DailyInterest', 0)), paid_interest=float(row.get('PaidInterest', 0)),
                    status=row.get('Status', 'ปกติ'), installment_amount=float(row.get('InstallmentAmount', 0)),
                    schedule_type=row.get('ScheduleType', 'จ่ายทุกวัน'), due_day_of_month=day_val,
                    funding_source=funding, start_next_day=s_next_day
                )
                db.session.add(new_t)
                db.session.flush()

                total_fine_val = float(row.get('TotalFine', 0) or 0)
                total_discount_val = float(row.get('TotalDiscount', 0) or 0)
                if total_fine_val > 0 or total_discount_val > 0:
                    db.session.add(PaymentHistory(
                        transaction_id=new_t.id, payment_date=s_date, pay_amount=total_fine_val,
                        fine_amount=total_fine_val, discount_amount=total_discount_val, interest_paid=0.0,
                        principal_reduced=0.0, note="นำเข้าข้อมูลสะสมจาก Backup CSV", admin_name=session.get('admin'),
                        receiving_account="กรุงศรีอยุธยา"
                    ))
            db.session.commit()
            db.session.remove()
        except Exception as e: print("Import error:", e)
    return redirect(url_for('index'))

@app.route('/update_payment/<int:tx_id>', methods=['POST'])
def update_payment(tx_id):
    if 'admin' not in session: return redirect(url_for('login'))
    tx = Transaction.query.get_or_404(tx_id)
    payment_type = request.form.get('payment_type')
    receiving_account = request.form.get('receiving_account', 'กรุงศรีอยุธยา')
    thai_today = get_thai_today()
    
    pay_amount_input = request.form.get('pay_amount', '').strip()
    pay_amount = float(pay_amount_input) if pay_amount_input != '' else 0.0
    
    discount_amt = float(request.form.get('discount_amount', 0))
    fine_amt = float(request.form.get('fine_amount', 0))
    closed_date_str = request.form.get('closed_date')
    note_text = request.form.get('note', '').strip()
    
    tx.closed_date = datetime.strptime(closed_date_str, '%Y-%m-%d').date() if closed_date_str else None
    calc_end_date = tx.closed_date if tx.closed_date else thai_today
    days = (calc_end_date - tx.start_date).days + 1
    if tx.start_next_day:
        days -= 1
    if days < 0: days = 0
        
    current_effective_daily = tx.initial_daily_interest * (tx.principal / tx.original_principal) if tx.original_principal > 0 else tx.daily_interest
    total_acc_interest = (current_effective_daily * days) - tx.paid_interest
    if total_acc_interest < 0: total_acc_interest = 0.0

    tx.last_payment_date = thai_today
    actual_interest_paid, actual_principal_reduced = 0.0, 0.0

    if payment_type == 'adjust':
        adjust_amount = float(request.form.get('adjust_amount', 0))
        tx.principal += adjust_amount
        if tx.principal < 0: tx.principal = 0.0
        actual_principal_reduced = -adjust_amount
        if pay_amount <= 0: pay_amount = abs(adjust_amount)
        if not note_text: note_text = f"ปรับปรุงยอดเงินต้น: {adjust_amount:+,.2f}"

    elif payment_type == 'full':
        net_interest_earned = total_acc_interest - discount_amt
        if net_interest_earned < 0: net_interest_earned = 0.0
        tx.paid_interest += net_interest_earned
        actual_interest_paid = net_interest_earned
        actual_principal_reduced = tx.principal
        if pay_amount <= 0: pay_amount = net_interest_earned + tx.principal
        tx.principal = 0.0
        tx.status = 'คืนแล้ว'
        if not tx.closed_date: tx.closed_date = thai_today
    else:
        net_acc_interest = total_acc_interest - discount_amt
        if net_acc_interest < 0: net_acc_interest = 0.0

        if pay_amount > 0:
            if pay_amount >= net_acc_interest:
                actual_interest_paid = net_acc_interest
                remainder = pay_amount - net_acc_interest
                tx.paid_interest += net_acc_interest
                if remainder > 0:
                    tx.principal -= remainder
                    actual_principal_reduced = remainder
                    if tx.principal < 0: tx.principal = 0.0
            else:
                tx.paid_interest += pay_amount
                actual_interest_paid = pay_amount
        else:
            actual_interest_paid = net_acc_interest
            pay_amount = actual_interest_paid + fine_amt

        if tx.principal <= 0:
            tx.status = 'คืนแล้ว'
            tx.principal = 0.0
            if not tx.closed_date: tx.closed_date = thai_today
        elif tx.principal < tx.original_principal:
            tx.status = 'ตัดยอดบางส่วน'

    total_net_pay = pay_amount if pay_amount > 0 else (actual_interest_paid + actual_principal_reduced + fine_amt - discount_amt)
    if total_net_pay < 0: total_net_pay = 0.0

    db.session.add(PaymentHistory(
        transaction_id=tx.id, payment_date=thai_today, pay_amount=total_net_pay,
        fine_amount=fine_amt, discount_amount=discount_amt, interest_paid=actual_interest_paid,
        principal_reduced=actual_principal_reduced, note=note_text or f"ชำระเงินประเภท: {payment_type}", admin_name=session.get('admin'),
        receiving_account=receiving_account
    ))

    if total_net_pay > 0 and receiving_account in ['กรุงศรีอยุธยา', 'ออมสิน', 'วอลเล็ท']:
        adj_bank = BankAdjustment.query.filter_by(account_name=receiving_account).first()
        if adj_bank: adj_bank.adjustment_amount += total_net_pay
        else: db.session.add(BankAdjustment(account_name=receiving_account, adjustment_amount=total_net_pay))

    db.session.commit()
    db.session.remove()
    return redirect(request.referrer or url_for('index'))

@app.route('/delete_tx/<int:tx_id>')
def delete_tx(tx_id):
    if 'admin' not in session: return redirect(url_for('login'))
    db.session.delete(Transaction.query.get_or_404(tx_id))
    db.session.commit()
    db.session.remove()
    return redirect(request.referrer or url_for('index'))

@app.route('/history/<int:tx_id>')
def payment_history(tx_id):
    if 'admin' not in session: return redirect(url_for('login'))
    tx = Transaction.query.get_or_404(tx_id)
    histories = PaymentHistory.query.filter_by(transaction_id=tx.id).order_by(PaymentHistory.payment_date.desc()).all()
    
    if not histories and (tx.original_principal > tx.principal or tx.paid_interest > 0):
        dummy_principal_diff = max(0.0, tx.original_principal - tx.principal)
        rows = f"<tr><td>{tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'}</td><td class='text-primary fw-bold'>{(tx.paid_interest + dummy_principal_diff):,.2f}</td><td><span class='badge bg-info text-dark'>{tx.funding_source or 'กรุงศรีอยุธยา'}</span></td><td class='text-danger'>0.00</td><td class='text-warning text-dark'>0.00</td><td>{tx.paid_interest:,.2f}</td><td>{dummy_principal_diff:,.2f}</td><td>ประวัติสะสมเดิม (ก่อนอัปเดตระบบ)</td><td><span class='badge bg-secondary'>ระบบ</span></td></tr>"
    else:
        rows = ""
        for h in histories:
            display_pay = h.pay_amount if h.pay_amount > 0 else (h.interest_paid + h.principal_reduced + h.fine_amount - h.discount_amount)
            if display_pay < 0: display_pay = 0.0
            rows += f"<tr><td>{h.payment_date.strftime('%d/%m/%Y')}</td><td class='text-primary fw-bold'>{display_pay:,.2f}</td><td><span class='badge bg-info text-dark'>{h.receiving_account or 'กรุงศรีอยุธยา'}</span></td><td class='text-danger'>{h.fine_amount:,.2f}</td><td class='text-warning text-dark'>{h.discount_amount:,.2f}</td><td>{h.interest_paid:,.2f}</td><td>{h.principal_reduced:,.2f}</td><td>{h.note or '-'}</td><td><span class='badge bg-secondary'>{h.admin_name or '-'}</span></td></tr>"
    
    if not rows: rows = "<tr><td colspan='9' class='text-center text-muted'>ยังไม่มีประวัติการชำระเงิน</td></tr>"
    content = f"""<div class="card p-4 shadow-sm border-warning"><div class="d-flex justify-content-between align-items-center mb-3"><h4 class="mb-0 fs-5 text-danger fw-bold">📜 ประวัติการชำระเงิน: {tx.customer_name}</h4><a href="/" class="btn btn-sm btn-secondary">กลับหน้าหลัก</a></div><div class="table-responsive"><table class="table table-striped align-middle text-nowrap"><thead class="table-dark"><tr><th>วันที่ทำรายการ</th><th>ยอดจ่ายจริง</th><th>ช่องทางรับเงิน</th><th>ค่าปรับ</th><th>ส่วนลด</th><th>ตัดดอกเบี้ย</th><th>ตัดเงินต้น</th><th>หมายเหตุ</th><th>ผู้บันทึก</th></tr></thead><tbody>{rows}</tbody></table></div></div>"""
    html = BASE_LAYOUT.replace('{% block header %}ประวัติการชำระเงิน{% endblock %}', 'ประวัติการชำระเงิน').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="ประวัติการชำระเงิน", page="dashboard")

@app.route('/sales_members')
def sales_members():
    if 'admin' not in session: return redirect(url_for('login'))
    sales_data = defaultdict(list)
    for tx in Transaction.query.filter(Transaction.principal > 0).order_by(Transaction.customer_name.asc()).all():
        calculate_tx_values(tx)
        sales_data[tx.sales_name].append(tx)

    sales_content = ""
    for sales, txs in sales_data.items():
        sub_rows = "".join([f"<tr><td><a href='/customer_details/{t.customer_name}' class='text-dark text-decoration-none fw-bold'>{t.customer_name}</a></td><td>{t.phone or '-'}</td><td><span class='badge bg-secondary'>{t.type}</span></td><td><span class='badge bg-warning text-dark'>{t.funding_source or 'กรุงศรีอยุธยา'}</span></td><td>{t.start_date.strftime('%d/%m/%Y')}</td><td>{t.original_principal:,.2f}</td><td>{t.principal:,.2f}</td><td><strong>{t.total_paid:,.2f}</strong></td><td><span class='badge bg-success'>{t.status}</span></td></tr>" for t in txs])
        sales_content += f"""
        <div class="card mb-4 shadow-sm border-warning">
            <div class="card-header bg-danger text-white"><h5 class="mb-0 fs-6">🔱 เซลล์ผู้ดูแล: {sales}</h5></div>
            <div class="card-body"><div class="table-responsive"><table class="table table-striped text-nowrap align-middle"><thead><tr><th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>ประเภท</th><th>บัญชีปล่อย</th><th>วันที่กู้</th><th>เงินลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th><th>สถานะ</th></tr></thead><tbody>{sub_rows}</tbody></table></div></div>
        </div>
        """
    html = BASE_LAYOUT.replace('{% block header %}2. สมาชิกภายใต้เซลล์{% endblock %}', 'สมาชิกแยกตามเซลล์').replace('{% block content %}{% endblock %}', sales_content or '<p class="text-center text-muted">ยังไม่มีข้อมูล</p>')
    return render_template_string(html, title="สมาชิกภายใต้เซลล์", page="sales")

@app.route('/customer_summary')
def customer_summary():
    if 'admin' not in session: return redirect(url_for('login'))
    rows = "".join([f"<tr><td><a href='/customer_details/{t.customer_name}' class='text-dark text-decoration-none fw-bold'>{t.customer_name}</a></td><td>{t.phone or '-'}</td><td><span class='badge bg-danger'>{t.sales_name}</span></td><td>{t.type}</td><td><span class='badge bg-warning text-dark'>{t.funding_source or 'กรุงศรีอยุธยา'}</span></td><td>{t.start_date.strftime('%d/%m/%Y')}</td><td>{t.original_principal:,.2f}</td><td>{t.principal:,.2f}</td><td><strong>{t.total_paid:,.2f}</strong></td><td>{t.paid_interest:,.2f}</td><td><span class='badge {'bg-success' if t.principal>0 else 'bg-danger'}'>{'ปกติ' if t.principal>0 else 'คืนแล้ว'}</span></td></tr>" for t in Transaction.query.order_by(Transaction.customer_name.asc()).all() if calculate_tx_values(t) or True])
    content = f"""<div class="card p-4 shadow-sm border-warning"><h4 class="mb-3 fs-5 text-danger fw-bold">📂 สรุปข้อมูลลูกค้าทั้งหมด</h4><div class="table-responsive"><table class="table table-striped align-middle text-nowrap"><thead class="table-dark"><tr><th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>เซลล์</th><th>ประเภท</th><th>บัญชีปล่อย</th><th>วันที่กู้</th><th>เงินลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th><th>กำไรสะสม</th><th>สถานะ</th></tr></thead><tbody>{rows}</tbody></table></div></div>"""
    html = BASE_LAYOUT.replace('{% block header %}3. สรุปลูกค้า{% endblock %}', 'สรุปลูกค้า').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="สรุปลูกค้า", page="customer")

@app.route('/customer_emergency')
def customer_emergency():
    if 'admin' not in session: return redirect(url_for('login'))
    rows = "".join([f"<tr><td><a href='/customer_details/{t.customer_name}' class='text-dark text-decoration-none fw-bold'>{t.customer_name}</a></td><td>{t.phone or '-'}</td><td>{t.sales_name}</td><td><span class='badge bg-warning text-dark'>{t.funding_source or 'กรุงศรีอยุธยา'}</span></td><td>{t.original_principal:,.2f}</td><td>{t.principal:,.2f}</td><td><strong>{t.total_paid:,.2f}</strong></td></tr>" for t in Transaction.query.filter_by(type='เงินฉุกเฉิน').all() if calculate_tx_values(t) or True])
    html = BASE_LAYOUT.replace('{% block header %}3.1 เงินฉุกเฉิน{% endblock %}', 'เงินฉุกเฉิน').replace('{% block content %}{% endblock %}', f'<div class="card p-4 shadow-sm border-warning"><div class="table-responsive"><table class="table table-striped text-nowrap"><thead><tr><th>ชื่อ</th><th>เบอร์</th><th>เซลล์</th><th>บัญชีปล่อย</th><th>ลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th></tr></thead><tbody>{rows}</tbody></table></div></div>')
    return render_template_string(html, title="เงินฉุกเฉิน", page="emergency")

@app.route('/customer_gold')
def customer_gold():
    if 'admin' not in session: return redirect(url_for('login'))
    rows = "".join([f"<tr><td><a href='/customer_details/{t.customer_name}' class='text-dark text-decoration-none fw-bold'>{t.customer_name}</a></td><td>{t.phone or '-'}</td><td>{t.sales_name}</td><td><span class='badge bg-warning text-dark'>{t.funding_source or 'กรุงศรีอยุธยา'}</span></td><td>{t.original_principal:,.2f}</td><td>{t.principal:,.2f}</td><td><strong>{t.total_paid:,.2f}</strong></td></tr>" for t in Transaction.query.filter_by(type='ผ่อนทอง').all() if calculate_tx_values(t) or True])
    html = BASE_LAYOUT.replace('{% block header %}3.2 ผ่อนทอง{% endblock %}', 'ผ่อนทอง').replace('{% block content %}{% endblock %}', f'<div class="card p-4 shadow-sm border-warning"><div class="table-responsive"><table class="table table-striped text-nowrap"><thead><tr><th>ชื่อ</th><th>เบอร์</th><th>เซลล์</th><th>บัญชีปล่อย</th><th>ลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th></tr></thead><tbody>{rows}</tbody></table></div></div>')
    return render_template_string(html, title="ผ่อนทอง", page="gold")

@app.route('/customer_debt')
def customer_debt():
    if 'admin' not in session: return redirect(url_for('login'))
    rows = "".join([f"<tr><td><a href='/customer_details/{t.customer_name}' class='text-dark text-decoration-none fw-bold'>{t.customer_name}</a></td><td>{t.phone or '-'}</td><td>{t.sales_name}</td><td><span class='badge bg-warning text-dark'>{t.funding_source or 'กรุงศรีอยุธยา'}</span></td><td>{t.original_principal:,.2f}</td><td>{t.principal:,.2f}</td><td><strong>{t.total_paid:,.2f}</strong></td></tr>" for t in Transaction.query.filter_by(type='ยอดค้างเก่า').all() if calculate_tx_values(t) or True])
    html = BASE_LAYOUT.replace('{% block header %}3.3 ยอดค้างเก่า{% endblock %}', 'ยอดค้างเก่า').replace('{% block content %}{% endblock %}', f'<div class="card p-4 shadow-sm border-warning"><div class="table-responsive"><table class="table table-striped text-nowrap"><thead><tr><th>ชื่อ</th><th>เบอร์</th><th>เซลล์</th><th>บัญชีปล่อย</th><th>ยอดตั้งต้น</th><th>ยอดคงเหลือ</th><th>ชำระแล้ว</th></tr></thead><tbody>{rows}</tbody></table></div></div>')
    return render_template_string(html, title="ยอดค้างเก่า", page="debt")

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
    app.run(debug=True)
