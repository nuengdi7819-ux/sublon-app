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
        </ul>
        <hr class="border-secondary">
        <div class="d-flex gap-2 mb-2">
            <a href="/export_data" class="btn btn-outline-warning btn-sm flex-fill text-center" title="สำรองข้อมูล (Backup)">📥 Backup</a>
            <button class="btn btn-outline-info btn-sm flex-fill text-center" data-bs-toggle="modal" data-bs-target="#importModal" title="นำเข้าข้อมูล (Restore)">📤 Restore</button>
        </div>
        <div class="d-flex flex-column gap-2">
            <a href="/logout" class="btn btn-outline-danger w-100 d-none d-lg-block">ออกจากระบบ</a>
        </div>
    </div>

    <!-- Modal นำเข้าข้อมูล -->
    <div class="modal fade" id="importModal" tabindex="-1"><div class="modal-dialog"><div class="modal-content"><form action="/import_data" method="POST" enctype="multipart/form-data"><div class="modal-header bg-info text-dark"><h5 class="modal-title fw-bold">📤 นำเข้าข้อมูลสำรอง (Restore)</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><input type="file" name="file" class="form-control" accept=".csv" required></div><div class="modal-footer"><button type="submit" class="btn btn-info fw-bold">อัปโหลดและกู้คืน</button></div></form></div></div></div>

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
    all_unique_customers = sorted(list(set(t.customer_name for t in all_txs_ever if t.customer_name)))

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

    today_histories = PaymentHistory.query.filter_by(payment_date=thai_today).all()
    today_collected_cash = sum((h.pay_amount if h.pay_amount > 0 else (h.interest_paid + h.principal_reduced + h.fine_amount - h.discount_amount)) + h.fine_amount for h in today_histories)

    total_profit_sum = 0.0
    for tx in all_txs_ever:
        if tx.type == 'ยอดค้างเก่า':
            net_earned = max(0.0, (tx.original_principal - tx.principal))
        else:
            net_earned = max(tx.paid_interest, sum(h.interest_paid for h in tx.histories) if tx.histories else 0.0)
        fine_sum = sum(h.fine_amount for h in tx.histories) if tx.histories else 0.0
        disc_sum = sum(h.discount_amount for h in tx.histories) if tx.histories else 0.0
        total_profit_sum += (net_earned + fine_sum - disc_sum)

    inv_by_source = defaultdict(float)
    for tx in all_txs_ever:
        if tx.type != 'ยอดค้างเก่า':
            inv_by_source[tx.funding_source or 'ออมสิน'] += tx.original_principal

    total_new_principal = sum(tx.principal for tx in all_txs_ever if tx.type != 'ยอดค้างเก่า' and tx.principal > 0)
    total_debt_principal = sum(tx.principal for tx in all_txs_ever if tx.type == 'ยอดค้างเก่า' and tx.principal > 0)

    # ข้อมูลธุรกรรมวันนี้สำหรับลิ้นชักสรุป
    today_new_txs = [tx for tx in all_txs_ever if tx.start_date == thai_today]
    today_outflow_by_acc = defaultdict(float)
    for tx in today_new_txs:
        if tx.type != 'ยอดค้างเก่า':
            today_outflow_by_acc[tx.funding_source or 'ออมสิน'] += tx.original_principal

    today_inflow_by_acc = defaultdict(float)
    for h in today_histories:
        acc = h.receiving_account or 'ออมสิน'
        amt = h.pay_amount if h.pay_amount > 0 else (h.interest_paid + h.principal_reduced + h.fine_amount - h.discount_amount)
        if amt > 0:
            today_inflow_by_acc[acc] += amt

    bank_modals_html = ""
    for acc_key, acc_title, modal_id, theme_color in [('กรุงศรีอยุธยา', '🟡 กรุงศรีอยุธยา', 'modalKrungsri', 'warning'), ('ออมสิน', '🩷 ออมสิน', 'modalGSB', 'danger'), ('วอลเล็ท', '🟠 TrueMoney Wallet', 'modalWallet', 'info')]:
        inflows = "".join([f"<tr><td>{i['date']}</td><td>{i['customer']}</td><td class='text-success fw-bold'>+{i['amount']:,.2f}</td><td>{i['note']}</td></tr>" for i in bank_details_data[acc_key]['inflows']])
        outflows = "".join([f"<tr><td>{o['date']}</td><td>{o['target']}</td><td class='text-danger fw-bold'>-{o['amount']:,.2f}</td><td>{o['note']}</td></tr>" for o in bank_details_data[acc_key]['outflows']])
        bank_modals_html += f"""
        <div class="modal fade" id="{modal_id}" tabindex="-1"><div class="modal-dialog modal-lg modal-dialog-centered"><div class="modal-content border-{theme_color}"><div class="modal-header bg-{theme_color} text-white py-2"><h5 class="modal-title fw-bold fs-6">📊 ความเคลื่อนไหว: {acc_title}</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div><div class="modal-body" style="max-height: 60vh; overflow-y: auto;"><h6 class="text-success fw-bold">📥 เงินเข้า</h6><table class="table table-sm table-striped"><thead><tr><th>วันที่</th><th>รายการ</th><th>จำนวนเงิน</th><th>หมายเหตุ</th></tr></thead><tbody>{inflows or "<tr><td colspan='4' class='text-muted text-center'>ไม่มีรายการ</td></tr>"}</tbody></table><h6 class="text-danger fw-bold mt-3">📤 เงินออก</h6><table class="table table-sm table-striped"><thead><tr><th>วันที่</th><th>รายการ</th><th>จำนวนเงิน</th><th>หมายเหตุ</th></tr></thead><tbody>{outflows or "<tr><td colspan='4' class='text-muted text-center'>ไม่มีรายการ</td></tr>"}</tbody></table></div><div class="modal-footer py-2 justify-content-between"><div class="d-flex gap-2"><button class="btn btn-warning btn-sm fw-bold" data-bs-dismiss="modal" onclick="openAddModal('{acc_key}')">➕ เพิ่มรายการใหม่</button><a href="/export_bank_report/{acc_key}" class="btn btn-outline-secondary btn-sm">📥 เซฟไฟล์รายงาน</a></div><button class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ปิด</button></div></div></div></div>
        """

    rows, modals_html = "", ""
    for tx in transactions:
        badge_color = 'bg-success' if tx.status == 'ปกติ' else ('bg-info text-dark' if tx.status == 'ตัดยอดบางส่วน' else 'bg-danger')
        rows += f"""
        <tr>
            <td><a href="/customer_details/{tx.customer_name}" class="text-dark fw-bold text-decoration-none">{tx.customer_name}</a></td>
            <td><span class="badge bg-secondary">{tx.type}</span></td>
            <td>{get_funding_badge(tx.funding_source)}</td>
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
        modals_html += f"""
        <div class="modal fade" id="payModal{tx.id}" tabindex="-1"><div class="modal-dialog modal-dialog-centered"><div class="modal-content border-warning"><form action="/update_payment/{tx.id}" method="POST"><div class="modal-header bg-danger text-white py-2"><h5 class="modal-title fs-6">จัดการยอด: {tx.customer_name}</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div><div class="modal-body py-2"><div class="p-2 mb-2 bg-light rounded border d-flex justify-content-between"><div><small class="text-muted">ต้นคงเหลือ</small><b>{tx.principal:,.2f} ฿</b></div><div class="text-end"><small class="text-muted">ดอกสะสม</small><b class="text-danger">{tx.accumulated_interest:,.2f} ฿</b></div></div><div class="mb-2"><label class="form-label text-success fw-bold small">รับเข้าบัญชี:</label><select name="receiving_account" class="form-select form-select-sm"><option value="ออมสิน">🩷 ออมสิน</option><option value="กรุงศรีอยุธยา">🟢 กรุงศรีอยุธยา</option><option value="วอลเล็ท">🟠 TrueMoney Wallet</option></select></div><div class="mb-2"><label class="form-label fw-bold text-primary small">ประเภทการชำระ</label><select name="payment_type" class="form-select form-select-sm" id="payType{tx.id}" onchange="togglePayInput({tx.id})" required><option value="" disabled selected>-- เลือก --</option><option value="partial">จ่ายบางส่วน</option><option value="full">คืนครบ (ปิดบิล)</option><option value="adjust">ปรับปรุงยอดต้น</option></select></div><div class="mb-2" id="amountDiv{tx.id}"><label class="form-label fw-bold small">จำนวนเงินที่รับ (บาท)</label><input type="number" step="any" name="pay_amount" class="form-control form-control-sm" placeholder="0.00"></div><div class="mb-2" id="adjustContainer{tx.id}" style="display:none;"><label class="form-label fw-bold small">จำนวนเงินปรับปรุง (+/-)</label><input type="number" step="any" name="adjust_amount" class="form-control form-control-sm" placeholder="เช่น 500 หรือ -200"></div><div class="row g-2 mb-2"><div class="col-6"><label class="form-label text-danger small">ส่วนลด</label><input type="number" step="any" name="discount_amount" class="form-control form-control-sm" value="0"></div><div class="col-6"><label class="form-label text-warning text-dark small">ค่าปรับ</label><input type="number" step="any" name="fine_amount" class="form-control form-control-sm" value="0"></div></div><div class="mb-2"><label class="form-label small">หมายเหตุ</label><input type="text" name="note" class="form-control form-control-sm" placeholder="หมายเหตุ..."></div></div><div class="modal-footer py-2"><button class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ยกเลิก</button><button type="submit" class="btn btn-success btn-sm fw-bold px-3">บันทึก</button></div></form></div></div></div>
        """

    content = f"""
    <div class="card p-3 mb-4 shadow-sm border-warning bg-white">
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <h5 class="text-danger fw-bold mb-0">🏦 สถานะกระเป๋าเงินจริง (คลิกกล่องเพื่อดูประวัติและเพิ่มรายการ)</h5>
            <button class="btn btn-outline-danger btn-sm fw-bold" data-bs-toggle="modal" data-bs-target="#withdrawModal">💸 ถอนเงินออก / โยกเงิน</button>
        </div>
        <div class="row g-3">
            <div class="col-md-4"><div class="p-3 rounded border border-warning bg-warning bg-opacity-10" style="cursor:pointer;" data-bs-toggle="modal" data-bs-target="#modalKrungsri"><h6 class="text-dark fw-bold">🟡 กรุงศรีอยุธยา</h6><h3 class="fw-bold">{account_balances['กรุงศรีอยุธยา']:,.2f} ฿</h3><div style="font-size:0.8rem;" class="text-muted">ลงทุนใหม่: {inv_by_source['กรุงศรีอยุธยา']:,.2f} ฿</div></div></div>
            <div class="col-md-4"><div class="p-3 rounded border border-danger bg-danger bg-opacity-10" style="cursor:pointer;" data-bs-toggle="modal" data-bs-target="#modalGSB"><h6 class="text-danger fw-bold">🩷 ออมสิน</h6><h3 class="fw-bold">{account_balances['ออมสิน']:,.2f} ฿</h3><div style="font-size:0.8rem;" class="text-muted">ลงทุนใหม่: {inv_by_source['ออมสิน']:,.2f} ฿</div></div></div>
            <div class="col-md-4"><div class="p-3 rounded border border-info bg-info bg-opacity-10" style="cursor:pointer;" data-bs-toggle="modal" data-bs-target="#modalWallet"><h6 class="text-dark fw-bold">🟠 TrueMoney Wallet</h6><h3 class="fw-bold">{account_balances['วอลเล็ท']:,.2f} ฿</h3><div style="font-size:0.8rem;" class="text-muted">ลงทุนใหม่: {inv_by_source['วอลเล็ท']:,.2f} ฿</div></div></div>
        </div>
    </div>
    {bank_modals_html}

    <!-- Modal ถอนเงินออก / โยกเงินออก -->
    <div class="modal fade" id="withdrawModal" tabindex="-1"><div class="modal-dialog modal-dialog-centered"><div class="modal-content border-danger"><form action="/withdraw_money" method="POST"><div class="modal-header bg-danger text-white py-2"><h5 class="modal-title fw-bold fs-6">💸 ถอนเงินออก / โยกเงินจากบัญชี</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div><div class="modal-body"><div class="mb-2"><label class="form-label fw-bold small">เลือกบัญชีที่ต้องการถอนออก:</label><select name="account_name" class="form-select form-select-sm" required><option value="ออมสิน">🩷 ออมสิน</option><option value="กรุงศรีอยุธยา">🟢 กรุงศรีอยุธยา</option><option value="วอลเล็ท">🟠 TrueMoney Wallet</option></select></div><div class="mb-2"><label class="form-label fw-bold small">จำนวนเงินที่ถอนออก (บาท):</label><input type="number" step="any" name="amount" class="form-control form-control-sm" placeholder="0.00" required></div><div class="mb-2"><label class="form-label fw-bold small">หมายเหตุ / เหตุผลการถอน:</label><input type="text" name="note" class="form-control form-control-sm" placeholder="เช่น ค่าใช้จ่าย, โยกเงิน..."></div></div><div class="modal-footer py-2"><button type="submit" class="btn btn-danger btn-sm fw-bold px-3">ยืนยันการถอนออก</button></div></form></div></div></div></div>

    <!-- 4 กล่องสรุป -->
    <div class="row mb-4">
        <div class="col-md-3 mb-2"><div class="card p-3 text-white bg-success shadow-sm" style="cursor:pointer;" data-bs-toggle="modal" data-bs-target="#modalCollectedToday"><h6>💵 ยอดเก็บสดวันนี้</h6><h3 class="fw-bold mb-0">{today_collected_cash:,.2f} ฿</h3><small class="text-light" style="font-size:0.75rem;">คลิกเพื่อดูและเซฟไฟล์</small></div></div>
        <div class="col-md-3 mb-2"><div class="card p-3 text-white bg-primary shadow-sm" style="cursor:pointer;" data-bs-toggle="modal" data-bs-target="#modalTotalProfit"><h6>💰 กำไรสะสมทั้งหมด</h6><h3 class="fw-bold mb-0">{total_profit_sum:,.2f} ฿</h3><small class="text-light" style="font-size:0.75rem;">คลิกเพื่อดูและเซฟไฟล์</small></div></div>
        <div class="col-md-3 mb-2"><div class="card p-3 text-white bg-danger shadow-sm" style="cursor:pointer;" data-bs-toggle="modal" data-bs-target="#modalNewPrincipal"><h6>💼 ทุนใหม่คงค้าง</h6><h3 class="fw-bold mb-0">{total_new_principal:,.2f} ฿</h3><small class="text-light" style="font-size:0.75rem;">คลิกเพื่อดูและเซฟไฟล์</small></div></div>
        <div class="col-md-3 mb-2"><div class="card p-3 text-white bg-warning text-dark shadow-sm" style="cursor:pointer;" data-bs-toggle="modal" data-bs-target="#modalDebtPrincipal"><h6>📂 ยอดค้างเก่ารอเก็บ</h6><h3 class="fw-bold mb-0">{total_debt_principal:,.2f} ฿</h3><small class="text-dark" style="font-size:0.75rem;">คลิกเพื่อดูและเซฟไฟล์</small></div></div>
    </div>

    <!-- Modals 4 กล่อง -->
    <div class="modal fade" id="modalCollectedToday" tabindex="-1"><div class="modal-dialog modal-dialog-centered"><div class="modal-content"><div class="modal-header bg-success text-white py-2"><h5 class="modal-title fs-6">💵 รายละเอียดยอดเก็บสดวันนี้</h5><button class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div><div class="modal-body"><p>ยอดรวมเก็บสดวันนี้: <b>{today_collected_cash:,.2f} บาท</b></p><a href="/export_report/collected_today" class="btn btn-success btn-sm w-100 fw-bold">📥 ดาวน์โหลดเซฟไฟล์รายงานนี้</a></div></div></div></div>
    <div class="modal fade" id="modalTotalProfit" tabindex="-1"><div class="modal-dialog modal-dialog-centered"><div class="modal-content"><div class="modal-header bg-primary text-white py-2"><h5 class="modal-title fs-6">💰 รายละเอียดกำไรสะสมทั้งหมด</h5><button class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div><div class="modal-body"><p>กำไรสะสมรวม: <b>{total_profit_sum:,.2f} บาท</b></p><a href="/export_report/total_profit" class="btn btn-primary btn-sm w-100 fw-bold">📥 ดาวน์โหลดเซฟไฟล์รายงานนี้</a></div></div></div></div>
    <div class="modal fade" id="modalNewPrincipal" tabindex="-1"><div class="modal-dialog modal-dialog-centered"><div class="modal-content"><div class="modal-header bg-danger text-white py-2"><h5 class="modal-title fs-6">💼 รายละเอียดทุนใหม่คงค้าง</h5><button class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div><div class="modal-body"><p>ทุนใหม่คงค้างรวม: <b>{total_new_principal:,.2f} บาท</b></p><a href="/export_report/new_principal" class="btn btn-danger btn-sm w-100 fw-bold">📥 ดาวน์โหลดเซฟไฟล์รายงานนี้</a></div></div></div></div>
    <div class="modal fade" id="modalDebtPrincipal" tabindex="-1"><div class="modal-dialog modal-dialog-centered"><div class="modal-content"><div class="modal-header bg-warning py-2"><h5 class="modal-title fs-6 text-dark">📂 รายละเอียดยอดค้างเก่ารอเก็บ</h5><button class="btn-close" data-bs-dismiss="modal"></button></div><div class="modal-body"><p>ยอดค้างเก่าคงเหลือรวม: <b>{total_debt_principal:,.2f} บาท</b></p><a href="/export_report/debt_principal" class="btn btn-warning btn-sm w-100 fw-bold text-dark">📥 ดาวน์โหลดเซฟไฟล์รายงานนี้</a></div></div></div></div>

    <!-- ลิ้นชักสรุปรายการธุรกรรมวันนี้ -->
    <div class="card mb-4 shadow-sm border-info">
        <div class="card-header bg-info bg-opacity-25 py-2">
            <button class="btn btn-sm btn-outline-dark w-100 fw-bold d-flex justify-content-between align-items-center border-0" type="button" data-bs-toggle="collapse" data-bs-target="#todayTransactionCollapse">
                <span>⚡ ลิ้นชักสรุปรายการธุรกรรมประจำวันนี้ ({thai_today.strftime('%d/%m/%Y')})</span>
                <span>▼ คลิกเพื่อเปิดดูรายละเอียด</span>
            </button>
        </div>
        <div class="collapse" id="todayTransactionCollapse">
            <div class="card-body bg-light">
                <div class="row g-3">
                    <div class="col-md-6">
                        <div class="p-3 bg-white rounded border border-danger">
                            <h6 class="text-danger fw-bold border-bottom pb-2">📤 ปล่อยยอดกู้ใหม่วันนี้ (แยกตามบัญชี)</h6>
                            <ul class="list-unstyled mb-0 small">
                                <li class="d-flex justify-content-between py-1 border-bottom"><span>🩷 ออมสิน:</span><b class="text-danger">-{today_outflow_by_acc['ออมสิน']:,.2f} ฿</b></li>
                                <li class="d-flex justify-content-between py-1 border-bottom"><span>🟡 กรุงศรีอยุธยา:</span><b class="text-danger">-{today_outflow_by_acc['กรุงศรีอยุธยา']:,.2f} ฿</b></li>
                                <li class="d-flex justify-content-between py-1"><span>🟠 TrueMoney Wallet:</span><b class="text-danger">-{today_outflow_by_acc['วอลเล็ท']:,.2f} ฿</b></li>
                            </ul>
                        </div>
                    </div>
                    <div class="col-md-6">
                        <div class="p-3 bg-white rounded border border-success">
                            <h6 class="text-success fw-bold border-bottom pb-2">📥 เก็บยอดชำระเข้ามาวันนี้ (แยกตามบัญชี)</h6>
                            <ul class="list-unstyled mb-0 small">
                                <li class="d-flex justify-content-between py-1 border-bottom"><span>🩷 ออมสิน:</span><b class="text-success">+{today_inflow_by_acc['ออมสิน']:,.2f} ฿</b></li>
                                <li class="d-flex justify-content-between py-1 border-bottom"><span>🟡 กรุงศรีอยุธยา:</span><b class="text-success">+{today_inflow_by_acc['กรุงศรีอยุธยา']:,.2f} ฿</b></li>
                                <li class="d-flex justify-content-between py-1"><span>🟠 TrueMoney Wallet:</span><b class="text-success">+{today_inflow_by_acc['วอลเล็ท']:,.2f} ฿</b></li>
                            </ul>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="card p-4 shadow-sm border-warning">
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <h4 class="mb-0 fs-5 text-danger fw-bold">🔔 รายการที่ต้องทวงวันนี้</h4>
            <form method="GET" class="d-flex gap-2">
                <input type="text" name="search" id="liveSearchInput" class="form-control form-control-sm" placeholder="🔍 พิมพ์ค้นหาชื่อลูกค้า..." value="{search_query}" list="customerListOptions" autocomplete="off">
                <datalist id="customerListOptions">
                    {''.join([f'<option value="{c}">' for c in all_unique_customers])}
                </datalist>
                <button class="btn btn-sm btn-outline-danger">ค้นหา</button>
            </form>
        </div>
        <div class="table-responsive">
            <table class="table table-striped align-middle text-nowrap">
                <thead class="table-dark"><tr><th>ชื่อลูกค้า</th><th>ประเภท</th><th>บัญชีปล่อย</th><th>วันที่กู้</th><th>ลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th><th>ดอก/วัน</th><th>ดอกสะสม</th><th>สถานะ</th><th>จัดการ</th></tr></thead>
                <tbody>{rows if rows else "<tr><td colspan='11' class='text-center text-muted'>ไม่มีรายการทวงในวันนี้</td></tr>"}</tbody>
            </table>
        </div>
    </div>

    <!-- Modal เพิ่มรายการใหม่ -->
    <div class="modal fade" id="addTransactionModal" tabindex="-1"><div class="modal-dialog modal-dialog-centered"><div class="modal-content border-success"><form action="/add_transaction" method="POST"><div class="modal-header bg-success text-white py-2"><h5 class="modal-title fw-bold fs-6">➕ เพิ่มรายการใหม่</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div><div class="modal-body"><div class="mb-2"><label class="form-label fw-bold small">ประเภท</label><select name="type" class="form-select form-select-sm"><option value="เงินฉุกเฉิน">เงินฉุกเฉิน</option><option value="ผ่อนทอง">ผ่อนทอง</option><option value="ยอดค้างเก่า">ยอดค้างเก่า</option></select></div><div class="mb-2"><label class="form-label fw-bold small">ชื่อลูกค้า</label><input type="text" name="customer_name" class="form-control form-control-sm" required></div><div class="mb-2"><label class="form-label fw-bold small">เบอร์โทร</label><input type="text" name="phone" class="form-control form-control-sm"></div><div class="mb-2"><label class="form-label fw-bold small">แหล่งทุนปล่อยกู้</label><select name="funding_source" id="addFundingSource" class="form-select form-select-sm"><option value="ออมสิน">🩷 ออมสิน</option><option value="กรุงศรีอยุธยา">🟢 กรุงศรีอยุธยา</option><option value="วอลเล็ท">🟠 TrueMoney Wallet</option></select></div><div class="mb-2"><label class="form-label fw-bold small">ยอดเงินลงทุน/เงินต้น</label><input type="number" step="any" name="principal" class="form-control form-control-sm" required></div><div class="mb-2"><label class="form-label fw-bold small">ดอกเบี้ย/วัน</label><input type="number" step="any" name="daily_interest" class="form-control form-control-sm" value="0" required></div></div><div class="modal-footer py-2"><button type="submit" class="btn btn-success btn-sm fw-bold px-3">บันทึก</button></div></form></div></div></div>
    {modals_html}
    """
    html = BASE_LAYOUT.replace('{% block header %}Dashboard{% endblock %}', '🔱 Dashboard บริหารจัดการระบบ')
    return render_template_string(html.replace('{% block content %}{% endblock %}', content), title="Dashboard", page="dashboard")

@app.route('/withdraw_money', methods=['POST'])
def withdraw_money():
    if 'admin' not in session: return redirect(url_for('login'))
    try:
        acc = request.form.get('account_name')
        amt = float(request.form.get('amount', 0))
        note = request.form.get('note', '').strip() or 'ถอนเงินออก / โยกเงิน'
        if amt > 0:
            db.session.add(BankExpenseLog(expense_date=get_thai_today(), account_name=acc, amount=amt, note=note, admin_name=session.get('admin')))
            adj = BankAdjustment.query.filter_by(account_name=acc).first()
            if not adj:
                db.session.add(BankAdjustment(account_name=acc, adjustment_amount=-amt))
            else:
                adj.adjustment_amount -= amt
            db.session.commit()
    except Exception as e: print("Withdraw error:", e)
    return redirect(url_for('index'))

@app.route('/add_transaction', methods=['POST'])
def add_transaction():
    if 'admin' not in session: return redirect(url_for('login'))
    try:
        p_val = float(request.form.get('principal', 0))
        funding = request.form.get('funding_source', 'ออมสิน')
        new_tx = Transaction(
            type=request.form.get('type'), customer_name=request.form.get('customer_name'),
            phone=request.form.get('phone', '').strip(),
            sales_name=session.get('admin'), original_principal=p_val, principal=p_val,
            daily_interest=float(request.form.get('daily_interest', 0)),
            initial_daily_interest=float(request.form.get('daily_interest', 0)),
            funding_source=funding, receiving_account=funding
        )
        db.session.add(new_tx)
        db.session.add(BankExpenseLog(expense_date=get_thai_today(), account_name=funding, amount=p_val, note=f"ปล่อยกู้ใหม่: {request.form.get('customer_name')}", admin_name=session.get('admin')))
        adj = BankAdjustment.query.filter_by(account_name=funding).first()
        if not adj:
            db.session.add(BankAdjustment(account_name=funding, adjustment_amount=-p_val))
        else:
            adj.adjustment_amount = max(0.0, adj.adjustment_amount - p_val)
        db.session.commit()
    except Exception as e: print("Error:", e)
    return redirect(url_for('index'))

@app.route('/transactions')
def transactions_list():
    if 'admin' not in session: return redirect(url_for('login'))
    search_q = request.args.get('search', '').strip()
    all_txs = Transaction.query.order_by(Transaction.start_date.desc()).all()
    all_customers = sorted(list(set(t.customer_name for t in all_txs if t.customer_name)))

    if search_q:
        all_txs = [t for t in all_txs if search_q.lower() in t.customer_name.lower()]

    active_txs = [tx for tx in all_txs if tx.principal > 0]
    closed_txs = [tx for tx in all_txs if tx.principal <= 0]

    def build_rows(tx_list):
        res = ""
        for tx in tx_list:
            calculate_tx_values(tx)
            badge_color = 'bg-success' if tx.status == 'ปกติ' else 'bg-danger'
            res += f"""
            <tr>
                <td><a href="/customer_details/{tx.customer_name}" class="text-dark fw-bold text-decoration-none">{tx.customer_name}</a></td>
                <td><span class="badge bg-secondary">{tx.type}</span></td>
                <td>{get_funding_badge(tx.funding_source)}</td>
                <td>{tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'}</td>
                <td>{tx.original_principal:,.2f}</td>
                <td>{tx.principal:,.2f}</td>
                <td><a href="/history/{tx.id}" target="_blank" class="text-primary fw-bold">{tx.total_paid:,.2f}</a></td>
                <td><span class="badge {badge_color}">{'ปิดบิลแล้ว' if tx.principal <= 0 else tx.status}</span></td>
            </tr>
            """
        return res

    content = f"""
    <div class="card p-4 shadow-sm border-warning">
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <h4 class="mb-0 fs-5 text-danger fw-bold">📋 รายการทั้งหมด (แยกหมวดหมู่)</h4>
            <form method="GET" class="d-flex gap-2">
                <input type="text" name="search" class="form-control form-control-sm" placeholder="🔍 ค้นหาชื่อลูกค้า..." value="{search_q}" list="custOpts" autocomplete="off">
                <datalist id="custOpts">
                    {''.join([f'<option value="{c}">' for c in all_customers])}
                </datalist>
                <button class="btn btn-sm btn-outline-danger">ค้นหา</button>
            </form>
        </div>
        <h6 class="text-success fw-bold border-bottom pb-2">🟢 รายการที่กำลังเดินอยู่ ({len(active_txs)} บิล)</h6>
        <div class="table-responsive mb-4">
            <table class="table table-striped align-middle text-nowrap">
                <thead class="table-dark"><tr><th>ชื่อลูกค้า</th><th>ประเภทลูกค้า</th><th>บัญชีปล่อย</th><th>วันที่กู้</th><th>ลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th><th>สถานะ</th></tr></thead>
                <tbody>{build_rows(active_txs) if active_txs else "<tr><td colspan='8' class='text-center text-muted'>ไม่มีรายการที่กำลังเดินอยู่</td></tr>"}</tbody>
            </table>
        </div>
        <h6 class="text-secondary fw-bold border-bottom pb-2">📁 บัญชีที่ปิดไปแล้ว (ประวัติย้อนหลัง {len(closed_txs)} บิล)</h6>
        <div class="table-responsive">
            <table class="table table-striped align-middle text-nowrap">
                <thead class="table-secondary"><tr><th>ชื่อลูกค้า</th><th>ประเภทลูกค้า</th><th>บัญชีปล่อย</th><th>วันที่กู้</th><th>ลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th><th>สถานะ</th></tr></thead>
                <tbody>{build_rows(closed_txs) if closed_txs else "<tr><td colspan='8' class='text-center text-muted'>ไม่มีประวัติบัญชีที่ปิดไปแล้ว</td></tr>"}</tbody>
            </table>
        </div>
    </div>
    """
    html = BASE_LAYOUT.replace('{% block header %}รายการทั้งหมด{% endblock %}', 'รายการทั้งหมด').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="รายการทั้งหมด", page="transactions")

@app.route('/members')
def members():
    if 'admin' not in session: return redirect(url_for('login'))
    search_q = request.args.get('search', '').strip()
    all_txs = Transaction.query.all()
    customers = sorted(list(set(t.customer_name for t in all_txs if t.customer_name)))
    
    if search_q:
        customers = [c for c in customers if search_q.lower() in c.lower()]

    rows = ""
    for c in customers:
        c_txs = [t for t in all_txs if t.customer_name == c]
        phone_val = next((t.phone for t in c_txs if t.phone), '-')
        active_cnt = sum(1 for t in c_txs if t.principal > 0)
        closed_cnt = sum(1 for t in c_txs if t.principal <= 0)
        rows += f"""
        <tr>
            <td><a href="/customer_details/{c}" class="text-dark fw-bold text-decoration-none">👤 {c}</a></td>
            <td>{phone_val}</td>
            <td><span class="badge bg-success">เดิน {active_cnt} บิล</span></td>
            <td><span class="badge bg-secondary">ปิด {closed_cnt} บิล</span></td>
            <td><a href="/customer_details/{c}" class="btn btn-sm btn-warning fw-bold">🔍 ตรวจสอบประวัติ</a></td>
        </tr>
        """

    content = f"""
    <div class="card p-4 shadow-sm border-warning">
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <h4 class="mb-0 fs-5 text-danger fw-bold">👥 สมาชิกทั้งหมด</h4>
            <form method="GET" class="d-flex gap-2">
                <input type="text" name="search" class="form-control form-control-sm" placeholder="🔍 ค้นหาชื่อสมาชิก..." value="{search_q}" list="custOpts2" autocomplete="off">
                <datalist id="custOpts2">
                    {''.join([f'<option value="{c}">' for c in customers])}
                </datalist>
                <button class="btn btn-sm btn-outline-danger">ค้นหา</button>
            </form>
        </div>
        <div class="table-responsive">
            <table class="table table-striped align-middle text-nowrap">
                <thead class="table-dark"><tr><th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>บิลกำลังเดิน</th><th>บิลที่ปิดแล้ว</th><th>จัดการ</th></tr></thead>
                <tbody>{rows if rows else "<tr><td colspan='5' class='text-center text-muted'>ไม่พบรายชื่อสมาชิก</td></tr>"}</tbody>
            </table>
        </div>
    </div>
    """
    html = BASE_LAYOUT.replace('{% block header %}สมาชิกทั้งหมด{% endblock %}', 'สมาชิกทั้งหมด').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="สมาชิก", page="members")

@app.route('/customer_details/<path:cust_name>')
def customer_details(cust_name):
    if 'admin' not in session: return redirect(url_for('login'))
    txs = Transaction.query.filter(Transaction.customer_name.ilike(f"%{cust_name}%")).all()
    for tx in txs: calculate_tx_values(tx)
    phone_val = next((t.phone for t in txs if t.phone), '-')
    rows = "".join([f"<tr><td><span class='badge bg-secondary'>{tx.type}</span></td><td>{get_funding_badge(tx.funding_source)}</td><td>{tx.start_date.strftime('%d/%m/%Y')}</td><td>{tx.original_principal:,.2f}</td><td>{tx.principal:,.2f}</td><td><a href='/history/{tx.id}' target='_blank' class='text-primary fw-bold'>{tx.total_paid:,.2f}</a></td></tr>" for tx in txs])
    content = f"""
    <div class="card p-4 shadow-sm border-warning">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h4 class="mb-0 fs-5 text-danger fw-bold">👤 ลูกค้า: {cust_name} (เบอร์โทร: {phone_val})</h4>
            <a href="/members" class="btn btn-sm btn-secondary fw-bold">⬅️ กลับ</a>
        </div>
        <div class="table-responsive">
            <table class="table table-striped align-middle text-nowrap">
                <thead class="table-dark"><tr><th>ประเภทลูกค้า</th><th>บัญชีปล่อย</th><th>วันที่กู้</th><th>ลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th></tr></thead>
                <tbody>{rows if rows else "<tr><td colspan='6' class='text-center text-muted'>ไม่มีข้อมูลบิล</td></tr>"}</tbody>
            </table>
        </div>
    </div>
    """
    html = BASE_LAYOUT.replace('{% block header %}รายละเอียดลูกค้า{% endblock %}', f'ลูกค้า: {cust_name}').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title=cust_name, page="members")

@app.route('/history/<int:tx_id>')
def payment_history(tx_id):
    if 'admin' not in session: return redirect(url_for('login'))
    tx = Transaction.query.get_or_404(tx_id)
    histories = PaymentHistory.query.filter_by(transaction_id=tx.id).all()
    rows = "".join([f"<tr><td>{h.payment_date.strftime('%d/%m/%Y')}</td><td>{h.pay_amount:,.2f}</td><td>{get_funding_badge(h.receiving_account)}</td></tr>" for h in histories])
    content = f"""<div class="card p-4 shadow-sm border-warning"><h4 class="mb-3 fs-5 text-danger fw-bold">📜 ประวัติ: {tx.customer_name}</h4><a href="/transactions" class="btn btn-sm btn-secondary mb-3">⬅️ กลับ</a><table class="table table-striped"><thead><tr><th>วันที่</th><th>ยอดจ่าย</th><th>ช่องทาง</th></tr></thead><tbody>{rows}</tbody></table></div>"""
    html = BASE_LAYOUT.replace('{% block header %}ประวัติ{% endblock %}', 'ประวัติการชำระ').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="ประวัติ", page="dashboard")

@app.route('/export_report/<report_type>')
def export_report(report_type):
    if 'admin' not in session: return redirect(url_for('login'))
    si = io.StringIO()
    cw = csv.writer(si)
    if report_type == 'collected_today':
        cw.writerow(['PaymentDate', 'CustomerName', 'PayAmount', 'FineAmount', 'Account'])
        for h in PaymentHistory.query.filter_by(payment_date=get_thai_today()).all():
            cw.writerow([h.payment_date, h.transaction.customer_name if h.transaction else '-', h.pay_amount, h.fine_amount, h.receiving_account])
    elif report_type == 'total_profit':
        cw.writerow(['CustomerID', 'CustomerName', 'Type', 'Status'])
        for t in Transaction.query.all():
            cw.writerow([t.id, t.customer_name, t.type, t.status])
    elif report_type == 'new_principal':
        cw.writerow(['CustomerName', 'Type', 'Principal', 'FundingSource'])
        for t in Transaction.query.filter(Transaction.principal > 0, Transaction.type != 'ยอดค้างเก่า').all():
            cw.writerow([t.customer_name, t.type, t.principal, t.funding_source])
    elif report_type == 'debt_principal':
        cw.writerow(['CustomerName', 'Type', 'Principal'])
        for t in Transaction.query.filter(Transaction.principal > 0, Transaction.type == 'ยอดค้างเก่า').all():
            cw.writerow([t.customer_name, t.type, t.principal])
    
    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name=f"report_{report_type}_{get_thai_today().strftime('%Y%m%d')}.csv")

@app.route('/export_bank_report/<bank_name>')
def export_bank_report(bank_name):
    if 'admin' not in session: return redirect(url_for('login'))
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['BankName', 'Date', 'CustomerName', 'Amount', 'Type'])
    for h in PaymentHistory.query.filter_by(receiving_account=bank_name).all():
        cw.writerow([bank_name, h.payment_date, h.transaction.customer_name if h.transaction else '-', h.pay_amount, 'Inflow'])
    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name=f"bank_{bank_name}_{get_thai_today().strftime('%Y%m%d')}.csv")

@app.route('/export_data')
def export_data():
    if 'admin' not in session: return redirect(url_for('login'))
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Type', 'CustomerName', 'Phone', 'Principal', 'Status', 'FundingSource'])
    for t in Transaction.query.all():
        cw.writerow([t.id, t.type, t.customer_name, t.phone, t.principal, t.status, t.funding_source])
    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8-sig'))
    output.seek(0)
    return send_file(output, mimetype='text/csv', as_attachment=True, download_name="sublon_backup.csv")

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
                    phone=row.get('Phone', ''), original_principal=float(row.get('Principal', 0)),
                    principal=float(row.get('Principal', 0)), status=row.get('Status', 'ปกติ'),
                    funding_source=row.get('FundingSource', 'ออมสิน'), sales_name=session.get('admin')
                ))
            db.session.commit()
        except Exception as e: print("Import error:", e)
    return redirect(url_for('index'))

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
