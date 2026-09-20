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
            <li><a href="/members" class="nav-link {% if page == 'members' %}active{% endif %}" onclick="toggleSidebar()">👥 1. สมาชิกทั้งหมด (เช็กบิลเดิน/ปิด)</a></li>
            <li><a href="/members_daily" class="nav-link sub-menu {% if page == 'members_daily' %}active{% endif %}" onclick="toggleSidebar()">🔸 1.1 จ่ายทุกวัน (ทวงทุกวัน)</a></li>
            <li><a href="/members_unscheduled" class="nav-link sub-menu {% if page == 'members_unscheduled' %}active{% endif %}" onclick="toggleSidebar()">🔸 1.2 ยังไม่มีกำหนดจ่าย</a></li>
            <li><a href="/members_scheduled_all" class="nav-link sub-menu {% if page == 'members_scheduled_all' %}active{% endif %}" onclick="toggleSidebar()">🔸 1.3 กำหนดจ่ายประจำเดือน</a></li>
            <li><a href="/sales_members" class="nav-link {% if page == 'sales' %}active{% endif %}" onclick="toggleSidebar()">📋 2. สมาชิกภายใต้เซลล์</a></li>
            <li><a href="/customer_summary" class="nav-link {% if page == 'customer' %}active{% endif %}" onclick="toggleSidebar()">📂 3. สรุปลูกค้า</a></li>
            <li><a href="/monthly_summary" class="nav-link sub-menu {% if page == 'monthly' %}active{% endif %}" onclick="toggleSidebar()">📅 4. สรุปยอดรายเดือน</a></li>
        </ul>
        <hr class="border-secondary">
        <div class="d-flex flex-column gap-2 mb-2">
            <a href="/export_data" class="btn btn-outline-warning btn-sm w-100">📥 สำรองข้อมูล (Backup)</a>
        </div>
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
        let statusElem = document.getElementById('newStatus' + id);
        if (selectElem.value === 'full') {
            if(amountContainer) amountContainer.style.display = 'none';
            if(adjustContainer) adjustContainer.style.display = 'none';
            if (statusElem) statusElem.value = 'คืนแล้ว';
        } else if (selectElem.value === 'adjust') {
            if(amountContainer) amountContainer.style.display = 'none';
            if(adjustContainer) adjustContainer.style.display = 'block';
        } else {
            if(amountContainer) amountContainer.style.display = 'block';
            if(adjustContainer) adjustContainer.style.display = 'none';
        }
    }
    function closeAllModals() {
        document.querySelectorAll('.modal').forEach(modal => {
            let bsModal = bootstrap.Modal.getInstance(modal);
            if (bsModal) bsModal.hide();
        });
        document.querySelectorAll('.modal-backdrop').forEach(el => el.remove());
        document.body.classList.remove('modal-open');
        document.body.style.overflow = '';
    }
    </script>
