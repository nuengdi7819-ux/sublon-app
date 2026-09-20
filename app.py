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
    'pool_recycle': 300,
    'pool_pre_ping': True
}

db = SQLAlchemy(app)

TH_TIMEZONE = timezone(timedelta(hours=7))

def get_thai_today():
    return datetime.now(TH_TIMEZONE).date()

VALID_USERS = {
    'nueng': '909090',
    'nice': '022540'
}

def get_funding_badge(source):
    if source == 'ออมสิน':
        return '<span class="badge" style="background-color: #e83e8c; color: #fff;">ออมสิน</span>'
    elif source == 'กรุงศรีอยุธยา':
        return '<span class="badge text-dark" style="background-color: #ffc107;">กรุงศรีอยุธยา</span>'
    elif source == 'วอลเล็ท':
        return '<span class="badge" style="background-color: #dc3545; color: #fff;">วอลเล็ท</span>'
    return f'<span class="badge bg-secondary">{source or "ออมสิน"}</span>'

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
    funding_source = db.Column(db.String(50), default='ออมสิน')
    receiving_account = db.Column(db.String(50), default='ออมสิน')

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
    receiving_account = db.Column(db.String(50), default='ออมสิน')

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

        .btn-warning { background-color: #ffd700; border-color: #ffc700; color: #2c0b0e; font-weight: 700; }
        .btn-warning:hover { background-color: #ffc107; border-color: #ffb300; color: #000; }
        .btn-success-light { background-color: #28a745; border-color: #28a745; color: #fff; font-weight: 600; }
        .btn-success-light:hover { background-color: #218838; border-color: #1e7e34; color: #fff; }

        .table-responsive::-webkit-scrollbar { height: 10px; }
        .table-responsive::-webkit-scrollbar-track { background: #f1f1f1; border-radius: 6px; }
        .table-responsive::-webkit-scrollbar-thumb { background: #ffd700; border-radius: 6px; }

        @media (max-width: 768px) {
            .modal-dialog { margin: 10px; max-width: calc(100% - 20px); }
            .modal-body { max-height: 75vh; overflow-y: auto; }
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
            <li><a href="/members_daily" class="nav-link sub-menu {% if page == 'members_daily' %}active{% endif %}" onclick="toggleSidebar()">🔸 1.1 จ่ายทุกวัน (ทวงทุกวัน)</a></li>
            <li><a href="/members_unscheduled" class="nav-link sub-menu {% if page == 'members_unscheduled' %}active{% endif %}" onclick="toggleSidebar()">🔸 1.2 ยังไม่มีกำหนดจ่าย</a></li>
            <li><a href="/members_scheduled_all" class="nav-link sub-menu {% if page == 'members_scheduled_all' %}active{% endif %}" onclick="toggleSidebar()">🔸 1.3 กำหนดจ่ายประจำเดือน</a></li>

            <li><a href="/sales_members" class="nav-link {% if page == 'sales' %}active{% endif %}" onclick="toggleSidebar()">📋 2. สมาชิกภายใต้เซลล์</a></li>
            <li><a href="/customer_summary" class="nav-link {% if page == 'customer' %}active{% endif %}" onclick="toggleSidebar()">📂 3. สรุปลูกค้า</a></li>
            <li><a href="/customer_emergency" class="nav-link sub-menu {% if page == 'emergency' %}active{% endif %}" onclick="toggleSidebar()">🔸 3.1 เงินฉุกเฉิน</a></li>
            <li><a href="/customer_gold" class="nav-link sub-menu {% if page == 'gold' %}active{% endif %}" onclick="toggleSidebar()">🔸 3.2 ผ่อนทอง</a></li>
            <li><a href="/customer_debt" class="nav-link sub-menu {% if page == 'debt' %}active{% endif %}" onclick="toggleSidebar()">🔸 3.3 ยอดค้างเก่า</a></li>
            <li><a href="/monthly_summary" class="nav-link sub-menu {% if page == 'monthly' %}active{% endif %}" onclick="toggleSidebar()">📅 4. สรุปยอดรายเดือน</a></li>
        </ul>
        <hr class="border-secondary">
        <div class="d-flex flex-column gap-2 mb-2">
            <a href="/export_data" class="btn btn-outline-warning btn-sm w-100">📥 สำรองข้อมูล (Backup)</a>
            <button type="button" class="btn btn-outline-info btn-sm w-100" data-bs-toggle="modal" data-bs-target="#importModal">📤 นำเข้าข้อมูล (Restore)</button>
        </div>
        <div class="d-flex flex-column gap-2">
            <a href="/logout" class="btn btn-outline-danger w-100 d-none d-lg-block">ออกจากระบบ</a>
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

    function openAddModal(accountName) {
        let selectFunding = document.getElementById('addFundingSource');
        if (selectFunding) {
            selectFunding.value = accountName;
        }
        let myModal = new bootstrap.Modal(document.getElementById('addTransactionModal'));
        myModal.show();
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
    if days < 1: days = 1
    tx.days_passed_val = days
    
    if tx.original_principal > 0 and tx.initial_daily_interest > 0:
        current_daily_interest = tx.initial_daily_interest * (tx.principal / tx.original_principal)
        tx.daily_interest = current_daily_interest
    
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

@app.route('/', methods=['GET'])
def index():
    if 'admin' not in session: return redirect(url_for('login'))

    search_query = request.args.get('search', '').strip()
    start_date_str = request.args.get('start_date', '').strip()
    end_date_str = request.args.get('end_date', '').strip()
    thai_today = get_thai_today()
    today_day = thai_today.day

    query = Transaction.query.filter(Transaction.principal > 0)
    if search_query:
        search_pattern = f"%{search_query}%"
        query = query.filter((Transaction.customer_name.ilike(search_pattern)) | (Transaction.phone.ilike(search_pattern)))
    
    if start_date_str and end_date_str:
        try:
            s_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            e_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            query = query.filter((Transaction.start_date >= s_date) & (Transaction.start_date <= e_date) | (Transaction.last_payment_date >= s_date) & (Transaction.last_payment_date <= e_date))
        except Exception as e: print("Date error:", e)
    elif start_date_str:
        try:
            target_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            query = query.filter((Transaction.start_date == target_date) | (Transaction.last_payment_date == target_date))
        except Exception as e: print("Date error:", e)
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

    all_unique_customers = sorted(list(set(t.customer_name for t in all_txs_ever if t.customer_name)))

    customer_active_counts = defaultdict(int)
    for t in all_txs_ever:
        if t.principal > 0 and t.customer_name:
            customer_active_counts[t.customer_name] += 1

    inv_by_source = defaultdict(float)
    total_new_investment = 0.0
    for tx in all_txs_ever:
        if tx.type != 'ยอดค้างเก่า':
            total_new_investment += tx.original_principal
            source = tx.funding_source or 'ออมสิน'
            inv_by_source[source] += tx.original_principal

    total_debt_principal = sum(tx.principal for tx in all_txs_ever if tx.type == 'ยอดค้างเก่า')
    total_new_principal = sum(tx.principal for tx in all_txs_ever if tx.type != 'ยอดค้างเก่า' and tx.principal > 0)
    
    today_new_txs = [tx for tx in all_txs_ever if tx.start_date == thai_today]
    today_new_count = len(today_new_txs)

    today_histories = PaymentHistory.query.filter_by(payment_date=thai_today).all()
    today_collected_cash = sum((h.pay_amount if h.pay_amount > 0 else (h.interest_paid + h.principal_reduced + h.fine_amount - h.discount_amount)) + h.fine_amount for h in today_histories)
    
    today_payment_count = len(today_histories)
    total_today_actions = today_new_count + today_payment_count

    # Optimized Bank Calculation (Single Pass & Indexed Lookup)
    account_balances = {
        'กรุงศรีอยุธยา': 0.0,
        'ออมสิน': 0.0,
        'วอลเล็ท': 0.0
    }

    adjustments = BankAdjustment.query.all()
    adj_dict = {adj.account_name: adj.adjustment_amount for adj in adjustments}

    for acc_name in account_balances.keys():
        account_balances[acc_name] = adj_dict.get(acc_name, 0.0)

    bank_details_data = {acc: {'inflows': [], 'outflows': []} for acc in account_balances.keys()}

    all_histories = PaymentHistory.query.all()
    for h in all_histories:
        acc = h.receiving_account or 'ออมสิน'
        if acc in bank_details_data:
            tx_ref = h.transaction
            cust_name = tx_ref.customer_name if tx_ref else "ไม่ระบุชื่อ"
            amt = h.pay_amount if h.pay_amount > 0 else (h.interest_paid + h.principal_reduced + h.fine_amount - h.discount_amount)
            if amt > 0:
                bank_details_data[acc]['inflows'].append({
                    'date': h.payment_date.strftime('%d/%m/%Y'),
                    'customer': cust_name,
                    'amount': amt,
                    'note': h.note or 'รับชำระเงิน'
                })

    for tx in all_txs_ever:
        if tx.type != 'ยอดค้างเก่า' and tx.principal > 0:
            acc = tx.funding_source or 'ออมสิน'
            if acc in bank_details_data:
                bank_details_data[acc]['outflows'].append({
                    'date': tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-',
                    'target': f"ปล่อยกู้ใหม่: {tx.customer_name}",
                    'amount': tx.original_principal,
                    'note': f"ทุนกู้ {tx.type}"
                })

    krungsri_keywords = ["แอนนา บริสุทธิ์", "วันดี ประสานสงฆ์", "ชั้นไม่ใช่ นางเอก", "Anongnad Petchanoo", "กุลธิดา อานับ", "เชิฟ"]

    profit_items = []
    for tx in all_txs_ever:
        if tx.type == 'ยอดค้างเก่า':
            net_earned = max(0.0, (tx.original_principal - tx.principal))
        else:
            hist_sum = sum(h.interest_paid for h in tx.histories) if tx.histories else 0.0
            net_earned = max(tx.paid_interest, hist_sum)
            
        tx_fine_sum = sum(h.fine_amount for h in tx.histories) if tx.histories else 0.0
        tx_discount_sum = sum(h.discount_amount for h in tx.histories) if tx.histories else 0.0
        total_item_profit = net_earned + tx_fine_sum - tx_discount_sum

        if total_item_profit != 0 or net_earned > 0 or tx_fine_sum > 0 or tx_discount_sum > 0:
            latest_date = tx.start_date
            if tx.histories:
                max_h_date = max(h.payment_date for h in tx.histories)
                if max_h_date > latest_date: latest_date = max_h_date
            if tx.last_payment_date and tx.last_payment_date > latest_date:
                latest_date = tx.last_payment_date

            profit_items.append({
                'customer_name': tx.customer_name,
                'type': tx.type,
                'net_earned': net_earned,
                'fine_amount': tx_fine_sum,
                'discount_amount': tx_discount_sum,
                'total_item_profit': total_item_profit,
                'latest_date': latest_date
            })

    profit_items.sort(key=lambda x: x['latest_date'], reverse=True)

    for item in profit_items:
        if item['total_item_profit'] > 0:
            is_krungsri = any(kw.lower() in item['customer_name'].lower() for kw in krungsri_keywords)
            target_acc = 'กรุงศรีอยุธยา' if is_krungsri else 'ออมสิน'
            
            bank_details_data[target_acc]['inflows'].append({
                'date': item['latest_date'].strftime('%d/%m/%Y') if item['latest_date'] else '-',
                'customer': f"กำไรสะสม: {item['customer_name']}",
                'amount': item['total_item_profit'],
                'note': f"ประเภท: {item['type']}"
            })

    expense_logs = BankExpenseLog.query.order_by(BankExpenseLog.expense_date.desc(), BankExpenseLog.id.desc()).all()
    for e in expense_logs:
        acc = e.account_name
        if acc in bank_details_data:
            bank_details_data[acc]['outflows'].append({
                'date': e.expense_date.strftime('%d/%m/%Y'),
                'target': f"ถอนเงินออก: {e.note or 'ค่าใช้จ่าย'}",
                'amount': e.amount,
                'note': f"ผู้ทำรายการ: {e.admin_name or '-'}"
            })

    bank_modals_html = ""
    bank_config = [
        ('กรุงศรีอยุธยา', '🟡 กรุงศรีอยุธยา (803-931-9819)', 'modalKrungsri', 'warning'),
        ('ออมสิน', '🩷 ออมสิน (020-409-437-819)', 'modalGSB', 'danger'),
        ('วอลเล็ท', '🟠 TrueMoney Wallet (092-923-7819)', 'modalWallet', 'info')
    ]

    for acc_key, acc_title, modal_id, theme_color in bank_config:
        inflows = bank_details_data[acc_key]['inflows']
        outflows = bank_details_data[acc_key]['outflows']

        inflow_rows = "".join([f"<tr><td>{item['date']}</td><td><a href='/customer_details/{item['customer']}' class='fw-bold text-dark text-decoration-none'>{item['customer']}</a></td><td class='text-success fw-bold'>+{item['amount']:,.2f}</td><td>{item['note']}</td></tr>" for item in inflows])
        outflow_rows = "".join([f"<tr><td>{item['date']}</td><td>{item['target']}</td><td class='text-danger fw-bold'>-{item['amount']:,.2f}</td><td>{item['note']}</td></tr>" for item in outflows])

        bank_modals_html += f"""
        <div class="modal fade" id="{modal_id}" tabindex="-1">
            <div class="modal-dialog modal-lg modal-dialog-centered">
                <div class="modal-content border-{theme_color}">
                    <div class="modal-header bg-{theme_color} text-white py-2">
                        <h5 class="modal-title fw-bold fs-6">📊 รายละเอียดความเคลื่อนไหว: {acc_title}</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body" style="max-height: 65vh; overflow-y: auto;">
                        <div class="mb-4">
                            <h6 class="text-success fw-bold border-bottom pb-2">📥 เงินเข้า (มาจากลูกค้าโอนชำระยอด + กำไรสะสม)</h6>
                            <div class="table-responsive">
                                <table class="table table-sm table-striped align-middle text-nowrap">
                                    <thead class="table-dark"><tr><th>วันที่</th><th>ชื่อลูกค้า / รายการ</th><th>จำนวนเงิน</th><th>หมายเหตุ</th></tr></thead>
                                    <tbody>{inflow_rows if inflow_rows else "<tr><td colspan='4' class='text-center text-muted'>ยังไม่มีรายการเงินเข้า</td></tr>"}</tbody>
                                </table>
                            </div>
                        </div>
                        <div class="mb-3">
                            <h6 class="text-danger fw-bold border-bottom pb-2">📤 เงินออก (รวมถึงการปล่อยกู้ใหม่ทั้งหมด)</h6>
                            <div class="table-responsive">
                                <table class="table table-sm table-striped align-middle text-nowrap">
                                    <thead class="table-dark"><tr><th>วันที่</th><th>รายการ / ผู้รับ</th><th>จำนวนเงิน</th><th>หมายเหตุ</th></tr></thead>
                                    <tbody>{outflow_rows if outflow_rows else "<tr><td colspan='4' class='text-center text-muted'>ยังไม่มีรายการเงินออก</td></tr>"}</tbody>
                                </table>
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer py-2 justify-content-between">
                        <button type="button" class="btn btn-warning btn-sm fw-bold text-dark px-3 py-1 shadow-sm" style="font-size: 0.82rem;" data-bs-dismiss="modal" onclick="openAddModal('{acc_key}')">➕ เพิ่มรายการใหม่</button>
                        <button type="button" class="btn btn-outline-secondary btn-sm px-3" data-bs-dismiss="modal" style="font-size: 0.8rem;">ปิดหน้าต่าง</button>
                    </div>
                </div>
            </div>
        </div>
        """

    expense_rows = "".join([f"<tr><td>{e.expense_date.strftime('%d/%m/%Y')}</td><td><span class='badge bg-warning text-dark'>{e.account_name}</span></td><td class='text-danger fw-bold'>-{e.amount:,.2f}</td><td>{e.note or '-'}</td><td><span class='badge bg-secondary'>{e.admin_name or '-'}</span></td><td><a href='/delete_expense/{e.id}' class='btn btn-sm btn-danger py-0 px-2' onclick=\"return confirm('ยืนยันลบประวัติการถอนนี้?')\">ลบ</a></td></tr>" for e in expense_logs])

    today_new_rows = ""
    for tx in today_new_txs:
        today_new_rows += f"""
        <tr>
            <td><a href="/customer_details/{tx.customer_name}" class="text-dark fw-bold text-decoration-none">{tx.customer_name}</a></td>
            <td><span class="badge bg-secondary">{tx.type}</span></td>
            <td>{tx.phone or '-'}</td>
            <td class="text-primary fw-bold">{tx.original_principal:,.2f}</td>
            <td>{get_funding_badge(tx.funding_source or 'ออมสิน')}</td>
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
            <td>{get_funding_badge(h.receiving_account or 'ออมสิน')}</td>
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

    sum_modal_actual_profit = sum(item['total_item_profit'] for item in profit_items)
    profit_card_rows = "".join([f"<tr><td><a href='/customer_details/{item['customer_name']}' class='text-dark fw-bold text-decoration-none'>{item['customer_name']}</a></td><td><span class='badge bg-secondary'>{item['type']}</span></td><td>{item['net_earned']:,.2f}</td><td>{item['fine_amount']:,.2f}</td><td class='text-danger'>-{item['discount_amount']:,.2f}</td><td class='text-success fw-bold'>{item['total_item_profit']:,.2f}</td><td>{item['latest_date'].strftime('%d/%m/%Y') if item['latest_date'] else '-'}</td></tr>" for item in profit_items])

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
            <td style="position: sticky; left: 0; background-color: #fff; z-index: 2; font-weight: 500;">
                <a href="/customer_details/{tx.customer_name}" class="text-dark fw-bold text-decoration-none">{tx.customer_name}</a>{count_badge}
            </td>
            <td>{tx.phone or '-'}</td>
            <td><span class="badge bg-secondary">{tx.type}</span> {schedule_badge}</td>
            <td>{get_funding_badge(tx.funding_source or 'ออมสิน')}</td>
            <td>{get_funding_badge(tx.receiving_account or 'ออมสิน')}</td>
            <td>{start_date_str_fmt}</td>
            <td>{last_pay_str}</td>
            <td>{tx.original_principal:,.2f}</td>
            <td>{tx.principal:,.2f}</td>
            <td><a href="/history/{tx.id}" target="_blank" class="text-primary fw-bold text-decoration-none" title="คลิกเพื่อดูประวัติการจ่าย">{tx.total_paid:,.2f}</a></td>
            <td>{tx.daily_interest:,.2f}</td>
            <td>{tx.days_passed}</td>
            <td>{tx.accumulated_interest:,.2f}</td>
            <td><span class="badge {badge_color}">{tx.status}</span></td>
            <td style="position: sticky; right: 0; background-color: #fff; z-index: 2; text-align: center;">
                <div class="d-flex flex-column gap-2" style="width: 90px; margin: 0 auto;">
                    <button type="button" class="btn btn-sm btn-success-light w-100" data-bs-toggle="modal" data-bs-target="#payModal{tx.id}">จัดการยอด</button>
                    <a href="/delete_tx/{tx.id}" class="btn btn-sm btn-danger w-100" onclick="return confirm('ยืนยันการลบ?')">ลบ</a>
                </div>
            </td>
        </tr>
        """

        cards += f"""
        <div class="card mb-3 shadow-sm border-warning">
            <div class="card-body p-3">
                <div class="d-flex justify-content-between align-items-start mb-2">
                    <div>
                        <h6 class="fw-bold mb-1">
                            👤 <a href="/customer_details/{tx.customer_name}" class="text-danger text-decoration-none">{tx.customer_name}</a>{count_badge}
                        </h6>
                        <span class="badge bg-secondary">{tx.type}</span> {schedule_badge}
                        {get_funding_badge(tx.funding_source or 'ออมสิน')}
                        <span class="badge {badge_color}">{tx.status}</span>
                    </div>
                    <div class="text-end"><small class="text-muted">โทร: {tx.phone or '-'}</small></div>
                </div>
                <hr class="my-2">
                <div class="row g-1 small mb-3">
                    <div class="col-6">📅 วันที่เริ่ม: {start_date_str_fmt}</div>
                    <div class="col-6">⏱️ เวลา: {tx.days_passed}</div>
                    <div class="col-6">💰 เงินลงทุน: <b>{tx.original_principal:,.2f}</b></div>
                    <div class="col-6 text-danger">💼 ต้นคงค้าง: <b>{tx.principal:,.2f}</b></div>
                    <div class="col-6 text-primary">💵 ชำระแล้ว: <a href="/history/{tx.id}" target="_blank" class="text-primary text-decoration-none"><b>{tx.total_paid:,.2f}</b></a></div>
                    <div class="col-6">📈 ดอก/วัน: {tx.daily_interest:,.2f}</div>
                    <div class="col-12 text-danger fw-bold mt-1">🔥 ดอกเบี้ยสะสม: {tx.accumulated_interest:,.2f} บาท</div>
                </div>
                <div class="d-flex gap-2">
                    <button type="button" class="btn btn-success-light btn-sm w-100 fw-bold" data-bs-toggle="modal" data-bs-target="#payModal{tx.id}">⚙️ จัดการยอด</button>
                    <a href="/delete_tx/{tx.id}" class="btn btn-outline-danger btn-sm" onclick="return confirm('ยืนยันการลบ?')">ลบ</a>
                </div>
            </div>
        </div>
        """

        selected_normal = "selected" if tx.status == "ปกติ" else ""
        selected_partial = "selected" if tx.status == "ตัดยอดบางส่วน" else ""

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
                                    <option value="ออมสิน" selected>🩷 ออมสิน (020-409-437-819)</option>
                                    <option value="กรุงศรีอยุธยา">🟢 กรุงศรีอยุธยา (803-931-9819)</option>
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
                            <div class="mb-2">
                                <label class="form-label text-dark fw-bold mb-1" style="font-size: 0.85rem;">📝 หมายเหตุการชำระ</label>
                                <input type="text" name="note" class="form-control form-control-sm" placeholder="เช่น จ่ายเฉพาะค่าปรับ, โอนผ่าน KTB">
                            </div>
                            <div class="mb-1">
                                <label class="form-label text-success fw-bold mb-1" style="font-size: 0.85rem;">สถานะรายการ</label>
                                <select name="new_status" class="form-select form-select-sm border-success" id="newStatus{tx.id}">
                                    <option value="ปกติ" {selected_normal}>ปกติ</option>
                                    <option value="ตัดยอดบางส่วน" {selected_partial}>ตัดยอดบางส่วน</option>
                                </select>
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
        table_title = f'📋 ผลการค้นหา: "{search_query}"'
        view_today_btn = '<a href="/" class="btn btn-sm btn-success fw-bold">🟢 แสดงรายการแจ้งเตือนวันนี้</a>'
    else:
        table_title = f"🔔 รายการที่ต้องทวงวันนี้ (ประจำวันที่ {today_day})"
        view_today_btn = '<a href="/all_transactions" class="btn btn-sm btn-outline-danger fw-bold">📂 ดูรายการทั้งหมด</a>'

    datalist_options = "".join([f'<option value="{c_name}">' for c_name in all_unique_customers])

    content = f"""
    <!-- 1. สถานะกระเป๋าเงินจริงในมือถือ -->
    <div class="card p-3 mb-4 shadow-sm border-warning bg-white">
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <h5 class="text-danger fw-bold mb-0">🏦 สถานะกระเป๋าเงินจริงในมือถือ (คลิกที่กล่องบัญชีเพื่อดูรายละเอียด)</h5>
            <div class="d-flex gap-2 flex-wrap">
                <button type="button" class="btn btn-outline-primary btn-sm fw-bold" data-bs-toggle="modal" data-bs-target="#transferModal">🔄 โยกเงินระหว่างบัญชี</button>
                <button type="button" class="btn btn-outline-danger btn-sm fw-bold" data-bs-toggle="modal" data-bs-target="#adjustBankModal">⚙️ ตั้งค่า/ปรับยอดเงินตั้งต้น</button>
                <button type="button" class="btn btn-danger btn-sm fw-bold" data-bs-toggle="modal" data-bs-target="#withdrawModal">💸 ถอนเงินออก (จ่ายพนักงาน/ค่าใช้จ่าย)</button>
            </div>
        </div>
        <div class="row g-3">
            <div class="col-md-4">
                <div class="p-3 rounded border border-warning bg-warning bg-opacity-15 shadow-sm" style="cursor: pointer;" data-bs-toggle="modal" data-bs-target="#modalKrungsri" title="คลิกเพื่อดูรายละเอียด">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="text-dark fw-bold mb-1">🟡 กรุงศรีอยุธยา (คลิกเพื่อจัดการ)</h6>
                            <small class="text-muted d-block mb-1">เลข: 803-931-9819</small>
                            <h3 class="text-dark fw-bold mb-0">{account_balances['กรุงศรีอยุธยา']:,.2f} บาท</h3>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="p-3 rounded border border-danger bg-danger bg-opacity-10 shadow-sm" style="cursor: pointer;" data-bs-toggle="modal" data-bs-target="#modalGSB" title="คลิกเพื่อดูรายละเอียด">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="text-danger fw-bold mb-1">🩷 ออมสิน (คลิกเพื่อจัดการ)</h6>
                            <small class="text-muted d-block mb-1">เลข: 020-409-437-819</small>
                            <h3 class="text-danger fw-bold mb-0">{account_balances['ออมสิน']:,.2f} บาท</h3>
                        </div>
                    </div>
                </div>
            </div>
            <div class="col-md-4">
                <div class="p-3 rounded border border-info bg-info bg-opacity-10 shadow-sm" style="cursor: pointer;" data-bs-toggle="modal" data-bs-target="#modalWallet" title="คลิกเพื่อดูรายละเอียด">
                    <div class="d-flex justify-content-between align-items-center">
                        <div>
                            <h6 class="text-dark fw-bold mb-1">🟠 TrueMoney Wallet (คลิกเพื่อจัดการ)</h6>
                            <small class="text-muted d-block mb-1">เบอร์: 092-923-7819</small>
                            <h3 class="text-dark fw-bold mb-0">{account_balances['วอลเล็ท']:,.2f} บาท</h3>
                        </div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- ประวัติการถอนเงินออกไปใช้จ่าย -->
        <div class="mt-3 pt-3 border-top">
            <button class="btn btn-outline-secondary btn-sm mb-2" type="button" data-bs-toggle="collapse" data-bs-target="#expenseLogCollapse">
                📜 ดูประวัติการถอนเงินออกไปจ่ายพนักงาน / ค่าใช้จ่ายทั้งหมด (คลิกเพื่อเปิด/ปิด)
            </button>
            <div class="collapse" id="expenseLogCollapse">
                <div class="table-responsive bg-light p-2 rounded">
                    <table class="table table-sm table-striped align-middle text-nowrap mb-0">
                        <thead>
                            <tr><th>วันที่</th><th>บัญชี</th><th>จำนวนเงิน</th><th>หมายเหตุ</th><th>ผู้ทำรายการ</th><th>จัดการ</th></tr>
                        </thead>
                        <tbody>
                            {expense_rows if expense_rows else "<tr><td colspan='6' class='text-center text-muted'>ยังไม่มีประวัติการถอนเงินออก</td></tr>"}
                        </tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>

    {bank_modals_html}

    <!-- Modal โยกเงินระหว่างบัญชีเพื่อพักเงิน -->
    <div class="modal fade" id="transferModal" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-primary">
                <form action="/transfer_bank_money" method="POST">
                    <div class="modal-header bg-primary text-white py-2">
                        <h5 class="modal-title fw-bold fs-6">🔄 โยกเงินระหว่างบัญชี (เพื่อพักเงิน)</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p class="text-muted small">เลือกบัญชีต้นทางที่ต้องการย้ายเงินออก และบัญชีปลายทางที่ต้องการพักเงิน</p>
                        <div class="mb-3">
                            <label class="form-label fw-bold text-danger">📤 โยกเงินออกจากบัญชี (ต้นทาง)</label>
                            <select name="from_account" id="transferFromSelect" class="form-select border-danger" required>
                                <option value="ออมสิน">🩷 ออมสิน (020-409-437-819)</option>
                                <option value="กรุงศรีอยุธยา">🟢 กรุงศรีอยุธยา (803-931-9819)</option>
                                <option value="วอลเล็ท">🟠 TrueMoney Wallet (092-923-7819)</option>
                            </select>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-bold text-success">📥 โยกไปเข้าบัญชี (ปลายทาง / ที่พักเงิน)</label>
                            <select name="to_account" class="form-select border-success" required>
                                <option value="กรุงศรีอยุธยา" selected>🟢 กรุงศรีอยุธยา (803-931-9819)</option>
                                <option value="ออมสิน">🩷 ออมสิน (020-409-437-819)</option>
                                <option value="วอลเล็ท">🟠 TrueMoney Wallet (092-923-7819)</option>
                            </select>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-bold text-dark">💵 จำนวนเงินที่ต้องการโยก (บาท)</label>
                            <input type="number" step="any" name="transfer_amount" class="form-control" placeholder="เช่น 2500" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-bold text-dark">📝 หมายเหตุการโยกเงิน</label>
                            <input type="text" name="note" class="form-control" placeholder="เช่น โยกกำไรจากออมสินมาพักไว้กรุงศรี">
                        </div>
                    </div>
                    <div class="modal-footer py-2">
                        <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ยกเลิก</button>
                        <button type="submit" class="btn btn-primary btn-sm fw-bold px-3">ยืนยันโยกเงิน</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- Modal ตั้งค่า/ปรับยอดเงินตั้งต้นในกระเป๋า -->
    <div class="modal fade" id="adjustBankModal" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-danger">
                <form action="/update_bank_adjustment" method="POST">
                    <div class="modal-header bg-danger text-white py-2">
                        <h5 class="modal-title fw-bold fs-6">⚙️ ตั้งค่าปรับยอดเงินตั้งต้นกระเป๋าจริง</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p class="text-muted small">กรอกยอดเงินสดที่มีอยู่จริงในแอปธนาคารหรือวอลเล็ทของคุณตอนนี้ ระบบจะแสดงผลตรงตามที่คุณกรอกทันที</p>
                        <div class="mb-3">
                            <label class="form-label fw-bold text-dark">🟡 กรุงศรีอยุธยา (ยอดเงินจริงในแอป)</label>
                            <input type="number" step="any" name="krungsri" class="form-control" value="{adj_dict.get('กรุงศรีอยุธยา', 0.0)}" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-bold text-danger">🩷 ออมสิน (ยอดเงินจริงในแอป)</label>
                            <input type="number" step="any" name="gsb" class="form-control" value="{adj_dict.get('ออมสิน', 0.0)}" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-bold text-primary">🟠 TrueMoney Wallet (ยอดเงินจริงในแอป)</label>
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

    <!-- Modal ถอนเงินออก (พร้อมหมายเหตุ) -->
    <div class="modal fade" id="withdrawModal" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-danger">
                <form action="/withdraw_bank_money" method="POST">
                    <div class="modal-header bg-danger text-white py-2">
                        <h5 class="modal-title fw-bold fs-6">💸 ถอนเงินออกจากบัญชี (เพื่อจ่ายพนักงาน/ค่าใช้จ่าย)</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <p class="text-muted small">การบันทึกนี้จะหักยอดออกจากกระเป๋าธนาคารจริงทันที พร้อมบันทึกประวัติและหมายเหตุไว้ตรวจสอบ</p>
                        <div class="mb-3">
                            <label class="form-label fw-bold text-success">💳 เลือกบัญชีที่ต้องการถอนออก</label>
                            <select name="account_name" class="form-select border-success" required>
                                <option value="ออมสิน" selected>🩷 ออมสิน (020-409-437-819)</option>
                                <option value="กรุงศรีอยุธยา">🟢 กรุงศรีอยุธยา (803-931-9819)</option>
                                <option value="วอลเล็ท">🟠 TrueMoney Wallet (092-923-7819)</option>
                            </select>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-bold text-danger">💵 จำนวนเงินที่ถอนออก (บาท)</label>
                            <input type="number" step="any" name="withdraw_amount" class="form-control" placeholder="เช่น 5000" required>
                        </div>
                        <div class="mb-3">
                            <label class="form-label fw-bold text-dark">📝 หมายเหตุการถอน (สำคัญมาก)</label>
                            <input type="text" name="note" class="form-control" placeholder="เช่น จ่ายเงินเดือนพนักงาน (คุณ...)" required>
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

    <!-- Modal เพิ่มรายการใหม่ (แบบกระทัดรัด 2 คอลัมน์) -->
    <div class="modal fade" id="addTransactionModal" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered modal-lg">
            <div class="modal-content border-success">
                <form action="/add_transaction" method="POST">
                    <div class="modal-header bg-success text-white py-2">
                        <h5 class="modal-title fw-bold fs-6">➕ เพิ่มรายการปล่อยกู้ใหม่</h5>
                        <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body py-3">
                        <div class="row g-2">
                            <div class="col-md-6">
                                <label class="form-label fw-bold small mb-1">ประเภทรายการ</label>
                                <select name="type" class="form-select form-select-sm" id="txTypeSelect" onchange="handleTypeChange()" required>
                                    <option value="เงินฉุกเฉิน">เงินฉุกเฉิน (ลูกค้าใหม่)</option>
                                    <option value="ผ่อนทอง">ผ่อนทอง (ลูกค้าใหม่)</option>
                                    <option value="ยอดค้างเก่า">ยอดค้างเก่า (ลูกค้าเก่า)</option>
                                </select>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label fw-bold small mb-1">ชื่อลูกค้า</label>
                                <input type="text" name="customer_name" class="form-control form-control-sm" list="customerListOptions" autocomplete="off" placeholder="พิมพ์ชื่อเพื่อค้นหาหรือเพิ่มใหม่..." required>
                                <datalist id="customerListOptions">
                                    {datalist_options}
                                </datalist>
                            </div>

                            <div class="col-md-6">
                                <label class="form-label fw-bold small mb-1">เบอร์โทร</label>
                                <input type="text" name="phone" class="form-control form-control-sm" autocomplete="tel" placeholder="08x-xxx-xxxx">
                            </div>
                            <div class="col-md-6">
                                <label class="form-label fw-bold small mb-1">วันที่กู้/วันที่เริ่ม</label>
                                <input type="date" name="start_date" class="form-control form-control-sm" value="{thai_today.strftime('%Y-%m-%d')}" required>
                            </div>

                            <div class="col-md-6">
                                <label class="form-label fw-bold text-success small mb-1">💳 แหล่งทุนที่ใช้ปล่อย:</label>
                                <select name="funding_source" id="addFundingSource" class="form-select form-select-sm border-success fw-bold text-success" required>
                                    <option value="ออมสิน">🩷 ออมสิน (020-409-437-819)</option>
                                    <option value="กรุงศรีอยุธยา">🟢 กรุงศรีอยุธยา (803-931-9819)</option>
                                    <option value="วอลเล็ท">🟠 TrueMoney Wallet (092-923-7819)</option>
                                </select>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label fw-bold text-danger small mb-1">ประเภทกำหนดจ่าย</label>
                                <select name="schedule_type" class="form-select form-select-sm border-danger" id="scheduleTypeSelect" onchange="handleScheduleChange()" required>
                                    <option value="จ่ายทุกวัน">จ่ายทุกวัน (ทวงทุกวัน)</option>
                                    <option value="กำหนดจ่ายประจำเดือน">กำหนดจ่ายประจำเดือน (เลือกหลายรอบ)</option>
                                    <option value="ยังไม่มีกำหนดจ่าย">ยังไม่มีกำหนดจ่าย</option>
                                </select>
                            </div>

                            <div class="col-12" id="dueDayDiv" style="display: none;">
                                <label class="form-label fw-bold text-primary small mb-1">รอบช่วงวันที่ต้องจ่าย</label>
                                <div class="p-2 border rounded bg-light d-flex flex-wrap gap-3">
                                    <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="2" id="chk_d2"><label class="form-check-label small" for="chk_d2">29-2</label></div>
                                    <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="6" id="chk_d6"><label class="form-check-label small" for="chk_d6">4-6</label></div>
                                    <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="12" id="chk_d12"><label class="form-check-label small" for="chk_d12">9-12</label></div>
                                    <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="16" id="chk_d16"><label class="form-check-label small" for="chk_d16">14-16</label></div>
                                    <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="23" id="chk_d23"><label class="form-check-label small" for="chk_d23">20-23</label></div>
                                    <div class="form-check"><input class="form-check-input" type="checkbox" name="due_day_of_month" value="26" id="chk_d26"><label class="form-check-label small" for="chk_d26">24-26</label></div>
                                </div>
                            </div>

                            <div class="col-md-6">
                                <label class="form-label fw-bold small mb-1">ยอดเงินต้น/ยอดค้างทั้งหมด (บาท)</label>
                                <input type="number" step="any" name="principal" class="form-control form-control-sm" placeholder="0.00" required>
                            </div>
                            <div class="col-md-6">
                                <label class="form-label fw-bold small mb-1">ดอกเบี้ย/วัน (บาท)</label>
                                <input type="number" step="any" name="daily_interest" class="form-control form-control-sm" value="0" required>
                            </div>

                            <div class="col-12" id="installmentDiv" style="display: none;">
                                <label class="form-label fw-bold text-danger small mb-1">ยอดชำระต่องวด (บาท)</label>
                                <input type="number" step="any" name="installment_amount" class="form-control form-control-sm" value="0" placeholder="เช่น 150">
                            </div>
                        </div>
                    </div>
                    <div class="modal-footer py-2">
                        <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ยกเลิก</button>
                        <button type="submit" class="btn btn-success btn-sm fw-bold px-4" onclick="closeAllModals()">บันทึกข้อมูล</button>
                    </div>
                </form>
            </div>
        </div>
    </div>

    <!-- 2. สรุปผลงานวันนี้ (ยอดเก็บสด & ธุรกรรมวันนี้) -->
    <div class="row mb-4">
        <div class="col-md-6 mb-3">
            <div class="card p-3 shadow-sm text-white border-success" style="background: linear-gradient(135deg, #198754, #20c997); cursor: pointer;" data-bs-toggle="modal" data-bs-target="#todayHistoryModal" title="คลิกเพื่อดูรายละเอียด">
                <div class="d-flex justify-content-between align-items-center">
                    <div>
                        <h6 class="mb-1 text-white-50">💵 ยอดเก็บสดวันนี้</h6>
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
                        <h6 class="mb-1 text-white-50">⚡ ธุรกรรมทั้งหมดวันนี้</h6>
                        <h3 class="fw-bold mb-0">{total_today_actions} รายการ</h3>
                    </div>
                    <div class="fs-1 opacity-50">⚡</div>
                </div>
            </div>
        </div>
    </div>

    <!-- Modal ยอดเก็บสดวันนี้ (สีเขียว) -->
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
                                <tr>
                                    <th>ชื่อลูกค้า</th>
                                    <th>ยอดจ่ายจริง</th>
                                    <th>เข้าบัญชี</th>
                                    <th>ค่าปรับ</th>
                                    <th>ส่วนลด</th>
                                    <th>ตัดดอกเบี้ย</th>
                                    <th>ตัดเงินต้น</th>
                                    <th>หมายเหตุ</th>
                                    <th>ผู้ทำรายการ</th>
                                </tr>
                            </thead>
                            <tbody>
                                {today_history_rows if today_history_rows else "<tr><td colspan='9' class='text-center text-muted'>ยังไม่มีการเก็บเงินในวันนี้</td></tr>"}
                            </tbody>
                        </table>
                    </div>
                </div>
                <div class="modal-footer py-2">
                    <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ปิดหน้าต่าง</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Modal ธุรกรรมทั้งหมดวันนี้ (สีฟ้า) -->
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
                                <thead class="table-dark">
                                    <tr><th>ชื่อลูกค้า</th><th>ประเภท</th><th>เบอร์โทร</th><th>ยอดลงทุน</th><th>บัญชีที่ใช้ปล่อย</th><th>เซลล์ผู้ดูแล</th></tr>
                                </thead>
                                <tbody>
                                    {today_new_rows if today_new_rows else "<tr><td colspan='6' class='text-center text-muted'>ไม่มีการเพิ่มเงินลงทุนใหม่ในวันนี้</td></tr>"}
                                </tbody>
                            </table>
                        </div>
                    </div>

                    <div>
                        <h6 class="text-success fw-bold border-bottom pb-2">💵 หมวดที่ 2: รายการรับชำระ / เก็บยอด / ปรับปรุงยอดวันนี้ ({today_payment_count} รายการ)</h6>
                        <div class="table-responsive">
                            <table class="table table-sm table-striped align-middle text-nowrap">
                                <thead class="table-dark">
                                    <tr>
                                        <th>ชื่อลูกค้า</th>
                                        <th>ยอดจ่ายจริง</th>
                                        <th>เข้าบัญชี</th>
                                        <th>ค่าปรับ</th>
                                        <th>ส่วนลด</th>
                                        <th>ตัดดอกเบี้ย</th>
                                        <th>ตัดเงินต้น</th>
                                        <th>หมายเหตุ</th>
                                        <th>ผู้ทำรายการ</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {today_history_rows if today_history_rows else "<tr><td colspan='9' class='text-center text-muted'>ยังไม่มีการทำธุรกรรมรับชำระในวันนี้</td></tr>"}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
                <div class="modal-footer py-2">
                    <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ปิดหน้าต่าง</button>
                </div>
            </div>
        </div>
    </div>

    <!-- 3. ตารางรายการที่ต้องจัดการวันนี้ (Action Table) -->
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
        
        <div class="table-responsive desktop-table-view">
            <table class="table table-striped align-middle text-nowrap">
                <thead class="table-dark">
                    <tr>
                        <th style="position: sticky; left: 0; background-color: #212529; z-index: 3;">ชื่อลูกค้า</th>
                        <th>เบอร์โทร</th>
                        <th>ประเภทการชำระ</th>
                        <th>บัญชีปล่อยกู้</th>
                        <th>โอนเข้าบัญชี</th>
                        <th>วันที่กู้</th>
                        <th>ชำระล่าสุด</th>
                        <th>เงินลงทุน</th>
                        <th>ต้นคงค้าง</th>
                        <th>ยอดที่ชำระมาแล้ว</th>
                        <th>ดอกเบี้ย/วัน</th>
                        <th>เวลาผ่านไป</th>
                        <th>ดอกเบี้ยสะสม</th>
                        <th>สถานะ</th>
                        <th style="position: sticky; right: 0; background-color: #212529; z-index: 3; text-align: center;">จัดการ</th>
                    </tr>
                </thead>
                <tbody>{rows if rows else "<tr><td colspan='15' class='text-center text-muted'>ไม่มีรายการที่ต้องทวงในวันนี้</td></tr>"}</tbody>
            </table>
        </div>

        <div class="mobile-card-view">{cards if cards else "<p class='text-center text-muted'>ไม่มีรายการที่ต้องทวงในวันนี้</p>"}</div>
    </div>

    <!-- 4. สรุปสถานะเงินจมและความเสี่ยง (เงินต้นคงค้าง / ยอดค้างเก่า) -->
    <div class="row mb-4">
        <div class="col-md-6 mb-3">
            <div class="card p-3 shadow-sm text-white" style="background: linear-gradient(135deg, #d97706, #f59e0b); cursor: pointer;" data-bs-toggle="modal" data-bs-target="#debtModal" title="คลิกเพื่อเช็กรายละเอียด">
                <h5>📂 ยอดค้างเก่าคงเหลือ</h5><h3>{total_debt_principal:,.2f} บาท</h3>
            </div>
        </div>
        <div class="col-md-6 mb-3">
            <div class="card p-3 shadow-sm text-white" style="background: linear-gradient(135deg, #b30000, #ff4d4d); cursor: pointer;" data-bs-toggle="modal" data-bs-target="#principalModal" title="คลิกเพื่อเช็กรายละเอียด">
                <h5>💼 เงินต้นคงค้าง</h5><h3>{total_new_principal:,.2f} บาท</h3>
            </div>
        </div>
    </div>

    <!-- Modal ยอดค้างเก่าคงเหลือ -->
    <div class="modal fade" id="debtModal" tabindex="-1">
        <div class="modal-dialog modal-lg modal-dialog-centered">
            <div class="modal-content border-warning">
                <div class="modal-header bg-warning text-dark py-2">
                    <h5 class="modal-title fw-bold fs-6">📂 รายละเอียด: ยอดค้างเก่าคงเหลือ ({total_debt_principal:,.2f} บาท)</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" style="max-height: 65vh; overflow-y: auto;">
                    <div class="table-responsive">
                        <table class="table table-striped align-middle text-nowrap">
                            <thead class="table-dark">
                                <tr><th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>วันที่ตั้งต้น</th><th>ยอดตั้งต้น</th><th>ยอดคงเหลือ</th></tr>
                            </thead>
                            <tbody>{debt_card_rows if debt_card_rows else "<tr><td colspan='5' class='text-center text-muted'>ไม่มีรายการยอดค้างเก่า</td></tr>"}</tbody>
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
                    <h5 class="modal-title fw-bold fs-6">💼 รายละเอียด: เงินต้นคงค้าง ({total_new_principal:,.2f} บาท)</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" style="max-height: 65vh; overflow-y: auto;">
                    <div class="table-responsive">
                        <table class="table table-striped align-middle text-nowrap">
                            <thead class="table-dark">
                                <tr><th>ชื่อลูกค้า</th><th>ประเภท</th><th>เบอร์โทร</th><th>วันที่กู้</th><th>เงินลงทุน</th><th>ต้นคงค้าง</th></tr>
                            </thead>
                            <tbody>{new_principal_rows if new_principal_rows else "<tr><td colspan='6' class='text-center text-muted'>ไม่มีรายการเงินต้นคงค้าง</td></tr>"}</tbody>
                        </table>
                    </div>
                </div>
                <div class="modal-footer py-2"><button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ปิดหน้าต่าง</button></div>
            </div>
        </div>
    </div>

    <!-- 5. สรุปกำไรและสถิติภาพรวม (กำไรสะสม / เงินลงทุนใหม่ แยกตามบัญชี) -->
    <div class="row mb-4">
        <div class="col-md-6 mb-3">
            <div class="card p-3 shadow-sm text-white" style="background: linear-gradient(135deg, #004d99, #3399ff); cursor: pointer;" data-bs-toggle="modal" data-bs-target="#investmentSourceModal" title="คลิกเพื่อดูว่าลงทุนจากบัญชีไหนบ้าง">
                <h5>🔱 เงินลงทุนใหม่ (รวมทั้งหมด)</h5><h3>{total_new_investment:,.2f} บาท</h3>
            </div>
        </div>
        <div class="col-md-6 mb-3">
            <div class="card p-3 shadow-sm text-white" style="background: linear-gradient(135deg, #006622, #00b33c); cursor: pointer;" data-bs-toggle="modal" data-bs-target="#profitModal" title="คลิกเพื่อเช็กรายละเอียด">
                <h5>💰 กำไรสะสมทั้งหมด</h5><h3>{sum_modal_actual_profit:,.2f} บาท</h3>
            </div>
        </div>
    </div>

    <!-- Modal เงินลงทุนใหม่ แยกตามบัญชี -->
    <div class="modal fade" id="investmentSourceModal" tabindex="-1">
        <div class="modal-dialog modal-dialog-centered">
            <div class="modal-content border-primary">
                <div class="modal-header bg-primary text-white py-2">
                    <h5 class="modal-title fw-bold fs-6">🔱 รายละเอียดเงินลงทุนใหม่ แยกตามบัญชีที่ใช้ปล่อย</h5>
                    <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body">
                    <p class="text-muted small">ยอดเงินลงทุนทั้งหมดในระบบแบ่งออกตามแหล่งทุนและบัญชีที่ใช้ปล่อยกู้:</p>
                    <ul class="list-group mb-3">
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span>🩷 ออมสิน</span>
                            <span class="badge" style="background-color: #e83e8c; color: #fff;">{inv_by_source.get('ออมสิน', 0.0):,.2f} บาท</span>
                        </li>
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span>🟡 กรุงศรีอยุธยา</span>
                            <span class="badge text-dark" style="background-color: #ffc107;">{inv_by_source.get('กรุงศรีอยุธยา', 0.0):,.2f} บาท</span>
                        </li>
                        <li class="list-group-item d-flex justify-content-between align-items-center">
                            <span>🟠 TrueMoney Wallet</span>
                            <span class="badge" style="background-color: #dc3545; color: #fff;">{inv_by_source.get('วอลเล็ท', 0.0):,.2f} บาท</span>
                        </li>
                    </ul>
                </div>
                <div class="modal-footer py-2">
                    <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ปิดหน้าต่าง</button>
                </div>
            </div>
        </div>
    </div>

    <!-- Modal กำไรสะสมทั้งหมด -->
    <div class="modal fade" id="profitModal" tabindex="-1">
        <div class="modal-dialog modal-lg modal-dialog-centered">
            <div class="modal-content border-success">
                <div class="modal-header bg-success text-white py-2">
                    <h5 class="modal-title fw-bold fs-6">💰 รายละเอียด: กำไรสะสมทั้งหมด (หักส่วนลดแล้ว: {sum_modal_actual_profit:,.2f} บาท)</h5>
                    <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                </div>
                <div class="modal-body" style="max-height: 65vh; overflow-y: auto;">
                    <div class="table-responsive">
                        <table class="table table-striped align-middle text-nowrap">
                            <thead class="table-dark">
                                <tr><th>ชื่อลูกค้า</th><th>ประเภท</th><th>กำไร/ดอกเบี้ย</th><th>ค่าปรับจริง</th><th>ส่วนลด</th><th>รวมสุทธิ</th><th>วันที่ชำระล่าสุด</th></tr>
                            </thead>
                            <tbody>{profit_card_rows if profit_card_rows else "<tr><td colspan='7' class='text-center text-muted'>ยังไม่มีกำไรสะสม</td></tr>"}</tbody>
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

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    if 'admin' not in session: return redirect(url_for('login'))
    try:
        p_val = float(request.form.get('principal', 0))
        custom_start_date = request.form.get('start_date')
        parsed_date = datetime.strptime(custom_start_date, '%Y-%m-%d').date() if custom_start_date else get_thai_today()
        current_sales = session.get('admin', 'unknown')
        d_interest = float(request.form.get('daily_interest', 0))
        tx_type = request.form.get('type')
        funding_source = request.form.get('funding_source', 'ออมสิน')
        
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
            funding_source=funding_source, receiving_account=funding_source
        )
        db.session.add(new_tx)

        if p_val > 0:
            db.session.add(BankExpenseLog(
                expense_date=parsed_date,
                account_name=funding_source,
                amount=p_val,
                note=f"ปล่อยกู้ใหม่: {request.form.get('customer_name')}",
                admin_name=current_sales
            ))
            adj = BankAdjustment.query.filter_by(account_name=funding_source).first()
            if adj:
                adj.adjustment_amount = max(0.0, adj.adjustment_amount - p_val)
            else:
                db.session.add(BankAdjustment(account_name=funding_source, adjustment_amount=0.0))

        db.session.commit()
        db.session.remove()
    except Exception as e: print("Error:", e)
    return redirect(url_for('index'))

@app.route('/transfer_bank_money', methods=['POST'])
def transfer_bank_money():
    if 'admin' not in session: return redirect(url_for('login'))
    try:
        from_acc = request.form.get('from_account')
        to_acc = request.form.get('to_account')
        amount = float(request.form.get('transfer_amount', 0))
        note_text = request.form.get('note', '').strip()

        if from_acc != to_acc and amount > 0:
            adj_from = BankAdjustment.query.filter_by(account_name=from_acc).first()
            if adj_from:
                adj_from.adjustment_amount = max(0.0, adj_from.adjustment_amount - amount)
            else:
                db.session.add(BankAdjustment(account_name=from_acc, adjustment_amount=0.0))

            adj_to = BankAdjustment.query.filter_by(account_name=to_acc).first()
            if adj_to:
                adj_to.adjustment_amount += amount
            else:
                db.session.add(BankAdjustment(account_name=to_acc, adjustment_amount=amount))

            db.session.add(BankExpenseLog(
                expense_date=get_thai_today(),
                account_name=from_acc,
                amount=amount,
                note=f"โยกเงินไปพักที่ {to_acc}: {note_text}",
                admin_name=session.get('admin')
            ))

            db.session.commit()
    except Exception as e:
        print("Transfer error:", e)
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
            if adj:
                adj.adjustment_amount = val
            else:
                db.session.add(BankAdjustment(account_name=acc_name, adjustment_amount=val))
        db.session.commit()
    except Exception as e:
        print("Adjustment error:", e)
    db.session.remove()
    return redirect(url_for('index'))

@app.route('/withdraw_bank_money', methods=['POST'])
def withdraw_bank_money():
    if 'admin' not in session: return redirect(url_for('login'))
    try:
        acc_name = request.form.get('account_name', 'ออมสิน')
        withdraw_amt = float(request.form.get('withdraw_amount', 0))
        note_text = request.form.get('note', '').strip()

        if withdraw_amt > 0:
            db.session.add(BankExpenseLog(
                expense_date=get_thai_today(),
                account_name=acc_name,
                amount=withdraw_amt,
                note=note_text,
                admin_name=session.get('admin')
            ))

            adj = BankAdjustment.query.filter_by(account_name=acc_name).first()
            if adj:
                adj.adjustment_amount = max(0.0, adj.adjustment_amount - withdraw_amt)
            else:
                db.session.add(BankAdjustment(account_name=acc_name, adjustment_amount=0.0))
            
            db.session.commit()
    except Exception as e:
        print("Withdraw error:", e)
    db.session.remove()
    return redirect(url_for('index'))

@app.route('/delete_expense/<int:exp_id>')
def delete_expense(exp_id):
    if 'admin' not in session: return redirect(url_for('login'))
    exp = BankExpenseLog.query.get_or_404(exp_id)
    adj = BankAdjustment.query.filter_by(account_name=exp.account_name).first()
    if adj:
        adj.adjustment_amount += exp.amount
    db.session.delete(exp)
    db.session.commit()
    db.session.remove()
    return redirect(url_for('index'))

@app.route('/customer_details/<path:cust_name>')
def customer_details(cust_name):
    if 'admin' not in session: return redirect(url_for('login'))
    
    clean_name = cust_name
    if clean_name.startswith("กำไรสะสม: "):
        clean_name = clean_name.replace("กำไรสะสม: ", "").strip()
    
    txs = Transaction.query.filter(Transaction.customer_name.ilike(f"%{clean_name}%")).order_by(Transaction.start_date.desc()).all()
    for tx in txs:
        calculate_tx_values(tx)

    rows = ""
    modals_html = ""
    for tx in txs:
        badge_color = 'bg-success' if tx.principal <= 0 else ('bg-info text-dark' if tx.status == 'ตัดยอดบางส่วน' else 'bg-success')
        if tx.principal <= 0 or tx.status == 'คืนแล้ว': badge_color = 'bg-danger'
        
        start_date_str = tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'
        last_pay_str = tx.last_payment_date.strftime('%d/%m/%Y') if tx.last_payment_date else '-'
        closed_date_str = tx.closed_date.strftime('%Y-%m-%d') if tx.closed_date else ''
        
        selected_normal = "selected" if tx.status == "ปกติ" else ""
        selected_partial = "selected" if tx.status == "ตัดยอดบางส่วน" else ""

        rows += f"""
        <tr>
            <td><span class="badge bg-secondary">{tx.type}</span></td>
            <td>{get_funding_badge(tx.funding_source or 'ออมสิน')}</td>
            <td>{get_funding_badge(tx.receiving_account or 'ออมสิน')}</td>
            <td>{start_date_str}</td>
            <td>{last_pay_str}</td>
            <td>{tx.original_principal:,.2f}</td>
            <td>{tx.principal:,.2f}</td>
            <td><a href="/history/{tx.id}" target="_blank" class="text-primary fw-bold text-decoration-none" title="คลิกเพื่อดูประวัติการจ่าย">{tx.total_paid:,.2f}</a></td>
            <td>{tx.daily_interest:,.2f}</td>
            <td class="text-danger fw-bold">{tx.accumulated_interest:,.2f}</td>
            <td><span class="badge {badge_color}">{'คืนแล้ว' if tx.principal <= 0 else tx.status}</span></td>
            <td class="text-center">
                <div class="d-flex justify-content-center gap-1 align-items-center">
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
                                <div class="text-end"><small class="text-muted d-block" style="font-size: 0.75rem;">ดอกเบี้ยสะสม</small><b class="text-danger" id="accInterestDisplay{tx.id}">{tx.accumulated_interest:,.2f} บาท</b></div>
                            </div>
                            <div class="mb-2 p-2 bg-warning bg-opacity-10 rounded border border-warning">
                                <label class="form-label text-dark fw-bold mb-1" style="font-size: 0.85rem;">📅 วันที่ปิดยอด / วันที่คืนยอด</label>
                                <input type="date" name="closed_date" class="form-control form-control-sm border-warning bg-white" id="closedDate{tx.id}" value="{closed_date_str}">
                            </div>

                            <div class="mb-2 p-2 bg-success bg-opacity-10 rounded border border-success">
                                <label class="form-label text-success fw-bold mb-1" style="font-size: 0.85rem;">📥 ลูกค้าโอนเข้าบัญชี / ช่องทางไหน:</label>
                                <select name="receiving_account" class="form-select form-select-sm border-success">
                                    <option value="ออมสิน" selected>🩷 ออมสิน (020-409-437-819)</option>
                                    <option value="กรุงศรีอยุธยา">🟢 กรุงศรีอยุธยา (803-931-9819)</option>
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
                            <div class="mb-2">
                                <label class="form-label text-dark fw-bold mb-1" style="font-size: 0.85rem;">📝 หมายเหตุการชำระ</label>
                                <input type="text" name="note" class="form-control form-control-sm" placeholder="เช่น จ่ายเฉพาะค่าปรับ, โอนผ่าน KTB">
                            </div>
                            <div class="mb-1">
                                <label class="form-label text-success fw-bold mb-1" style="font-size: 0.85rem;">สถานะรายการ</label>
                                <select name="new_status" class="form-select form-select-sm border-success" id="newStatus{tx.id}">
                                    <option value="ปกติ" {selected_normal}>ปกติ</option>
                                    <option value="ตัดยอดบางส่วน" {selected_partial}>ตัดยอดบางส่วน</option>
                                </select>
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
                    <tr>
                        <th>ประเภทบัญชี</th>
                        <th>บัญชีปล่อยกู้</th>
                        <th>โอนเข้าบัญชีล่าสุด</th>
                        <th>วันที่กู้</th>
                        <th>ชำระล่าสุด</th>
                        <th>เงินลงทุน</th>
                        <th>ต้นคงค้าง</th>
                        <th>ชำระแล้ว</th>
                        <th>ดอก/วัน</th>
                        <th>ดอกเบี้ยสะสม</th>
                        <th>สถานะ</th>
                        <th class="text-center">จัดการ</th>
                    </tr>
                </thead>
                <tbody>{rows if rows else "<tr><td colspan='12' class='text-center text-muted'>ไม่พบข้อมูลรายการของลูกค้ารายนี้</td></tr>"}</tbody>
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
    sum_modal_actual_profit = 0.0
    for tx in all_txs_ever:
        if tx.type == 'ยอดค้างเก่า':
            net_earned = max(0.0, (tx.original_principal - tx.principal))
        else:
            hist_sum = sum(h.interest_paid for h in tx.histories) if tx.histories else 0.0
            net_earned = max(tx.paid_interest, hist_sum)
            
        tx_fine_sum = sum(h.fine_amount for h in tx.histories) if tx.histories else 0.0
        tx_discount_sum = sum(h.discount_amount for h in tx.histories) if tx.histories else 0.0
        total_item_profit = net_earned + tx_fine_sum - tx_discount_sum
        if total_item_profit != 0 or net_earned > 0 or tx_fine_sum > 0 or tx_discount_sum > 0:
            sum_modal_actual_profit += total_item_profit

    monthly_data = defaultdict(lambda: {
        'count_tx': set(), 
        'new_investment': 0.0, 
        'new_collected': 0.0, 
        'debt_collected': 0.0, 
        'total_fine': 0.0, 
        'total_discount': 0.0, 
        'month_profit': 0.0
    })
    
    for tx in all_txs_ever:
        ym_start = tx.start_date.strftime('%Y-%m') if tx.start_date else '2026-09'
        monthly_data[ym_start]['count_tx'].add(tx.id)
        
        if tx.type != 'ยอดค้างเก่า':
            monthly_data[ym_start]['new_investment'] += tx.original_principal
            hist_interest = sum(h.interest_paid for h in tx.histories) if tx.histories else tx.paid_interest
            net_earned = max(tx.paid_interest, hist_interest)
            monthly_data[ym_start]['new_collected'] += net_earned
            monthly_data[ym_start]['month_profit'] += net_earned
        else:
            debt_earned = max(0.0, tx.original_principal - tx.principal)
            monthly_data[ym_start]['debt_collected'] += debt_earned
            monthly_data[ym_start]['month_profit'] += debt_earned

        if tx.histories:
            for h in tx.histories:
                if h.payment_date:
                    ym_h = h.payment_date.strftime('%Y-%m')
                    monthly_data[ym_h]['total_fine'] += h.fine_amount
                    monthly_data[ym_h]['total_discount'] += h.discount_amount
                    monthly_data[ym_h]['month_profit'] += (h.fine_amount - h.discount_amount)

    monthly_rows = ""
    sum_new_inv = 0.0
    sum_new_col = 0.0
    sum_debt_col = 0.0
    sum_fine = 0.0
    sum_disc = 0.0
    sum_profit = 0.0

    for ym, d in sorted(monthly_data.items(), reverse=True):
        sum_new_inv += d['new_investment']
        sum_new_col += d['new_collected']
        sum_debt_col += d['debt_collected']
        sum_fine += d['total_fine']
        sum_disc += d['total_discount']
        sum_profit += d['month_profit']

        monthly_rows += f"""
        <tr>
            <td><span class='text-danger fw-bold'>📅 {ym}</span></td>
            <td><span class='badge bg-secondary px-2 py-1'>{len(d['count_tx'])} รายการ</span></td>
            <td><a href='/monthly_details/{ym}/new_inv' class='text-primary fw-bold text-decoration-none'>{d['new_investment']:,.2f}</a></td>
            <td><a href='/monthly_details/{ym}/new_col' class='text-success fw-bold text-decoration-none'>{d['new_collected']:,.2f}</a></td>
            <td><a href='/monthly_details/{ym}/debt_col' class='text-warning text-dark fw-bold text-decoration-none'>{d['debt_collected']:,.2f}</a></td>
            <td><a href='/monthly_details/{ym}/fine' class='text-warning text-dark fw-bold text-decoration-none'>{d['total_fine']:,.2f}</a></td>
            <td><a href='/monthly_details/{ym}/discount' class='text-danger fw-bold text-decoration-none'>-{d['total_discount']:,.2f}</a></td>
            <td><a href='/monthly_details/{ym}/profit' class='text-success fw-bold text-decoration-none'>{d['month_profit']:,.2f}</a></td>
        </tr>
        """
    
    monthly_rows += f"""
    <tr class="table-dark fw-bold">
        <td colspan="2" class="text-end">รวมทั้งสิ้น:</td>
        <td>{sum_new_inv:,.2f}</td>
        <td>{sum_new_col:,.2f}</td>
        <td>{sum_debt_col:,.2f}</td>
        <td>{sum_fine:,.2f}</td>
        <td class="text-danger">-{sum_disc:,.2f}</td>
        <td class="text-success fs-6">{sum_modal_actual_profit:,.2f}</td>
    </tr>
    """

    content = f"""
    <div class="card p-4 shadow-sm border-warning">
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <h4 class="mb-0 fs-5 text-danger fw-bold">📊 ตารางสรุปยอดรายรับและกำไร</h4>
        </div>
        <div class="table-responsive">
            <table class="table table-bordered align-middle text-nowrap">
                <thead class="table-dark">
                    <tr>
                        <th>เดือนที่ชำระ</th>
                        <th>รายการ</th>
                        <th>ทุนที่ลูกค้าใหม่กู้</th>
                        <th>ยอดเก็บจากลูกค้าใหม่</th>
                        <th>ยอดเก็บจากลูกค้าเก่า</th>
                        <th>ยอดค่าปรับ</th>
                        <th>ยอดส่วนลด</th>
                        <th>กำไรสะสมเดือนนี้</th>
                    </tr>
                </thead>
                <tbody>
                    {monthly_rows}
                </tbody>
            </table>
        </div>
    </div>
    """
    html = BASE_LAYOUT.replace('{% block header %}4. สรุปยอดผลประกอบการรายเดือน{% endblock %}', 'สรุปยอดรายเดือน').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="สรุปยอดรายเดือน", page="monthly")

@app.route('/monthly_details/<ym>/<category>')
def monthly_details(ym, category):
    if 'admin' not in session: return redirect(url_for('login'))
    try:
        year_val, month_val = ym.split('-')
        year_i, month_i = int(year_val), int(month_val)
    except:
        return redirect(url_for('monthly_summary'))

    if category == 'new_inv':
        txs = Transaction.query.filter(db.extract('year', Transaction.start_date) == year_i, db.extract('month', Transaction.start_date) == month_i, Transaction.type != 'ยอดค้างเก่า').all()
        title_str = f"ทุนที่ลูกค้าใหม่กู้ ประจำเดือน {ym}"
    elif category == 'new_col':
        txs = Transaction.query.filter(db.extract('year', Transaction.start_date) == year_i, db.extract('month', Transaction.start_date) == month_i, Transaction.type != 'ยอดค้างเก่า').all()
        title_str = f"ยอดเก็บจากลูกค้าใหม่ ประจำเดือน {ym}"
    elif category == 'debt_col':
        txs = Transaction.query.filter(db.extract('year', Transaction.start_date) == year_i, db.extract('month', Transaction.start_date) == month_i, Transaction.type == 'ยอดค้างเก่า').all()
        title_str = f"ยอดเก็บจากลูกค้าเก่า (ยอดค้างเก่า) ประจำเดือน {ym}"
    else:
        histories = PaymentHistory.query.filter(db.extract('year', PaymentHistory.payment_date) == year_i, db.extract('month', PaymentHistory.payment_date) == month_i).all()
        tx_ids = [h.transaction_id for h in histories if (h.fine_amount > 0 if category == 'fine' else h.discount_amount > 0)]
        txs = Transaction.query.filter(Transaction.id.in_(tx_ids)).all() if tx_ids else []
        title_str = f"รายการ{'ค่าปรับ' if category == 'fine' else 'ส่วนลด'} ประจำเดือน {ym}"

    rows = ""
    for tx in txs:
        calculate_tx_values(tx)
        badge_color = 'bg-success' if tx.principal <= 0 else ('bg-info text-dark' if tx.status == 'ตัดยอดบางส่วน' else 'bg-success')
        if tx.principal <= 0 or tx.status == 'คืนแล้ว': badge_color = 'bg-danger'

        start_date_str = tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'
        closed_date_str = tx.closed_date.strftime('%d/%m/%Y') if tx.closed_date else '-'
        
        actual_paid_total = 0.0
        if tx.histories:
            for h in tx.histories:
                actual_paid_total += (h.pay_amount if h.pay_amount > 0 else (h.interest_paid + h.principal_reduced + h.fine_amount - h.discount_amount))
        else:
            actual_paid_total = tx.total_paid

        rows += f"""
        <tr>
            <td><a href="/customer_details/{tx.customer_name}" class="text-dark text-decoration-none fw-bold">{tx.customer_name}</a></td>
            <td>{tx.phone or '-'}</td>
            <td><span class="badge bg-secondary">{tx.type}</span></td>
            <td>{get_funding_badge(tx.funding_source or 'ออมสิน')}</td>
            <td>{get_funding_badge(tx.receiving_account or 'ออมสิน')}</td>
            <td>{start_date_str}</td>
            <td>{closed_date_str}</td>
            <td>{tx.original_principal:,.2f}</td>
            <td>{tx.principal:,.2f}</td>
            <td>{actual_paid_total:,.2f}</td>
            <td><span class="badge {badge_color}">{'คืนแล้ว' if tx.principal <= 0 else tx.status}</span></td>
        </tr>
        """

    content = f"""
    <div class="card p-4 shadow-sm border-warning">
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <h4 class="mb-0 fs-5 text-danger fw-bold">📋 {title_str}</h4>
            <a href="/monthly_summary" class="btn btn-sm btn-secondary fw-bold">⬅️ กลับไปหน้าสรุปรายเดือน</a>
        </div>
        <div class="table-responsive">
            <table class="table table-striped align-middle text-nowrap">
                <thead class="table-dark">
                    <tr><th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>ประเภท</th><th>บัญชีปล่อยกู้</th><th>โอนเข้าบัญชี</th><th>วันที่กู้</th><th>วันที่ปิด/ชำระ</th><th>เงินลงทุน</th><th>ต้นคงค้าง</th><th>ยอดจ่ายจริง</th><th>สถานะ</th></tr>
                </thead>
                <tbody>{rows if txs else "<tr><td colspan='11' class='text-center text-muted'>ไม่มีรายการในหมวดนี้สำหรับเดือนนี้</td></tr>"}</tbody>
            </table>
        </div>
    </div>
    """
    html = BASE_LAYOUT.replace('{% block header %}รายละเอียดประจำเดือน{% endblock %}', title_str).replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title=title_str, page="monthly")

@app.route('/members_scheduled_all')
def members_scheduled_all():
    if 'admin' not in session: return redirect(url_for('login'))
    all_txs_for_select = Transaction.query.filter(Transaction.principal > 0).order_by(Transaction.customer_name.asc()).all()
    for t in all_txs_for_select: calculate_tx_values(t)

    sections = [
        ("2", "📅 รอบช่วงวันที่ 29-2 (รอบข้ามเดือน)", ["2", "29", "30", "31", "1"]),
        ("6", "📅 รอบช่วงวันที่ 4-6", ["6"]),
        ("12", "📅 รอบช่วงวันที่ 9-12", ["12"]),
        ("16", "📅 รอบช่วงวันที่ 14-16", ["16"]),
        ("23", "📅 รอบช่วงวันที่ 20-23", ["23"]),
        ("26", "📅 รอบช่วงวันที่ 24-26", ["26"])
    ]

    all_sections_html = ""
    for day_val, section_title, target_codes in sections:
        checkboxes_html = ""
        for t in all_txs_for_select:
            checkboxes_html += f"""
            <div class="form-check customer-item-{day_val}" data-name="{t.customer_name}">
                <input class="form-check-input" type="checkbox" name="transaction_ids" value="{t.id}" id="chk_{day_val}_{t.id}">
                <label class="form-check-label small" for="chk_{day_val}_{t.id}">
                    <b>{t.customer_name}</b> (ทุน: {t.original_principal:,.0f} | ปัจจุบัน: {t.schedule_type})
                </label>
            </div>
            """

        pull_section = f"""
        <div class="card p-3 mb-3 bg-light border-warning shadow-sm">
            <button class="btn btn-outline-danger btn-sm fw-bold mb-2 w-100 text-start" type="button" data-bs-toggle="collapse" data-bs-target="#collapseAdd{day_val}">
                ➕ เลือกเพิ่มรายชื่อเข้ากลุ่มนี้ ({section_title})
            </button>
            <div class="collapse" id="collapseAdd{day_val}">
                <form action="/quick_assign_schedule_multi" method="POST" class="mt-2">
                    <input type="hidden" name="target_schedule" value="กำหนดจ่ายประจำเดือน">
                    <input type="hidden" name="target_day" value="{day_val}">
                    <div class="border rounded p-2 bg-white mb-2" style="max-height: 160px; overflow-y: auto;">
                        {checkboxes_html if checkboxes_html else '<p class="text-muted small mb-0">ไม่มีรายชื่อในระบบ</p>'}
                    </div>
                    <button type="submit" class="btn btn-sm btn-success fw-bold w-100">📥 บันทึกดึงรายชื่อที่เลือกเข้ากลุ่มนี้</button>
                </form>
            </div>
        </div>
        """

        all_active_txs = Transaction.query.filter(Transaction.principal > 0, Transaction.schedule_type == 'กำหนดจ่ายประจำเดือน').all()
        txs = [t for t in all_active_txs if t.due_day_of_month and any(c in target_codes for c in t.due_day_of_month.split(','))]

        rows = ""
        for t in txs:
            calculate_tx_values(t)
            start_str = t.start_date.strftime('%d/%m/%Y') if t.start_date else '-'
            badge_color = 'bg-success' if t.status == 'ปกติ' else ('bg-info text-dark' if t.status == 'ตัดยอดบางส่วน' else 'bg-danger')
            rows += f"<tr><td><a href='/customer_details/{t.customer_name}' class='text-dark fw-bold text-decoration-none'>{t.customer_name}</a></td><td>{t.phone or '-'}</td><td>{t.sales_name}</td><td>{get_funding_badge(t.funding_source or 'ออมสิน')}</td><td>{get_funding_badge(t.receiving_account or 'ออมสิน')}</td><td>{start_str}</td><td>{t.original_principal:,.2f}</td><td>{t.principal:,.2f}</td><td><strong>{t.total_paid:,.2f}</strong></td><td><span class='badge {badge_color}'>{t.status}</span></td></tr>"

        all_sections_html += f"""
        <div class="card p-3 mb-4 shadow-sm border-warning">
            <h5 class="text-danger fw-bold mb-3">{section_title}</h5>
            {pull_section}
            <div class="table-responsive">
                <table class="table table-striped text-nowrap align-middle">
                    <thead class="table-dark">
                        <tr><th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>เซลล์</th><th>บัญชีปล่อย</th><th>โอนเข้าบัญชี</th><th>วันที่กู้</th><th>ลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th><th>สถานะ</th></tr>
                    </thead>
                    <tbody>{rows if rows else "<tr><td colspan='10' class='text-center text-muted'>ยังไม่มีสมาชิกในรอบวันนี้</td></tr>"}</tbody>
                </table>
            </div>
        </div>
        """

    content = f"""
    <div class="mb-4"><h4 class="text-danger fw-bold">📅 บริหารจัดการสมาชิก: กำหนดจ่ายประจำเดือน (แบ่งตามช่วงวันเลท)</h4></div>
    {all_sections_html}
    """
    html = BASE_LAYOUT.replace('{% block header %}1.3 กำหนดจ่ายประจำเดือน{% endblock %}', '1.3 กำหนดจ่ายประจำเดือน').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="กำหนดจ่ายประจำเดือน", page="members_scheduled_all")

@app.route('/quick_assign_schedule_multi', methods=['POST'])
def quick_assign_schedule_multi():
    if 'admin' not in session: return redirect(url_for('login'))
    tx_ids = request.form.getlist('transaction_ids')
    target_schedule = request.form.get('target_schedule')
    target_day = request.form.get('target_day')
    if tx_ids:
        for tx_id in tx_ids:
            tx = Transaction.query.get(int(tx_id))
            if tx:
                tx.schedule_type = target_schedule
                if target_schedule == 'กำหนดจ่ายประจำเดือน' and target_day:
                    current_list = tx.due_day_of_month.split(',') if tx.due_day_of_month else []
                    if target_day not in current_list: current_list.append(target_day)
                    tx.due_day_of_month = ",".join(current_list)
        db.session.commit()
    db.session.remove()
    return redirect(request.referrer or url_for('index'))

@app.route('/members')
def members():
    if 'admin' not in session: return redirect(url_for('login'))
    txs = Transaction.query.filter(Transaction.principal > 0).order_by(Transaction.customer_name.asc()).all()
    for t in txs: calculate_tx_values(t)
    rows = "".join([f"<tr><td><a href='/customer_details/{t.customer_name}' class='text-dark text-decoration-none fw-bold'>{t.customer_name}</a></td><td>{t.phone or '-'}</td><td><span class='badge bg-danger'>{t.sales_name}</span></td><td>{get_funding_badge(t.funding_source or 'ออมสิน')}</td><td>{get_funding_badge(t.receiving_account or 'ออมสิน')}</td><td>{t.schedule_type}</td><td>{t.start_date.strftime('%d/%m/%Y')}</td><td>{t.original_principal:,.2f}</td><td>{t.principal:,.2f}</td><td><strong>{t.total_paid:,.2f}</strong></td></tr>" for t in txs])
    content = f"""<div class="card p-4 shadow-sm border-warning"><h4 class="mb-3 fs-5 text-danger fw-bold">👥 สมาชิกทั้งหมดในระบบ</h4><div class="table-responsive"><table class="table table-striped text-nowrap align-middle"><thead class="table-dark"><tr><th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>เซลล์</th><th>บัญชีปล่อย</th><th>โอนเข้าบัญชี</th><th>ประเภท</th><th>วันที่กู้</th><th>ลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th></tr></thead><tbody>{rows if rows else "<tr><td colspan='10' class='text-center text-muted'>ยังไม่มีข้อมูล</td></tr>"}</tbody></table></div></div>"""
    html = BASE_LAYOUT.replace('{% block header %}สมาชิกทั้งหมด{% endblock %}', 'สมาชิกทั้งหมด').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="สมาชิกทั้งหมด", page="members")

@app.route('/members_daily')
def members_daily():
    if 'admin' not in session: return redirect(url_for('login'))
    txs = Transaction.query.filter(Transaction.principal > 0, Transaction.schedule_type == 'จ่ายทุกวัน').order_by(Transaction.customer_name.asc()).all()
    for t in txs: calculate_tx_values(t)
    rows = "".join([f"<tr><td><a href='/customer_details/{t.customer_name}' class='text-dark text-decoration-none fw-bold'>{t.customer_name}</a></td><td>{t.phone or '-'}</td><td>{t.sales_name}</td><td>{get_funding_badge(t.funding_source or 'ออมสิน')}</td><td>{get_funding_badge(t.receiving_account or 'ออมสิน')}</td><td>{t.original_principal:,.2f}</td><td>{t.principal:,.2f}</td><td><strong>{t.total_paid:,.2f}</strong></td></tr>" for t in txs])
    html = BASE_LAYOUT.replace('{% block header %}1.1 จ่ายทุกวัน{% endblock %}', 'จ่ายทุกวัน').replace('{% block content %}{% endblock %}', f'<div class="card p-4 shadow-sm border-warning"><table class="table table-striped text-nowrap"><thead><tr><th>ชื่อ</th><th>เบอร์</th><th>เซลล์</th><th>บัญชีปล่อย</th><th>โอนเข้าบัญชี</th><th>ลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th></tr></thead><tbody>{rows}</tbody></table></div>')
    return render_template_string(html, title="จ่ายทุกวัน", page="members_daily")

@app.route('/members_unscheduled')
def members_unscheduled():
    if 'admin' not in session: return redirect(url_for('login'))
    txs = Transaction.query.filter(Transaction.principal > 0, Transaction.schedule_type == 'ยังไม่มีกำหนดจ่าย').order_by(Transaction.customer_name.asc()).all()
    for t in txs: calculate_tx_values(t)
    rows = "".join([f"<tr><td><a href='/customer_details/{t.customer_name}' class='text-dark text-decoration-none fw-bold'>{t.customer_name}</a></td><td>{t.phone or '-'}</td><td>{t.sales_name}</td><td>{get_funding_badge(t.funding_source or 'ออมสิน')}</td><td>{get_funding_badge(t.receiving_account or 'ออมสิน')}</td><td>{t.original_principal:,.2f}</td><td>{t.principal:,.2f}</td><td><strong>{t.total_paid:,.2f}</strong></td></tr>" for t in txs])
    html = BASE_LAYOUT.replace('{% block header %}1.2 ยังไม่มีกำหนดจ่าย{% endblock %}', 'ยังไม่มีกำหนดจ่าย').replace('{% block content %}{% endblock %}', f'<div class="card p-4 shadow-sm border-warning"><table class="table table-striped"><thead><tr><th>ชื่อ</th><th>เบอร์</th><th>เซลล์</th><th>บัญชีปล่อย</th><th>โอนเข้าบัญชี</th><th>ลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th></tr></thead><tbody>{rows}</tbody></table></div>')
    return render_template_string(html, title="ยังไม่มีกำหนดจ่าย", page="members_unscheduled")

@app.route('/all_transactions')
def all_transactions():
    if 'admin' not in session: return redirect(url_for('login'))
    search_query = request.args.get('search', '').strip()
    query = Transaction.query
    if search_query:
        query = query.filter((Transaction.customer_name.ilike(f"%{search_query}%")) | (Transaction.phone.ilike(f"%{search_query}%")))
    
    transactions = query.all()
    for tx in transactions: calculate_tx_values(tx)

    active_txs = [t for t in transactions if t.principal > 0]
    closed_txs = [t for t in transactions if t.principal <= 0]

    def build_rows(tx_list, is_closed=False):
        res = ""
        for tx in tx_list:
            badge_color = 'bg-danger' if is_closed else ('bg-success' if tx.status == 'ปกติ' else 'bg-info text-dark')
            res += f"""
            <tr>
                <td><a href="/customer_details/{tx.customer_name}" class="text-dark text-decoration-none fw-bold">{tx.customer_name}</a></td>
                <td>{tx.phone or '-'}</td>
                <td><span class="badge bg-secondary">{tx.type}</span></td>
                <td>{get_funding_badge(tx.funding_source or 'ออมสิน')}</td>
                <td>{get_funding_badge(tx.receiving_account or 'ออมสิน')}</td>
                <td>{tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'}</td>
                <td>{tx.original_principal:,.2f}</td>
                <td>{tx.principal:,.2f}</td>
                <td><strong class="text-primary">{tx.total_paid:,.2f}</strong></td>
                <td><span class="badge {badge_color}">{'คืนแล้ว' if is_closed else tx.status}</span></td>
                <td><a href="/" class="btn btn-sm btn-success-light">จัดการ</a></td>
            </tr>
            """
        return res

    content = f"""
    <div class="card p-4 shadow-sm border-warning mb-4">
        <h4 class="mb-3 fs-5 text-danger fw-bold">📋 รายการบัญชีที่ยังไม่ปิด</h4>
        <div class="table-responsive">
            <table class="table table-striped align-middle text-nowrap">
                <thead class="table-dark"><tr><th>ชื่อลูกค้า</th><th>เบอร์</th><th>ประเภท</th><th>บัญชีปล่อย</th><th>โอนเข้าบัญชี</th><th>วันที่กู้</th><th>ลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th><th>สถานะ</th><th>จัดการ</th></tr></thead>
                <tbody>{build_rows(active_txs, False) if active_txs else "<tr><td colspan='11' class='text-center text-muted'>ไม่มีรายการ</td></tr>"}</tbody>
            </table>
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
    cw.writerow(['ID', 'Type', 'CustomerName', 'Phone', 'SalesName', 'StartDate', 'ClosedDate', 'OriginalPrincipal', 'Principal', 'DailyInterest', 'PaidInterest', 'Status', 'InstallmentAmount', 'TotalPaid', 'ScheduleType', 'DueDayOfMonth', 'FundingSource', 'ReceivingAccount'])
    for t in Transaction.query.all():
        cw.writerow([t.id, t.type, t.customer_name, t.phone, t.sales_name, t.start_date, t.closed_date, t.original_principal, t.principal, t.daily_interest, t.paid_interest, t.status, t.installment_amount, t.paid_interest, t.schedule_type, t.due_day_of_month, t.funding_source, t.receiving_account])
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
                db.session.add(Transaction(
                    type=row.get('Type', 'เงินฉุกเฉิน'), customer_name=row.get('CustomerName', 'ไม่ระบุ'),
                    phone=row.get('Phone', ''), sales_name=row.get('SalesName', session.get('admin')),
                    start_date=get_thai_today(), original_principal=float(row.get('OriginalPrincipal', 0)),
                    principal=float(row.get('Principal', 0)), daily_interest=float(row.get('DailyInterest', 0)),
                    initial_daily_interest=float(row.get('DailyInterest', 0)), paid_interest=float(row.get('PaidInterest', 0)),
                    status=row.get('Status', 'ปกติ'), schedule_type=row.get('ScheduleType', 'จ่ายทุกวัน'),
                    funding_source=row.get('FundingSource', 'ออมสิน'), receiving_account=row.get('ReceivingAccount', 'ออมสิน')
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
    receiving_account = request.form.get('receiving_account', 'ออมสิน')
    tx.receiving_account = receiving_account 
    
    thai_today = get_thai_today()
    pay_amount = float(request.form.get('pay_amount', 0) or 0)
    discount_amt = float(request.form.get('discount_amount', 0))
    fine_amt = float(request.form.get('fine_amount', 0))
    new_status = request.form.get('new_status')
    closed_date_str = request.form.get('closed_date')
    note_text = request.form.get('note', '').strip()
    
    tx.closed_date = datetime.strptime(closed_date_str, '%Y-%m-%d').date() if closed_date_str else None
    calc_end_date = tx.closed_date if tx.closed_date else thai_today
    days = max(1, (calc_end_date - tx.start_date).days + 1)
        
    current_effective_daily = tx.initial_daily_interest * (tx.principal / tx.original_principal) if tx.original_principal > 0 else tx.daily_interest
    total_acc_interest = max(0.0, (current_effective_daily * days) - tx.paid_interest)

    tx.last_payment_date = thai_today
    actual_interest_paid, actual_principal_reduced = 0.0, 0.0

    if payment_type == 'adjust':
        adjust_amount = float(request.form.get('adjust_amount', 0))
        tx.principal = max(0.0, tx.principal + adjust_amount)
        actual_principal_reduced = -adjust_amount
        if pay_amount <= 0: pay_amount = abs(adjust_amount)
        if not note_text: note_text = f"ปรับปรุงยอดเงินต้น: {adjust_amount:+,.2f}"
    elif payment_type == 'full':
        net_interest_earned = max(0.0, total_acc_interest - discount_amt)
        tx.paid_interest += net_interest_earned
        actual_interest_paid = net_interest_earned
        actual_principal_reduced = tx.principal
        if pay_amount <= 0: pay_amount = net_interest_earned + tx.principal
        tx.principal = 0.0
        tx.status = 'คืนแล้ว'
        if not tx.closed_date: tx.closed_date = thai_today
    else:
        net_acc_interest = max(0.0, total_acc_interest - discount_amt)
        if pay_amount > 0:
            if pay_amount >= net_acc_interest:
                actual_interest_paid = net_acc_interest
                remainder = pay_amount - net_acc_interest
                tx.paid_interest += net_acc_interest
                if remainder > 0:
                    tx.principal = max(0.0, tx.principal - remainder)
                    actual_principal_reduced = remainder
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
        elif new_status:
            tx.status = new_status

    db.session.add(PaymentHistory(
        transaction_id=tx.id, payment_date=thai_today, pay_amount=pay_amount,
        fine_amount=fine_amt, discount_amount=discount_amt, interest_paid=actual_interest_paid,
        principal_reduced=actual_principal_reduced, note=note_text, admin_name=session.get('admin'),
        receiving_account=receiving_account
    ))
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
    rows = "".join([f"<tr><td>{h.payment_date.strftime('%d/%m/%Y')}</td><td class='text-primary fw-bold'>{h.pay_amount:,.2f}</td><td>{get_funding_badge(h.receiving_account or 'ออมสิน')}</td><td>{h.fine_amount:,.2f}</td><td>{h.discount_amount:,.2f}</td><td>{h.interest_paid:,.2f}</td><td>{h.principal_reduced:,.2f}</td><td>{h.note or '-'}</td><td><span class='badge bg-secondary'>{h.admin_name or '-'}</span></td></tr>" for h in histories])
    content = f"""<div class="card p-4 shadow-sm border-warning"><h4 class="mb-3 fs-5 text-danger fw-bold">📜 ประวัติการชำระเงิน: {tx.customer_name}</h4><table class="table table-striped align-middle text-nowrap"><thead><tr><th>วันที่</th><th>ยอดจ่าย</th><th>ช่องทาง</th><th>ค่าปรับ</th><th>ส่วนลด</th><th>ดอกเบี้ย</th><th>เงินต้น</th><th>หมายเหตุ</th><th>ผู้บันทึก</th></tr></thead><tbody>{rows if rows else "<tr><td colspan='9' class='text-center text-muted'>ไม่มีประวัติ</td></tr>"}</tbody></table></div>"""
    html = BASE_LAYOUT.replace('{% block header %}ประวัติการชำระเงิน{% endblock %}', 'ประวัติการชำระเงิน').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="ประวัติการชำระเงิน", page="dashboard")

@app.route('/sales_members')
def sales_members():
    if 'admin' not in session: return redirect(url_for('login'))
    sales_data = defaultdict(list)
    for tx in Transaction.query.filter(Transaction.principal > 0).all():
        calculate_tx_values(tx)
        sales_data[tx.sales_name].append(tx)
    
    sales_content = ""
    for sales, txs in sales_data.items():
        table_rows = ""
        for t in txs:
            table_rows += f"<tr><td><a href='/customer_details/{t.customer_name}'>{t.customer_name}</a></td><td>{t.phone or '-'}</td><td>{get_funding_badge(t.funding_source)}</td><td>{get_funding_badge(t.receiving_account)}</td><td>{t.original_principal:,.2f}</td><td>{t.principal:,.2f}</td></tr>"
        sales_content += f"<div class='card mb-4 shadow-sm border-warning'><div class='card-header bg-danger text-white'><h5 class='mb-0 fs-6'>เซลล์: {sales}</h5></div><div class='card-body'><table class='table table-striped text-nowrap'><thead><tr><th>ชื่อ</th><th>เบอร์</th><th>บัญชีปล่อย</th><th>โอนเข้าล่าสุด</th><th>ลงทุน</th><th>ต้นคงค้าง</th></tr></thead><tbody>{table_rows}</tbody></table></div></div>"

    html = BASE_LAYOUT.replace('{% block header %}2. สมาชิกภายใต้เซลล์{% endblock %}', 'สมาชิกแยกตามเซลล์').replace('{% block content %}{% endblock %}', sales_content or '<p class="text-center text-muted">ยังไม่มีข้อมูล</p>')
    return render_template_string(html, title="สมาชิกภายใต้เซลล์", page="sales")

@app.route('/customer_summary')
def customer_summary():
    if 'admin' not in session: return redirect(url_for('login'))
    rows = "".join([f"<tr><td><a href='/customer_details/{t.customer_name}' class='text-dark fw-bold'>{t.customer_name}</a></td><td>{t.phone or '-'}</td><td>{t.sales_name}</td><td>{t.type}</td><td>{get_funding_badge(t.funding_source or 'ออมสิน')}</td><td>{get_funding_badge(t.receiving_account or 'ออมสิน')}</td><td>{t.original_principal:,.2f}</td><td>{t.principal:,.2f}</td></tr>" for t in Transaction.query.all() if calculate_tx_values(t) or True])
    html = BASE_LAYOUT.replace('{% block header %}3. สรุปลูกค้า{% endblock %}', 'สรุปลูกค้า').replace('{% block content %}{% endblock %}', f'<div class="card p-4 shadow-sm border-warning"><table class="table table-striped"><thead><tr><th>ชื่อ</th><th>เบอร์</th><th>เซลล์</th><th>ประเภท</th><th>บัญชีปล่อย</th><th>โอนเข้าล่าสุด</th><th>ลงทุน</th><th>ต้นคงค้าง</th></tr></thead><tbody>{rows}</tbody></table></div>')
    return render_template_string(html, title="สรุปลูกค้า", page="customer")

@app.route('/customer_emergency')
def customer_emergency():
    if 'admin' not in session: return redirect(url_for('login'))
    rows = "".join([f"<tr><td><a href='/customer_details/{t.customer_name}'>{t.customer_name}</a></td><td>{t.phone or '-'}</td><td>{get_funding_badge(t.funding_source)}</td><td>{get_funding_badge(t.receiving_account)}</td><td>{t.original_principal:,.2f}</td><td>{t.principal:,.2f}</td></tr>" for t in Transaction.query.filter_by(type='เงินฉุกเฉิน').all()])
    html = BASE_LAYOUT.replace('{% block header %}3.1 เงินฉุกเฉิน{% endblock %}', 'เงินฉุกเฉิน').replace('{% block content %}{% endblock %}', f'<div class="card p-4 shadow-sm border-warning"><table class="table table-striped"><thead><tr><th>ชื่อ</th><th>เบอร์</th><th>บัญชีปล่อย</th><th>โอนเข้าล่าสุด</th><th>ลงทุน</th><th>ต้นคงค้าง</th></tr></thead><tbody>{rows}</tbody></table></div>')
    return render_template_string(html, title="เงินฉุกเฉิน", page="emergency")

@app.route('/customer_gold')
def customer_gold():
    if 'admin' not in session: return redirect(url_for('login'))
    rows = "".join([f"<tr><td><a href='/customer_details/{t.customer_name}'>{t.customer_name}</a></td><td>{t.phone or '-'}</td><td>{get_funding_badge(t.funding_source)}</td><td>{get_funding_badge(t.receiving_account)}</td><td>{t.original_principal:,.2f}</td><td>{t.principal:,.2f}</td></tr>" for t in Transaction.query.filter_by(type='ผ่อนทอง').all()])
    html = BASE_LAYOUT.replace('{% block header %}3.2 ผ่อนทอง{% endblock %}', 'ผ่อนทอง').replace('{% block content %}{% endblock %}', f'<div class="card p-4 shadow-sm border-warning"><table class="table table-striped"><thead><tr><th>ชื่อ</th><th>เบอร์</th><th>บัญชีปล่อย</th><th>โอนเข้าล่าสุด</th><th>ลงทุน</th><th>ต้นคงค้าง</th></tr></thead><tbody>{rows}</tbody></table></div>')
    return render_template_string(html, title="ผ่อนทอง", page="gold")

@app.route('/customer_debt')
def customer_debt():
    if 'admin' not in session: return redirect(url_for('login'))
    rows = "".join([f"<tr><td><a href='/customer_details/{t.customer_name}'>{t.customer_name}</a></td><td>{t.phone or '-'}</td><td>{get_funding_badge(t.funding_source)}</td><td>{get_funding_badge(t.receiving_account)}</td><td>{t.original_principal:,.2f}</td><td>{t.principal:,.2f}</td></tr>" for t in Transaction.query.filter_by(type='ยอดค้างเก่า').all()])
    html = BASE_LAYOUT.replace('{% block header %}3.3 ยอดค้างเก่า{% endblock %}', 'ยอดค้างเก่า').replace('{% block content %}{% endblock %}', f'<div class="card p-4 shadow-sm border-warning"><table class="table table-striped"><thead><tr><th>ชื่อ</th><th>เบอร์</th><th>บัญชีปล่อย</th><th>โอนเข้าล่าสุด</th><th>ยอดตั้งต้น</th><th>ยอดคงเหลือ</th></tr></thead><tbody>{rows}</tbody></table></div>')
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
    login_html = """<!DOCTYPE html><html lang="th"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>เข้าสู่ระบบ</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"><style>body{font-family:'Prompt',sans-serif;background:#2c0b0e;color:#fff}.card{background:#fff;color:#333;border:2px solid #d4af37}</style></head><body class="d-flex align-items-center justify-content-center vh-100 p-3"><div class="card p-4 shadow-lg w-100" style="max-width:380px;"><h3 class="text-center mb-1 text-danger fw-bold">🔱 ทรัพย์ล้น</h3><p class="text-center text-muted small mb-4">ระบบบริหารจัดการการเงิน</p>{% if error %}<div class="alert alert-danger py-2 text-center">{{ error }}</div>{% endif %}<form method="POST"><div class="mb-3"><label class="form-label">ชื่อผู้ใช้งาน:</label><input type="text" name="username" class="form-control" required></div><div class="mb-3"><label class="form-label">รหัสผ่าน:</label><input type="password" name="password" class="form-control" required></div><button type="submit" class="btn btn-warning w-100 fw-bold">เข้าสู่ระบบ</button></form></div></body></html>"""
    return render_template_string(login_html, error=error)

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
