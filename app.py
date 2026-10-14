from flask import Flask, render_template_string, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import traceback

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///thonglon.db'
app.config['SECRET_KEY'] = 'your_secret_key'
db = SQLAlchemy(app)

VALID_USERS = {
    'nueng': '909090',
    'nice': '022540'
}

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False)
    customer_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20), nullable=True)
    sales_name = db.Column(db.String(100), nullable=False)
    start_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    principal = db.Column(db.Float, nullable=False)      
    daily_interest = db.Column(db.Float, nullable=False)
    paid_interest = db.Column(db.Float, default=0.0)     
    status = db.Column(db.String(20), default='ปกติ')

with app.app_context():
    db.create_all()

BASE_LAYOUT = """
<!DOCTYPE html>
<html lang="th">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ title }} - ทองล้น</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600&display=swap" rel="stylesheet">
    <style>
        body { font-family: 'Prompt', sans-serif; background-color: #f8f9fa; }
        .sidebar { width: 260px; min-height: 100vh; background: #fff; border-right: 1px solid #dee2e6; position: fixed; }
        .main-content { margin-left: 260px; padding: 30px; }
        .nav-link { color: #333; font-weight: 500; padding: 10px 20px; border-radius: 6px; margin-bottom: 5px; }
        .nav-link:hover, .nav-link.active { background-color: #ffc107; color: #000; }
    </style>
</head>
<body>
    <div class="sidebar p-3 d-flex flex-column">
        <h4 class="text-warning fw-bold mb-4 px-2">🪙 ทองล้น.com</h4>
        <ul class="nav nav-pills flex-column mb-auto">
            <li class="nav-item"><a href="/" class="nav-link {% if page == 'dashboard' %}active{% endif %}">📊 Dashboard</a></li>
            <li><a href="/members" class="nav-link {% if page == 'members' %}active{% endif %}">👥 1. สมาชิกทั้งหมด</a></li>
            <li><a href="/sales_members" class="nav-link {% if page == 'sales' %}active{% endif %}">📋 2. สมาชิกภายใต้เซลล์</a></li>
            <li><a href="/customer_summary" class="nav-link {% if page == 'customer' %}active{% endif %}">📂 3. สรุปลูกค้า</a></li>
            <li><a href="/monthly_summary" class="nav-link {% if page == 'monthly' %}active{% endif %}">📅 4. สรุปยอดรายเดือน</a></li>
        </ul>
        <hr>
        <a href="/logout" class="btn btn-outline-danger w-100">ออกจากระบบ</a>
    </div>
    <div class="main-content">
        <h2 class="mb-4 text-dark fw-bold">{% block header %}{% endblock %}</h2>
        {% block content %}{% endblock %}
    </div>
</body>
</html>
"""

