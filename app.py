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
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {'pool_recycle': 300, 'pool_pre_ping': True}

db = SQLAlchemy(app)
TH_TIMEZONE = timezone(timedelta(hours=7))

def get_thai_today():
    return datetime.now(TH_TIMEZONE).date()

VALID_USERS = {'nueng': '909090', 'nice': '022540'}

def get_funding_badge(source):
    if source == 'ออมสิน':
        return '<span class="badge" style="background-color: #e83e8c; color: #fff;">ออมสิน</span>'
    elif source == 'กรุงศรีอยุธยา':
        return '<span class="badge text-dark" style="background-color: #ffc107;">กรุงศรีอยุธยา</span>'
    elif source == 'วอลเล็ท':
        return '<span class="badge" style="background-color: #fd7e14; color: #fff;">วอลเล็ท</span>'
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

def calculate_tx_values(tx):
    thai_today = get_thai_today()
    end_date = tx.closed_date if tx.closed_date else thai_today
    days = max(1, (end_date - tx.start_date).days + 1)
    tx.days_passed_val = days
    
    if tx.original_principal > 0 and tx.initial_daily_interest > 0:
        tx.daily_interest = tx.initial_daily_interest * (tx.principal / tx.original_principal)
    
    acc = (tx.daily_interest * days) - tx.paid_interest
    tx.accumulated_interest = acc if acc > 0 else 0.0
    
    total_history_pay = sum((h.pay_amount if h.pay_amount > 0 else (h.interest_paid + h.principal_reduced)) for h in tx.histories) if tx.histories else 0.0
    if tx.type == 'ยอดค้างเก่า':
        tx.total_paid = max(total_history_pay, max(0.0, tx.original_principal - tx.principal))
    else:
        tx.total_paid = total_history_pay if total_history_pay > 0 else tx.paid_interest

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
        .btn-success-light { background-color: #28a745; border-color: #28a745; color: #fff; font-weight: 600; }
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
            <li><a href="/members" class="nav-link {% if page == 'members' %}active{% endif %}" onclick="toggleSidebar()">👥 1. สมาชิกทั้งหมด</a></li>
            <li><a href="/transactions" class="nav-link {% if page == 'transactions' %}active{% endif %}" onclick="toggleSidebar()">📋 รายการทั้งหมด</a></li>
            <li><a href="/export_data" class="nav-link" onclick="toggleSidebar()">📥 สำรองข้อมูล (Backup)</a></li>
        </ul>
        <hr class="border-secondary">
        <div class="d-flex flex-column gap-2">
            <a href="/logout" class="btn btn-outline-danger w-100 d-none d-lg-block">ออกจากระบบ</a>
        </div>
    </div>
    <div class="main-content">
        <h2 class="mb-4 text-danger fw-bold fs-4">{% block header %}{% endblock %}</h2>
        {% block content %}{% endblock %}
    </div>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
    function toggleSidebar() {
        document.getElementById('sidebarMenu').classList.toggle('show');
        document.getElementById('sidebarBackdrop').classList.toggle('show');
    }
    function openAddModal(accountName) {
        let selectFunding = document.getElementById('addFundingSource');
        if (selectFunding) selectFunding.value = accountName;
        new bootstrap.Modal(document.getElementById('addTransactionModal')).show();
    }
    function togglePayInput(id) {
        let selectElem = document.getElementById('payType' + id);
        let amountContainer = document.getElementById('amountDiv' + id);
        let adjustContainer = document.getElementById('adjustContainer' + id);
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
    </script>
</body>
</html>
"""

@app.route('/', methods=['GET'])
def index():
    if 'admin' not in session: return redirect(url_for('login'))
    search_query = request.args.get('search', '').strip()
    thai_today = get_thai_today()
    today_day = thai_today.day

    query = Transaction.query.filter(Transaction.principal > 0)
    if search_query:
        query = query.filter((Transaction.customer_name.ilike(f"%{search_query}%")) | (Transaction.phone.ilike(f"%{search_query}%")))
    
    if not search_query:
        current_match_codes = []
        if 4 <= today_day <= 6: current_match_codes.append("6")
        if 9 <= today_day <= 12: current_match_codes.append("12")
        if 14 <= today_day <= 16: current_match_codes.append("16")
        if 20 <= today_day <= 23: current_match_codes.append("23")
        if 24 <= today_day <= 26: current_match_codes.append("26")
        if today_day >= 29 or today_day <= 2: current_match_codes.append("2")

        all_active_txs = Transaction.query.filter(Transaction.principal > 0).all()
        scheduled_today = [t for t in all_active_txs if t.schedule_type == 'กำหนดจ่ายประจำเดือน' and t.due_day_of_month and any(c in current_match_codes for c in t.due_day_of_month.split(','))]
        other_txs = Transaction.query.filter(Transaction.principal > 0, db.or_(Transaction.schedule_type == 'จ่ายทุกวัน', Transaction.start_date == thai_today, Transaction.last_payment_date == thai_today)).all()

        seen_ids = set()
        transactions = []
        for t in scheduled_today + other_txs:
            if t.id not in seen_ids:
                seen_ids.add(t.id)
                transactions.append(t)
    else:
        transactions = query.order_by(Transaction.customer_name.asc()).all()

    for tx in transactions: calculate_tx_values(tx)
    all_txs_ever = Transaction.query.all()
    for tx in all_txs_ever: calculate_tx_values(tx)

    account_balances = {'กรุงศรีอยุธยา': 0.0, 'ออมสิน': 0.0, 'วอลเล็ท': 0.0}
    adjustments = BankAdjustment.query.all()
    adj_dict = {adj.account_name: adj.adjustment_amount for adj in adjustments}
    for acc_name in account_balances.keys(): account_balances[acc_name] = adj_dict.get(acc_name, 0.0)

    bank_details_data = {acc: {'inflows': [], 'outflows': []} for acc in account_balances.keys()}
    for h in PaymentHistory.query.all():
        acc = h.receiving_account or 'ออมสิน'
        if acc in bank_details_data:
            cust_name = h.transaction.customer_name if h.transaction else "ไม่ระบุชื่อ"
            amt = h.pay_amount if h.pay_amount > 0 else (h.interest_paid + h.principal_reduced + h.fine_amount - h.discount_amount)
            if amt > 0: bank_details_data[acc]['inflows'].append({'date': h.payment_date.strftime('%d/%m/%Y'), 'customer': cust_name, 'amount': amt, 'note': h.note or 'รับชำระเงิน'})

    for tx in all_txs_ever:
        if tx.type != 'ยอดค้างเก่า' and tx.principal > 0:
            acc = tx.funding_source or 'ออมสิน'
            if acc in bank_details_data: bank_details_data[acc]['outflows'].append({'date': tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-', 'target': f"ปล่อยกู้ใหม่: {tx.customer_name}", 'amount': tx.original_principal, 'note': f"ทุนกู้ {tx.type}"})

    for e in BankExpenseLog.query.all():
        if e.account_name in bank_details_data: bank_details_data[e.account_name]['outflows'].append({'date': e.expense_date.strftime('%d/%m/%Y'), 'target': f"ถอนเงินออก: {e.note or 'ค่าใช้จ่าย'}", 'amount': e.amount, 'note': f"ผู้ทำ: {e.admin_name or '-'}"})

    rows = ""
    for tx in transactions:
        badge_color = 'bg-success' if tx.status == 'ปกติ' else ('bg-info text-dark' if tx.status == 'ตัดยอดบางส่วน' else 'bg-danger')
        rows += f"""
        <tr>
            <td><a href="/customer_details/{tx.customer_name}" class="text-dark fw-bold text-decoration-none">{tx.customer_name}</a></td>
            <td>{tx.phone or '-'}</td>
            <td><span class="badge bg-secondary">{tx.type}</span></td>
            <td>{get_funding_badge(tx.funding_source)}</td>
            <td>{get_funding_badge(tx.receiving_account)}</td>
            <td>{tx.start_date.strftime('%d/%m/%Y')}</td>
            <td>{tx.original_principal:,.2f}</td>
            <td>{tx.principal:,.2f}</td>
            <td><a href="/history/{tx.id}" target="_blank" class="text-primary fw-bold">{tx.total_paid:,.2f}</a></td>
            <td>{tx.daily_interest:,.2f}</td>
            <td class="text-danger fw-bold">{tx.accumulated_interest:,.2f}</td>
            <td><span class="badge {badge_color}">{tx.status}</span></td>
            <td><button class="btn btn-sm btn-success-light w-100" data-bs-toggle="modal" data-bs-target="#payModal{tx.id}">จัดการ</button></td>
        </tr>
        """

    content = f"""
    <div class="card p-3 mb-4 shadow-sm border-warning bg-white">
        <h5 class="text-danger fw-bold mb-3">🏦 สถานะกระเป๋าเงินจริง</h5>
        <div class="row g-3">
            <div class="col-md-4"><div class="p-3 rounded border border-warning bg-warning bg-opacity-10"><h6 class="text-dark fw-bold">🟡 กรุงศรีอยุธยา</h6><h3 class="fw-bold">{account_balances['กรุงศรีอยุธยา']:,.2f} ฿</h3></div></div>
            <div class="col-md-4"><div class="p-3 rounded border border-danger bg-danger bg-opacity-10"><h6 class="text-danger fw-bold">🩷 ออมสิน</h6><h3 class="fw-bold">{account_balances['ออมสิน']:,.2f} ฿</h3></div></div>
            <div class="col-md-4"><div class="p-3 rounded border border-info bg-info bg-opacity-10"><h6 class="text-dark fw-bold">🟠 TrueMoney Wallet</h6><h3 class="fw-bold">{account_balances['วอลเล็ท']:,.2f} ฿</h3></div></div>
        </div>
    </div>
    <div class="card p-4 shadow-sm border-warning">
        <h4 class="mb-3 fs-5 text-danger fw-bold">🔔 รายการที่ต้องทวงวันนี้</h4>
        <div class="table-responsive">
            <table class="table table-striped align-middle text-nowrap">
                <thead class="table-dark"><tr><th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>ประเภท</th><th>บัญชีปล่อย</th><th>โอนเข้า</th><th>วันที่กู้</th><th>ลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th><th>ดอก/วัน</th><th>ดอกสะสม</th><th>สถานะ</th><th>จัดการ</th></tr></thead>
                <tbody>{rows if rows else "<tr><td colspan='13' class='text-center text-muted'>ไม่มีรายการทวงในวันนี้</td></tr>"}</tbody>
            </table>
        </div>
    </div>
    """
    html = BASE_LAYOUT.replace('{% block header %}Dashboard{% endblock %}', '🔱 Dashboard บริหารจัดการระบบ')
    return render_template_string(html.replace('{% block content %}{% endblock %}', content), title="Dashboard", page="dashboard")

@app.route('/transactions')
def transactions_list():
    if 'admin' not in session: return redirect(url_for('login'))
    txs = Transaction.query.order_by(Transaction.start_date.desc()).all()
    for tx in txs: calculate_tx_values(tx)
    rows = "".join([f"<tr><td>{tx.customer_name}</td><td><span class='badge bg-secondary'>{tx.type}</span></td><td>{get_funding_badge(tx.funding_source)}</td><td>{tx.start_date.strftime('%d/%m/%Y')}</td><td>{tx.original_principal:,.2f}</td><td>{tx.principal:,.2f}</td><td><span class='badge bg-success'>{tx.status}</span></td></tr>" for tx in txs])
    content = f"""<div class="card p-4 shadow-sm border-warning"><h4 class="mb-3 fs-5 text-danger fw-bold">📋 รายการทั้งหมด</h4><table class="table table-striped align-middle text-nowrap"><thead class="table-dark"><tr><th>ชื่อลูกค้า</th><th>ประเภท</th><th>บัญชีปล่อย</th><th>วันที่กู้</th><th>ลงทุน</th><th>ต้นคงค้าง</th><th>สถานะ</th></tr></thead><tbody>{rows}</tbody></table></div>"""
    html = BASE_LAYOUT.replace('{% block header %}รายการทั้งหมด{% endblock %}', 'รายการทั้งหมด').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="รายการทั้งหมด", page="transactions")

@app.route('/members')
def members():
    if 'admin' not in session: return redirect(url_for('login'))
    txs = Transaction.query.all()
    customers = sorted(list(set(t.customer_name for t in txs if t.customer_name)))
    rows = "".join([f"<tr><td><a href='/customer_details/{c}' class='text-dark fw-bold text-decoration-none'>👤 {c}</a></td><td><a href='/customer_details/{c}' class='btn btn-sm btn-warning fw-bold'>🔍 ดูประวัติ</a></td></tr>" for c in customers])
    content = f"""<div class="card p-4 shadow-sm border-warning"><h4 class="mb-3 fs-5 text-danger fw-bold">👥 สมาชิกทั้งหมด</h4><table class="table table-striped align-middle"><thead><tr><th>ชื่อลูกค้า</th><th>จัดการ</th></tr></thead><tbody>{rows}</tbody></table></div>"""
    html = BASE_LAYOUT.replace('{% block header %}สมาชิกทั้งหมด{% endblock %}', 'สมาชิกทั้งหมด').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="สมาชิก", page="members")

@app.route('/customer_details/<path:cust_name>')
def customer_details(cust_name):
    if 'admin' not in session: return redirect(url_for('login'))
    txs = Transaction.query.filter(Transaction.customer_name.ilike(f"%{cust_name}%")).all()
    for tx in txs: calculate_tx_values(tx)
    rows = "".join([f"<tr><td>{tx.type}</td><td>{get_funding_badge(tx.funding_source)}</td><td>{tx.original_principal:,.2f}</td><td>{tx.principal:,.2f}</td><td><a href='/history/{tx.id}' target='_blank' class='text-primary fw-bold'>{tx.total_paid:,.2f}</a></td></tr>" for tx in txs])
    content = f"""<div class="card p-4 shadow-sm border-warning"><h4 class="mb-3 fs-5 text-danger fw-bold">👤 ลูกค้า: {cust_name}</h4><a href="/members" class="btn btn-sm btn-secondary mb-3">⬅️ กลับ</a><table class="table table-striped align-middle"><thead><tr><th>ประเภท</th><th>บัญชี</th><th>ลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th></tr></thead><tbody>{rows}</tbody></table></div>"""
    html = BASE_LAYOUT.replace('{% block header %}รายละเอียดลูกค้า{% endblock %}', f'ลูกค้า: {cust_name}').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title=cust_name, page="members")

@app.route('/history/<int:tx_id>')
def payment_history(tx_id):
    if 'admin' not in session: return redirect(url_for('login'))
    tx = Transaction.query.get_or_404(tx_id)
    histories = PaymentHistory.query.filter_by(transaction_id=tx.id).all()
    rows = "".join([f"<tr><td>{h.payment_date.strftime('%d/%m/%Y')}</td><td>{h.pay_amount:,.2f}</td><td>{get_funding_badge(h.receiving_account)}</td></tr>" for h in histories])
    content = f"""<div class="card p-4 shadow-sm border-warning"><h4 class="mb-3 fs-5 text-danger fw-bold">📜 ประวัติ: {tx.customer_name}</h4><table class="table table-striped"><thead><tr><th>วันที่</th><th>ยอดจ่าย</th><th>ช่องทาง</th></tr></thead><tbody>{rows}</tbody></table></div>"""
    html = BASE_LAYOUT.replace('{% block header %}ประวัติ{% endblock %}', 'ประวัติการชำระ').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="ประวัติ", page="dashboard")

@app.route('/export_data')
def export_data():
    if 'admin' not in session: return redirect(url_for('login'))
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Type', 'CustomerName', 'Principal', 'Status'])
    for t in Transaction.query.all():
        cw.writerow([t.id, t.type, t.customer_name, t.principal, t.status])
    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name="backup.csv")

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        if request.form.get('username') in VALID_USERS and VALID_USERS[request.form.get('username')] == request.form.get('password'):
            session['admin'] = request.form.get('username')
            return redirect(url_for('index'))
        else: error = 'รหัสผ่านไม่ถูกต้อง!'
    return render_template_string("""<!DOCTYPE html><html lang="th"><head><meta charset="UTF-8"><title>เข้าสู่ระบบ</title><link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet"></head><body class="d-flex align-items-center justify-content-center vh-100 bg-dark"><div class="card p-4 shadow-lg w-100" style="max-width:380px;"><h3 class="text-center text-danger fw-bold">🔱 ทรัพย์ล้น</h3>{% if error %}<div class="alert alert-danger py-1 text-center">{{ error }}</div>{% endif %}<form method="POST"><div class="mb-3"><label>ผู้ใช้งาน</label><input type="text" name="username" class="form-control" required></div><div class="mb-3"><label>รหัสผ่าน</label><input type="password" name="password" class="form-control" required></div><button class="btn btn-warning w-100 fw-bold">เข้าสู่ระบบ</button></form></div></body></html>""", error=error)

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