</body>
</html>
"""

# จัดการ Error 404 (หน้าไม่พบ) ไม่ให้ขึ้นหน้าขาว Not Found ธรรมดา
@app.errorhandler(404)
def page_not_found(e):
    if 'admin' not in session: return redirect(url_for('login'))
    error_content = """
    <div class="card p-5 text-center shadow-sm border-danger" style="max-width: 600px; margin: 50px auto;">
        <h1 class="text-danger fw-bold display-4">404</h1>
        <h4 class="text-dark fw-bold mb-3">ไม่พบหน้าที่คุณต้องการ</h4>
        <p class="text-muted mb-4">ลิงก์ที่คุณพยายามเข้าถึงอาจไม่ถูกต้องหรือถูกย้ายไปแล้ว</p>
        <a href="/" class="btn btn-warning fw-bold px-4 py-2">⬅️ กลับสู่หน้าหลัก (Dashboard)</a>
    </div>
    """
    html = BASE_LAYOUT.replace('{% block header %}ไม่พบหน้าเว็บ{% endblock %}', 'เกิดข้อผิดพลาด').replace('{% block content %}{% endblock %}', error_content)
    return render_template_string(html, title="ไม่พบหน้าเว็บ", page="error"), 404

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
    all_unique_customers = sorted(list(set(t.customer_name for t in all_txs_ever if t.customer_name)))
    customer_active_counts = defaultdict(int)
    for t in all_txs_ever:
        if t.principal > 0 and t.customer_name: customer_active_counts[t.customer_name] += 1

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

    krungsri_keywords = ["แอนนา บริสุทธิ์", "วันดี ประสานสงฆ์", "ชั้นไม่ใช่ นางเอก", "Anongnad Petchanoo", "กุลธิดา อานับ", "เชิฟ"]
    profit_items = []
    for tx in all_txs_ever:
        net_earned = max(0.0, (tx.original_principal - tx.principal)) if tx.type == 'ยอดค้างเก่า' else max(tx.paid_interest, sum(h.interest_paid for h in tx.histories) if tx.histories else 0.0)
        tx_fine_sum = sum(h.fine_amount for h in tx.histories) if tx.histories else 0.0
        tx_discount_sum = sum(h.discount_amount for h in tx.histories) if tx.histories else 0.0
        total_item_profit = net_earned + tx_fine_sum - tx_discount_sum
        if total_item_profit != 0:
            latest_date = max([tx.start_date] + [h.payment_date for h in tx.histories] + ([tx.last_payment_date] if tx.last_payment_date else []))
            profit_items.append({'customer_name': tx.customer_name, 'type': tx.type, 'total_item_profit': total_item_profit, 'latest_date': latest_date})

    for item in profit_items:
        if item['total_item_profit'] > 0:
            target_acc = 'กรุงศรีอยุธยา' if any(kw.lower() in item['customer_name'].lower() for kw in krungsri_keywords) else 'ออมสิน'
            bank_details_data[target_acc]['inflows'].append({'date': item['latest_date'].strftime('%d/%m/%Y'), 'customer': f"กำไรสะสม: {item['customer_name']}", 'amount': item['total_item_profit'], 'note': f"ประเภท: {item['type']}"})

    for e in BankExpenseLog.query.all():
        if e.account_name in bank_details_data: bank_details_data[e.account_name]['outflows'].append({'date': e.expense_date.strftime('%d/%m/%Y'), 'target': f"ถอนเงินออก: {e.note or 'ค่าใช้จ่าย'}", 'amount': e.amount, 'note': f"ผู้ทำ: {e.admin_name or '-'}"})

    bank_modals_html = ""
    for acc_key, acc_title, modal_id, theme_color in [('กรุงศรีอยุธยา', '🟡 กรุงศรีอยุธยา', 'modalKrungsri', 'warning'), ('ออมสิน', '🩷 ออมสิน', 'modalGSB', 'danger'), ('วอลเล็ท', '🟠 TrueMoney Wallet', 'modalWallet', 'info')]:
        inflows = "".join([f"<tr><td>{i['date']}</td><td><a href='/customer_details/{i['customer']}' class='fw-bold text-dark'>{i['customer']}</a></td><td class='text-success fw-bold'>+{i['amount']:,.2f}</td><td>{i['note']}</td></tr>" for i in bank_details_data[acc_key]['inflows']])
        outflows = "".join([f"<tr><td>{o['date']}</td><td>{o['target']}</td><td class='text-danger fw-bold'>-{o['amount']:,.2f}</td><td>{o['note']}</td></tr>" for o in bank_details_data[acc_key]['outflows']])
        bank_modals_html += f"""
        <div class="modal fade" id="{modal_id}" tabindex="-1"><div class="modal-dialog modal-lg modal-dialog-centered"><div class="modal-content border-{theme_color}"><div class="modal-header bg-{theme_color} text-white py-2"><h5 class="modal-title fw-bold fs-6">📊 ความเคลื่อนไหว: {acc_title}</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div><div class="modal-body" style="max-height: 60vh; overflow-y: auto;"><h6 class="text-success fw-bold">📥 เงินเข้า</h6><table class="table table-sm table-striped"><thead><tr><th>วันที่</th><th>รายการ</th><th>จำนวนเงิน</th><th>หมายเหตุ</th></tr></thead><tbody>{inflows or "<tr><td colspan='4' class='text-muted text-center'>ไม่มีรายการ</td></tr>"}</tbody></table><h6 class="text-danger fw-bold mt-3">📤 เงินออก</h6><table class="table table-sm table-striped"><thead><tr><th>วันที่</th><th>รายการ</th><th>จำนวนเงิน</th><th>หมายเหตุ</th></tr></thead><tbody>{outflows or "<tr><td colspan='4' class='text-muted text-center'>ไม่มีรายการ</td></tr>"}</tbody></table></div><div class="modal-footer py-2"><button class="btn btn-warning btn-sm" data-bs-dismiss="modal" onclick="openAddModal('{acc_key}')">➕ เพิ่มรายการ</button></div></div></div></div>
        """

    rows = ""
    for tx in transactions:
        badge_color = 'bg-success' if tx.status == 'ปกติ' else ('bg-info text-dark' if tx.status == 'ตัดยอดบางส่วน' else 'bg-danger')
        active_cnt = customer_active_counts.get(tx.customer_name, 1)
        count_badge = f' <a href="/customer_details/{tx.customer_name}" class="badge bg-danger text-decoration-none">🔥 {active_cnt} บิล</a>'
        rows += f"""
        <tr>
            <td><a href="/customer_details/{tx.customer_name}" class="text-dark fw-bold text-decoration-none">{tx.customer_name}</a>{count_badge}</td>
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

    today_collected_cash = sum((h.pay_amount if h.pay_amount > 0 else (h.interest_paid + h.principal_reduced)) for h in PaymentHistory.query.filter_by(payment_date=thai_today).all())

    content = f"""
    <div class="card p-3 mb-4 shadow-sm border-warning bg-white">
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <h5 class="text-danger fw-bold mb-0">🏦 สถานะกระเป๋าเงินจริง</h5>
        </div>
        <div class="row g-3">
            <div class="col-md-4"><div class="p-3 rounded border border-warning bg-warning bg-opacity-10" style="cursor:pointer;" data-bs-toggle="modal" data-bs-target="#modalKrungsri"><h6 class="text-dark fw-bold">🟡 กรุงศรีอยุธยา</h6><h3 class="fw-bold">{account_balances['กรุงศรีอยุธยา']:,.2f} ฿</h3></div></div>
            <div class="col-md-4"><div class="p-3 rounded border border-danger bg-danger bg-opacity-10" style="cursor:pointer;" data-bs-toggle="modal" data-bs-target="#modalGSB"><h6 class="text-danger fw-bold">🩷 ออมสิน</h6><h3 class="fw-bold">{account_balances['ออมสิน']:,.2f} ฿</h3></div></div>
            <div class="col-md-4"><div class="p-3 rounded border border-info bg-info bg-opacity-10" style="cursor:pointer;" data-bs-toggle="modal" data-bs-target="#modalWallet"><h6 class="text-dark fw-bold">🟠 TrueMoney Wallet</h6><h3 class="fw-bold">{account_balances['วอลเล็ท']:,.2f} ฿</h3></div></div>
        </div>
    </div>
    {bank_modals_html}
    <div class="row mb-4">
        <div class="col-md-6 mb-2"><div class="card p-3 text-white bg-success"><h6>💵 ยอดเก็บสดวันนี้</h6><h3>{today_collected_cash:,.2f} บาท</h3></div></div>
        <div class="col-md-6 mb-2"><div class="card p-3 text-white bg-primary"><h6>📋 บิลที่ต้องจัดการวันนี้</h6><h3>{len(transactions)} บิล</h3></div></div>
    </div>
    <div class="card p-4 shadow-sm border-warning">
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <h4 class="mb-0 fs-5 text-danger fw-bold">🔔 รายการที่ต้องทวงวันนี้</h4>
            <form method="GET" class="d-flex gap-2"><input type="text" name="search" class="form-control form-control-sm" placeholder="ค้นหาชื่อลูกค้า..." value="{search_query}"><button class="btn btn-sm btn-outline-danger">ค้นหา</button></form>
        </div>
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

@app.route('/members')
def members():
    if 'admin' not in session: return redirect(url_for('login'))
    search_query = request.args.get('search', '').strip()
    all_txs = Transaction.query.all()
    customer_dict = defaultdict(lambda: {'active_count': 0, 'closed_count': 0, 'phone': '-', 'sales': '-'})
    
    for t in all_txs:
        c_name = t.customer_name
        customer_dict[c_name]['phone'] = t.phone or customer_dict[c_name]['phone']
        customer_dict[c_name]['sales'] = t.sales_name or customer_dict[c_name]['sales']
        if t.principal > 0: customer_dict[c_name]['active_count'] += 1
        else: customer_dict[c_name]['closed_count'] += 1

    rows = ""
    for c_name, data in sorted(customer_dict.items()):
        if search_query and search_query.lower() not in c_name.lower(): continue
        rows += f"""
        <tr>
            <td><a href="/customer_details/{c_name}" class="text-dark fw-bold text-decoration-none fs-6">👤 {c_name}</a></td>
            <td>{data['phone']}</td>
            <td><span class="badge bg-danger">{data['sales']}</span></td>
            <td><span class="badge bg-success">เดินอยู่ {data['active_count']} บิล</span></td>
            <td><span class="badge bg-secondary">ปิดแล้ว {data['closed_count']} บิล</span></td>
            <td><a href="/customer_details/{c_name}" class="btn btn-sm btn-warning fw-bold">🔍 ตรวจสอบ / จัดการบิล</a></td>
        </tr>
        """

    content = f"""
    <div class="card p-4 shadow-sm border-warning">
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <h4 class="mb-0 fs-5 text-danger fw-bold">👥 สมาชิกทั้งหมดในระบบ (คลิกดูบิลทั้งหมดของลูกค้า)</h4>
            <form method="GET" class="d-flex gap-2"><input type="text" name="search" class="form-control form-control-sm" placeholder="ค้นหาชื่อลูกค้า..." value="{search_query}"><button class="btn btn-sm btn-outline-danger">ค้นหา</button></form>
        </div>
        <div class="table-responsive">
            <table class="table table-striped text-nowrap align-middle">
                <thead class="table-dark"><tr><th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>เซลล์</th><th>บิลที่กำลังเดิน</th><th>บิลที่ปิดแล้ว</th><th>จัดการ</th></tr></thead>
                <tbody>{rows if rows else "<tr><td colspan='6' class='text-center text-muted'>ไม่พบรายชื่อสมาชิก</td></tr>"}</tbody>
            </table>
        </div>
    </div>
    """
    html = BASE_LAYOUT.replace('{% block header %}1. สมาชิกทั้งหมด{% endblock %}', 'สมาชิกทั้งหมด').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="สมาชิกทั้งหมด", page="members")

@app.route('/customer_details/<path:cust_name>')
def customer_details(cust_name):
    if 'admin' not in session: return redirect(url_for('login'))
    clean_name = cust_name.replace("กำไรสะสม: ", "").strip()
    txs = Transaction.query.filter(Transaction.customer_name.ilike(f"%{clean_name}%")).order_by(Transaction.start_date.desc()).all()
    for tx in txs: calculate_tx_values(tx)

    active_txs = [t for t in txs if t.principal > 0]
    closed_txs = [t for t in txs if t.principal <= 0]

    def build_table(tx_list, is_closed=False):
        res = ""
        for tx in tx_list:
            badge_color = 'bg-danger' if is_closed else ('bg-success' if tx.status == 'ปกติ' else 'bg-info text-dark')
            res += f"""
            <tr>
                <td><span class="badge bg-secondary">{tx.type}</span></td>
                <td>{get_funding_badge(tx.funding_source)}</td>
                <td>{get_funding_badge(tx.receiving_account)}</td>
                <td>{tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'}</td>
                <td>{tx.original_principal:,.2f}</td>
                <td>{tx.principal:,.2f}</td>
                <td><a href="/history/{tx.id}" target="_blank" class="text-primary fw-bold text-decoration-none">{tx.total_paid:,.2f}</a></td>
                <td><span class="badge {badge_color}">{'ปิดบิลแล้ว' if is_closed else tx.status}</span></td>
                <td class="text-center">
                    <div class="d-flex justify-content-center gap-1">
                        <button class="btn btn-sm btn-success-light fw-bold" data-bs-toggle="modal" data-bs-target="#payModal{tx.id}">จัดการ</button>
                        <a href="/delete_tx/{tx.id}" class="btn btn-sm btn-danger" onclick="return confirm('ยืนยันลบบิลนี้?')">ลบ</a>
                    </div>
                </td>
            </tr>
            """
        return res

    modals_html = ""
    for tx in txs:
        modals_html += f"""
        <div class="modal fade" id="payModal{tx.id}" tabindex="-1"><div class="modal-dialog modal-dialog-centered"><div class="modal-content border-warning"><form action="/update_payment/{tx.id}" method="POST"><div class="modal-header bg-danger text-white py-2"><h5 class="modal-title fs-6">จัดการยอด: {tx.customer_name}</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div><div class="modal-body py-2"><div class="p-2 mb-2 bg-light rounded border d-flex justify-content-between"><div><small class="text-muted">ต้นคงเหลือ</small><b>{tx.principal:,.2f} ฿</b></div><div class="text-end"><small class="text-muted">ดอกสะสม</small><b class="text-danger">{tx.accumulated_interest:,.2f} ฿</b></div></div><div class="mb-2"><label class="form-label text-success fw-bold small">รับเข้าบัญชี:</label><select name="receiving_account" class="form-select form-select-sm"><option value="ออมสิน">🩷 ออมสิน</option><option value="กรุงศรีอยุธยา">🟢 กรุงศรีอยุธยา</option><option value="วอลเล็ท">🟠 TrueMoney Wallet</option></select></div><div class="mb-2"><label class="form-label fw-bold text-primary small">ประเภทการชำระ</label><select name="payment_type" class="form-select form-select-sm" id="payType{tx.id}" onchange="togglePayInput({tx.id})" required><option value="" disabled selected>-- เลือก --</option><option value="partial">จ่ายบางส่วน</option><option value="full">คืนครบ (ปิดบิล)</option><option value="adjust">ปรับปรุงยอดต้น</option></select></div><div class="mb-2" id="amountDiv{tx.id}"><label class="form-label fw-bold small">จำนวนเงินที่รับ (บาท)</label><input type="number" step="any" name="pay_amount" class="form-control form-control-sm" placeholder="0.00"></div><div class="mb-2" id="adjustContainer{tx.id}" style="display:none;"><label class="form-label fw-bold small">จำนวนเงินปรับปรุง (+/-)</label><input type="number" step="any" name="adjust_amount" class="form-control form-control-sm" placeholder="เช่น 500 หรือ -200"></div><div class="row g-2 mb-2"><div class="col-6"><label class="form-label text-danger small">ส่วนลด</label><input type="number" step="any" name="discount_amount" class="form-control form-control-sm" value="0"></div><div class="col-6"><label class="form-label text-warning text-dark small">ค่าปรับ</label><input type="number" step="any" name="fine_amount" class="form-control form-control-sm" value="0"></div></div><div class="mb-2"><label class="form-label small">หมายเหตุ</label><input type="text" name="note" class="form-control form-control-sm" placeholder="หมายเหตุ..."></div></div><div class="modal-footer py-2"><button class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ยกเลิก</button><button type="submit" class="btn btn-success btn-sm fw-bold px-3">บันทึก</button></div></form></div></div></div>
        """

    content = f"""
    <div class="card p-4 shadow-sm border-warning mb-3">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h4 class="mb-0 fs-5 text-danger fw-bold">👤 รายละเอียดบัญชีของ: {clean_name}</h4>
            <a href="/members" class="btn btn-sm btn-secondary fw-bold">⬅️ กลับหน้ารายชื่อสมาชิก</a>
        </div>
        <h6 class="text-success fw-bold border-bottom pb-2">🟢 บิลที่กำลังเดินอยู่ ({len(active_txs)} บิล)</h6>
        <div class="table-responsive mb-4">
            <table class="table table-striped align-middle text-nowrap">
                <thead class="table-dark"><tr><th>ประเภท</th><th>บัญชีปล่อย</th><th>โอนเข้า</th><th>วันที่กู้</th><th>ลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th><th>สถานะ</th><th class="text-center">จัดการ</th></tr></thead>
                <tbody>{build_table(active_txs, False) if active_txs else "<tr><td colspan='9' class='text-center text-muted'>ไม่มีบิลที่กำลังเดินอยู่</td></tr>"}</tbody>
            </table>
        </div>
        <div class="border rounded p-3 bg-light">
            <button class="btn btn-outline-secondary btn-sm w-100 fw-bold d-flex justify-content-between align-items-center" type="button" data-bs-toggle="collapse" data-bs-target="#closedBillsCollapse">
                <span>📁 ลิ้นชักเก็บประวัติบิลที่ปิดไปแล้ว ({len(closed_txs)} บิล)</span>
                <span>▼ คลิกเพื่อเปิดดู</span>
            </button>
            <div class="collapse mt-3" id="closedBillsCollapse">
                <div class="table-responsive bg-white p-2 rounded">
                    <table class="table table-sm table-striped align-middle text-nowrap mb-0">
                        <thead class="table-secondary"><tr><th>ประเภท</th><th>บัญชีปล่อย</th><th>โอนเข้า</th><th>วันที่กู้</th><th>ลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th><th>สถานะ</th><th class="text-center">จัดการ</th></tr></thead>
                        <tbody>{build_table(closed_txs, True) if closed_txs else "<tr><td colspan='9' class='text-center text-muted'>ไม่มีบิลที่ปิดไปแล้ว</td></tr>"}</tbody>
                    </table>
                </div>
            </div>
        </div>
    </div>
    {modals_html}
    """
    html = BASE_LAYOUT.replace('{% block header %}รายละเอียดลูกค้า{% endblock %}', f'รายละเอียดลูกค้า: {clean_name}').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title=f"ลูกค้า: {clean_name}", page="members")

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
    note_text = request.form.get('note', '').strip()
    
    days = max(1, (thai_today - tx.start_date).days + 1)
    current_effective_daily = tx.initial_daily_interest * (tx.principal / tx.original_principal) if tx.original_principal > 0 else tx.daily_interest
    total_acc_interest = max(0.0, (current_effective_daily * days) - tx.paid_interest)

    tx.last_payment_date = thai_today
    actual_interest_paid, actual_principal_reduced = 0.0, 0.0

    if payment_type == 'adjust':
        adjust_amount = float(request.form.get('adjust_amount', 0))
        tx.principal = max(0.0, tx.principal + adjust_amount)
        actual_principal_reduced = -adjust_amount
        if pay_amount <= 0: pay_amount = abs(adjust_amount)
    elif payment_type == 'full':
        net_interest_earned = max(0.0, total_acc_interest - discount_amt)
        tx.paid_interest += net_interest_earned
        actual_interest_paid = net_interest_earned
        actual_principal_reduced = tx.principal
        if pay_amount <= 0: pay_amount = net_interest_earned + tx.principal
        tx.principal = 0.0
        tx.status = 'คืนแล้ว'
        tx.closed_date = thai_today
    else:
        net_acc_interest = max(0.0, total_acc_interest - discount_amt)
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

        if tx.principal <= 0:
            tx.status = 'คืนแล้ว'
            tx.principal = 0.0
            tx.closed_date = thai_today

    db.session.add(PaymentHistory(
        transaction_id=tx.id, payment_date=thai_today, pay_amount=pay_amount,
        fine_amount=fine_amt, discount_amount=discount_amt, interest_paid=actual_interest_paid,
        principal_reduced=actual_principal_reduced, note=note_text, admin_name=session.get('admin'),
        receiving_account=receiving_account
    ))
    db.session.commit()
    db.session.remove()
    return redirect(url_for('customer_details', cust_name=tx.customer_name))

@app.route('/delete_tx/<int:tx_id>')
def delete_tx(tx_id):
    if 'admin' not in session: return redirect(url_for('login'))
    tx = Transaction.query.get_or_404(tx_id)
    db.session.delete(tx)
    db.session.commit()
    db.session.remove()
    return redirect(request.referrer or url_for('index'))

@app.route('/history/<int:tx_id>')
def payment_history(tx_id):
    if 'admin' not in session: return redirect(url_for('login'))
    tx = Transaction.query.get_or_404(tx_id)
    histories = PaymentHistory.query.filter_by(transaction_id=tx.id).order_by(PaymentHistory.payment_date.desc()).all()
    rows = "".join([f"<tr><td>{h.payment_date.strftime('%d/%m/%Y')}</td><td class='text-primary fw-bold'>{h.pay_amount:,.2f}</td><td>{get_funding_badge(h.receiving_account)}</td><td>{h.fine_amount:,.2f}</td><td>{h.discount_amount:,.2f}</td><td>{h.interest_paid:,.2f}</td><td>{h.principal_reduced:,.2f}</td><td>{h.note or '-'}</td><td><span class='badge bg-secondary'>{h.admin_name or '-'}</span></td></tr>" for h in histories])
    content = f"""<div class="card p-4 shadow-sm border-warning"><h4 class="mb-3 fs-5 text-danger fw-bold">📜 ประวัติการชำระเงิน: {tx.customer_name}</h4><a href="/customer_details/{tx.customer_name}" class="btn btn-sm btn-secondary mb-3">⬅️ กลับหน้าประวัติลูกค้า</a><table class="table table-striped align-middle text-nowrap"><thead><tr><th>วันที่</th><th>ยอดจ่าย</th><th>ช่องทาง</th><th>ค่าปรับ</th><th>ส่วนลด</th><th>ดอกเบี้ย</th><th>เงินต้น</th><th>หมายเหตุ</th><th>ผู้บันทึก</th></tr></thead><tbody>{rows if rows else "<tr><td colspan='9' class='text-center text-muted'>ไม่มีประวัติ</td></tr>"}</tbody></table></div>"""
    html = BASE_LAYOUT.replace('{% block header %}ประวัติการชำระเงิน{% endblock %}', 'ประวัติการชำระเงิน').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="ประวัติการชำระเงิน", page="dashboard")

@app.route('/export_data')
def export_data():
    if 'admin' not in session: return redirect(url_for('login'))
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Type', 'CustomerName', 'Phone', 'SalesName', 'StartDate', 'OriginalPrincipal', 'Principal', 'DailyInterest', 'Status'])
    for t in Transaction.query.all():
        cw.writerow([t.id, t.type, t.customer_name, t.phone, t.sales_name, t.start_date, t.original_principal, t.principal, t.daily_interest, t.status])
    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name=f"sublon_backup_{get_thai_today().strftime('%Y%m%d_%H%M%S')}.csv")

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