@app.route('/', methods=['GET', 'POST'])
def index():
    if 'admin' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        try:
            new_tx = Transaction(
                type=request.form.get('type'),
                customer_name=request.form.get('customer_name'),
                phone=request.form.get('phone'),
                sales_name=request.form.get('sales_name'),
                start_date=datetime.strptime(request.form.get('start_date'), '%Y-%m-%d').date() if request.form.get('start_date') else datetime.utcnow().date(),
                principal=float(request.form.get('principal', 0)),
                daily_interest=float(request.form.get('daily_interest', 0))
            )
            db.session.add(new_tx)
            db.session.commit()
        except Exception as e:
            print("Error adding transaction:", e)
        return redirect(url_for('index'))

    search_query = request.args.get('search', '').strip()
    if search_query:
        transactions = Transaction.query.filter(
            (Transaction.customer_name.contains(search_query)) | 
            (Transaction.phone.contains(search_query))
        ).all()
    else:
        transactions = Transaction.query.all()

    today = datetime.now().date()
    for tx in transactions:
        days = (today - tx.start_date).days
        if days < 1:
            days = 1
        tx.days_passed = days
        acc = (tx.daily_interest * days) - tx.paid_interest
        tx.accumulated_interest = acc if acc > 0 else 0.0

    all_txs = Transaction.query.all()
    total_investment = sum(tx.principal for tx in all_txs if tx.status != 'คืนแล้ว')
    total_profit = sum(tx.paid_interest for tx in all_txs)

    rows = ""
    for tx in transactions:
        rows += f"""
        <tr>
            <td>{tx.customer_name}</td>
            <td>{tx.phone or '-'}</td>
            <td>{tx.sales_name}</td>
            <td>{tx.principal:,.2f}</td>
            <td>{tx.daily_interest:,.2f}</td>
            <td>{tx.days_passed} วัน</td>
            <td>{tx.accumulated_interest:,.2f}</td>
            <td><span class="badge {'bg-success' if tx.status=='ปกติ' else 'bg-warning'}">{tx.status}</span></td>
            <td>
                <form action="/update_payment/{tx.id}" method="POST" class="d-inline">
                    <input type="hidden" name="payment_type" value="full">
                    <button type="submit" class="btn btn-sm btn-success" onclick="return confirm('ยืนยันปิดยอด/คืนทั้งหมด?')">คืนครบ</button>
                </form>
                <a href="/delete_tx/{tx.id}" class="btn btn-sm btn-danger" onclick="return confirm('ยืนยันการลบ?')">ลบ</a>
            </td>
        </tr>
        """

    content = f"""
    <div class="row mb-4">
        <div class="col-md-6">
            <div class="card p-3 shadow-sm bg-warning text-dark">
                <h5>ยอดลงทุนรวม (เงินต้นค้าง)</h5>
                <h3>{total_investment:,.2f} บาท</h3>
            </div>
        </div>
        <div class="col-md-6">
            <div class="card p-3 shadow-sm bg-success text-white">
                <h5>กำไรสะสมทั้งหมด</h5>
                <h3>{total_profit:,.2f} บาท</h3>
            </div>
        </div>
    </div>

    <div class="card p-4 shadow-sm mb-4">
        <h4 class="mb-3">➕ เพิ่มรายการใหม่</h4>
        <form method="POST" class="row g-3">
            <div class="col-md-3">
                <label class="form-label">ประเภท</label>
                <select name="type" class="form-select" required>
                    <option value="เงินฉุกเฉิน">เงินฉุกเฉิน</option>
                    <option value="ผ่อนทอง">ผ่อนทอง</option>
                </select>
            </div>
            <div class="col-md-3">
                <label class="form-label">ชื่อลูกค้า</label>
                <input type="text" name="customer_name" class="form-control" required>
            </div>
            <div class="col-md-3">
                <label class="form-label">เบอร์โทร</label>
                <input type="text" name="phone" class="form-control">
            </div>
            <div class="col-md-3">
                <label class="form-label">เซลล์ผู้ดูแล</label>
                <select name="sales_name" class="form-select" required>
                    <option value="เซลล์ A">เซลล์ A</option>
                    <option value="เซลล์ B">เซลล์ B</option>
                    <option value="เซลล์ C">เซลล์ C</option>
                </select>
            </div>
            <div class="col-md-3">
                <label class="form-label">วันที่เริ่ม</label>
                <input type="date" name="start_date" class="form-control" value="{datetime.now().strftime('%Y-%m-%d')}" required>
            </div>
            <div class="col-md-3">
                <label class="form-label">เงินต้น (บาท)</label>
                <input type="number" step="any" name="principal" class="form-control" required>
            </div>
            <div class="col-md-3">
                <label class="form-label">ดอกเบี้ย/วัน (บาท)</label>
                <input type="number" step="any" name="daily_interest" class="form-control" required>
            </div>
            <div class="col-md-3 d-flex align-items-end">
                <button type="submit" class="btn btn-dark w-100">บันทึกข้อมูล</button>
            </div>
        </form>
    </div>

    <div class="card p-4 shadow-sm">
        <div class="d-flex justify-content-between align-items-center mb-3">
            <h4 class="mb-0">📋 รายการทั้งหมด</h4>
            <form method="GET" class="d-flex">
                <input type="text" name="search" class="form-control form-control-sm me-2" placeholder="ค้นหาชื่อ หรือเบอร์โทร..." value="{search_query}">
                <button type="submit" class="btn btn-sm btn-outline-dark">ค้นหา</button>
            </form>
        </div>
        <table class="table table-striped align-middle">
            <thead>
                <tr>
                    <th>ชื่อลูกค้า</th>
                    <th>เบอร์โทร</th>
                    <th>เซลล์</th>
                    <th>เงินต้น</th>
                    <th>ดอกเบี้ย/วัน</th>
                    <th>เวลาผ่านไป</th>
                    <th>ดอกเบี้ยสะสม</th>
                    <th>สถานะ</th>
                    <th>จัดการ</th>
                </tr>
            </thead>
            <tbody>
                {rows if rows else "<tr><td colspan='9' class='text-center text-muted'>ยังไม่มีข้อมูลรายการ</td></tr>"}
            </tbody>
        </table>
    </div>
    """

    html = BASE_LAYOUT.replace('{% block header %}Dashboard{% endblock %}', 'Dashboard บริหารจัดการระบบ')
    html = html.replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="Dashboard", page="dashboard")

@app.route('/update_payment/<int:tx_id>', methods=['POST'])
def update_payment(tx_id):
    if 'admin' not in session:
        return redirect(url_for('login'))
        
    tx = Transaction.query.get_or_404(tx_id)
    today = datetime.now().date()
    days = (today - tx.start_date).days
    if days < 1:
        days = 1
        
    total_acc_interest = (tx.daily_interest * days) - tx.paid_interest
    if total_acc_interest < 0:
        total_acc_interest = 0.0

    tx.paid_interest += total_acc_interest
    tx.principal = 0.0
    tx.status = 'คืนแล้ว'
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/delete_tx/<int:tx_id>')
def delete_tx(tx_id):
    if 'admin' not in session:
        return redirect(url_for('login'))
    tx = Transaction.query.get_or_404(tx_id)
    db.session.delete(tx)
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/members')
def members():
    if 'admin' not in session:
        return redirect(url_for('login'))
    
    txs = Transaction.query.all()
    rows = "".join([f"<tr><td>{t.customer_name}</td><td>{t.phone or '-'}</td><td>{t.sales_name}</td><td>{t.principal:,.2f}</td><td>{t.status}</td></tr>" for t in txs])
    
    content = f"""
    <div class="card p-4 shadow-sm">
        <h4 class="mb-3">รายชื่อสมาชิกทั้งหมด</h4>
        <table class="table table-striped">
            <thead><tr><th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>เซลล์ผู้ดูแล</th><th>เงินต้น</th><th>สถานะ</th></tr></thead>
            <tbody>{rows if rows else "<tr><td colspan='5' class='text-center text-muted'>ยังไม่มีข้อมูลสมาชิก</td></tr>"}</tbody>
        </table>
    </div>
    """
    html = BASE_LAYOUT.replace('{% block header %}1. สมาชิกทั้งหมด{% endblock %}', 'สมาชิกทั้งหมด').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="สมาชิกทั้งหมด", page="members")

@app.route('/sales_members')
def sales_members():
    if 'admin' not in session:
        return redirect(url_for('login'))
    
    all_txs = Transaction.query.all()
    sales_data = {}
    for tx in all_txs:
        if tx.sales_name not in sales_data:
            sales_data[tx.sales_name] = []
        sales_data[tx.sales_name].append(tx)

    sales_content = ""
    for sales, txs in sales_data.items():
        sub_rows = "".join([f"<tr><td>{t.customer_name}</td><td>{t.phone or '-'}</td><td>{t.principal:,.2f}</td><td>{t.status}</td></tr>" for t in txs])
        sales_content += f"""
        <div class="card mb-4 shadow-sm">
            <div class="card-header bg-dark text-white"><h5 class="mb-0">เซลล์: {sales}</h5></div>
            <div class="card-body">
                <table class="table table-striped">
                    <thead><tr><th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>เงินต้น</th><th>สถานะ</th></tr></thead>
                    <tbody>{sub_rows}</tbody>
                </table>
            </div>
        </div>
        """

    content = sales_content if sales_content else '<div class="card p-4 shadow-sm"><p class="text-muted text-center">ยังไม่มีข้อมูลสมาชิกภายใต้เซลล์</p></div>'
    html = BASE_LAYOUT.replace('{% block header %}2. สมาชิกภายใต้เซลล์{% endblock %}', 'สมาชิกแยกตามเซลล์').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="สมาชิกภายใต้เซลล์", page="sales")

@app.route('/customer_summary')
def customer_summary():
    if 'admin' not in session:
        return redirect(url_for('login'))
    
    content = """
    <div class="card p-4 shadow-sm">
        <h4 class="mb-3">สรุปข้อมูลลูกค้า</h4>
        <p class="text-muted">หน้ารายละเอียดและประวัติการทำรายการของลูกค้าแต่ละราย</p>
    </div>
    """
    html = BASE_LAYOUT.replace('{% block header %}3. สรุปลูกค้า{% endblock %}', 'สรุปลูกค้า').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="สรุปลูกค้า", page="customer")

@app.route('/monthly_summary')
def monthly_summary():
    if 'admin' not in session:
        return redirect(url_for('login'))
    
    content = """
    <div class="card p-4 shadow-sm">
        <h4 class="mb-3">สรุปยอดผลประกอบการรายเดือน</h4>
        <table class="table table-bordered">
            <thead class="table-dark"><tr><th>ประจำเดือน (Year-Month)</th><th>จำนวนรายการ</th><th>ทุนที่ใช้เดือนนี้ (บาท)</th><th>กำไรเดือนนี้ (บาท)</th><th>ยอดรอเก็บรวม (บาท)</th></tr></thead>
            <tbody><tr><td colspan="5" class="text-center text-muted">ยังไม่มีข้อมูลสรุปยอดรายเดือน</td></tr></tbody>
        </table>
    </div>
    """
    html = BASE_LAYOUT.replace('{% block header %}4. สรุปยอดรายเดือน{% endblock %}', 'สรุปยอดรายเดือน').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="สรุปยอดรายเดือน", page="monthly")

@app.route('/login', methods=['GET', 'POST'])
def login():
    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        
        if username in VALID_USERS and VALID_USERS[username] == password:
            session['admin'] = username
            return redirect(url_for('index'))
        else:
            error = 'ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง!'
            
    login_html = """
    <!DOCTYPE html>
    <html lang="th">
    <head>
        <meta charset="UTF-8">
        <title>เข้าสู่ระบบ - ทองล้น</title>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        <link href="https://fonts.googleapis.com/css2?family=Prompt:wght@300;400;500;600&display=swap" rel="stylesheet">
        <style>body { font-family: 'Prompt', sans-serif; background-color: #f8f9fa; }</style>
    </head>
    <body class="d-flex align-items-center justify-content-center vh-100">
        <div class="card p-4 shadow" style="width: 380px;">
            <h3 class="text-center mb-4 text-warning fw-bold">🪙 ทองล้น</h3>
            {% if error %}<div class="alert alert-danger py-2 text-center">{{ error }}</div>{% endif %}
            <form method="POST">
                <div class="mb-3"><label class="form-label">ชื่อผู้ใช้งาน:</label><input type="text" name="username" class="form-control" required></div>
                <div class="mb-3"><label class="form-label">รหัสผ่าน:</label><input type="password" name="password" class="form-control" required></div>
                <button type="submit" class="btn btn-warning w-100 fw-bold">เข้าสู่ระบบ</button>
            </form>
        </div>
    </body>
    </html>
    """
    return render_template_string(login_html, error=error)

@app.route('/logout')
def logout():
    session.pop('admin', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    app.run(debug=True)
