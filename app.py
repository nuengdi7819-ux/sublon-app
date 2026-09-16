@app.route('/summary_breakdown/<breakdown_type>')
def summary_breakdown(breakdown_type):
    if 'admin' not in session: return redirect(url_for('login'))
    
    all_txs_ever = Transaction.query.all()
    for tx in all_txs_ever: calculate_tx_values(tx)
    
    title_text = ""
    rows = ""
    table_headers = ""
    
    if breakdown_type == 'new_investment':
        title_text = "🔱 รายละเอียดที่มา: เงินลงทุนใหม่ทั้งหมด (เงินฉุกเฉิน และ ผ่อนทอง)"
        txs = [tx for tx in all_txs_ever if tx.type != 'ยอดค้างเก่า']
        rows = "".join([f"<tr><td><a href='/customer_details/{tx.customer_name}' class='text-dark fw-bold text-decoration-none'>{tx.customer_name}</a></td><td>{tx.phone or '-'}</td><td><span class='badge bg-secondary'>{tx.type}</span></td><td>{tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'}</td><td><b>{tx.original_principal:,.2f}</b></td><td>{tx.principal:,.2f}</td><td><span class='badge {'bg-success' if tx.principal>0 else 'bg-danger'}'>{tx.status}</span></td><td class='text-center'><a href='/delete_tx/{tx.id}' class='btn btn-sm btn-danger' onclick=\"return confirm('ยืนยันการลบบัญชีนี้? (ยอดลงทุนจะถูกตัดออกจากระบบ)')\">❌ ลบรายการ</a></td></tr>" for tx in txs])
        table_headers = "<th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>ประเภท</th><th>วันที่เริ่ม</th><th>เงินลงทุนตั้งต้น</th><th>ต้นคงค้าง</th><th>สถานะ</th><th class='text-center'>จัดการ</th>"
        
    elif breakdown_type == 'debt_remaining':
        title_text = "📂 รายละเอียดที่มา: ยอดค้างเก่าคงเหลือ"
        txs = [tx for tx in all_txs_ever if tx.type == 'ยอดค้างเก่า' and tx.principal > 0]
        rows = "".join([f"<tr><td><a href='/customer_details/{tx.customer_name}' class='text-dark fw-bold text-decoration-none'>{tx.customer_name}</a></td><td>{tx.phone or '-'}</td><td>{tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'}</td><td>{tx.original_principal:,.2f}</td><td><b class='text-warning'>{tx.principal:,.2f}</b></td><td><strong class='text-primary'>{(tx.original_principal - tx.principal):,.2f}</strong></td><td class='text-center'><a href='/delete_tx/{tx.id}' class='btn btn-sm btn-danger' onclick=\"return confirm('ยืนยันการลบบัญชีนี้?')\">❌ ลบรายการ</a></td></tr>" for tx in txs])
        table_headers = "<th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>วันที่เริ่ม</th><th>ยอดค้างตั้งต้น</th><th>ยอดค้างคงเหลือ</th><th>ชำระลดแล้ว</th><th class='text-center'>จัดการ</th>"
        
    elif breakdown_type == 'new_remaining':
        title_text = "💼 รายละเอียดที่มา: เงินต้นคงค้าง (เฉพาะบัญชีใหม่ที่ยังไม่ปิด)"
        txs = [tx for tx in all_txs_ever if tx.type != 'ยอดค้างเก่า' and tx.principal > 0]
        rows = "".join([f"<tr><td><a href='/customer_details/{tx.customer_name}' class='text-dark fw-bold text-decoration-none'>{tx.customer_name}</a></td><td>{tx.phone or '-'}</td><td><span class='badge bg-secondary'>{tx.type}</span></td><td>{tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'}</td><td>{tx.original_principal:,.2f}</td><td><b class='text-danger'>{tx.principal:,.2f}</b></td><td><span class='badge bg-success'>{tx.status}</span></td><td class='text-center'><a href='/delete_tx/{tx.id}' class='btn btn-sm btn-danger' onclick=\"return confirm('ยืนยันการลบบัญชีนี้?')\">❌ ลบรายการ</a></td></tr>" for tx in txs])
        table_headers = "<th>ชื่อลูกค้า</th><th>เบอร์โทร</th><th>ประเภท</th><th>วันที่เริ่ม</th><th>เงินลงทุน</th><th>ต้นคงค้าง</th><th>สถานะ</th><th class='text-center'>จัดการ</th>"
        
    elif breakdown_type == 'profit_breakdown':
        title_text = "💰 รายละเอียดที่มา: กำไรสะสมทั้งหมด (คลิกตรวจสอบประวัติการตัดยอดได้)"
        
        histories = PaymentHistory.query.order_by(PaymentHistory.payment_date.desc(), PaymentHistory.id.desc()).all()
        for h in histories:
            if not h.transaction:
                continue  # ข้ามรายการที่ผูกกับบัญชีที่ถูกลบไปแล้ว เพื่อป้องกัน Error 500
            
            new_val = h.interest_paid if h.transaction.type != 'ยอดค้างเก่า' else 0.0
            debt_val = h.interest_paid if h.transaction.type == 'ยอดค้างเก่า' else 0.0
            fine_val = h.fine_amount
            
            rows += f"""
            <tr>
                <td>{h.payment_date.strftime('%d/%m/%Y')}</td>
                <td><a href='/customer_details/{h.transaction.customer_name}' class='text-dark fw-bold text-decoration-none'>{h.transaction.customer_name}</a></td>
                <td><span class='badge bg-secondary'>{h.transaction.type}</span></td>
                <td class='text-success'><b>{new_val:,.2f}</b></td>
                <td class='text-primary'><b>{debt_val:,.2f}</b></td>
                <td class='text-warning text-dark'><b>{fine_val:,.2f}</b></td>
                <td>{h.note or 'รับชำระปกติ'}</td>
                <td><span class='badge bg-secondary'>{h.admin_name or '-'}</span></td>
                <td class='text-center'>
                    <a href='/history/{h.transaction_id}' class='btn btn-sm btn-outline-primary fw-bold' target='_blank'>🔍 เช็กบิล</a>
                    <a href='/delete_history/{h.id}' class='btn btn-sm btn-danger' onclick="return confirm('ยืนยันการลบประวัติรายการนี้? (ระบบจะคืนยอดเงินต้นและดอกเบี้ยกลับให้อัตโนมัติ)')">❌ ลบ</a>
                </td>
            </tr>
            """

        for tx in all_txs_ever:
            if tx.type == 'ยอดค้างเก่า':
                debt_profit = tx.original_principal - tx.principal
                if debt_profit != 0:
                    rows += f"""
                    <tr>
                        <td>{tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'}</td>
                        <td><a href='/customer_details/{tx.customer_name}' class='text-dark fw-bold text-decoration-none'>{tx.customer_name}</a></td>
                        <td><span class='badge bg-warning text-dark'>ยอดค้างเก่า (ส่วนต่างรวม)</span></td>
                        <td class='text-success'><b>0.00</b></td>
                        <td class='text-primary'><b>{debt_profit:,.2f}</b></td>
                        <td class='text-warning text-dark'><b>0.00</b></td>
                        <td>กำไรส่วนต่างยอดค้างเก่า (ตั้งต้น - คงเหลือ) [สถานะ: {tx.status}]</td>
                        <td><span class='badge bg-secondary'>{tx.sales_name}</span></td>
                        <td class='text-center'>
                            <a href='/customer_details/{tx.customer_name}' class='btn btn-sm btn-outline-dark fw-bold' target='_blank'>🔍 เช็กบัญชี</a>
                        </td>
                    </tr>
                    """

        table_headers = "<th>วันที่ทำรายการ</th><th>ชื่อลูกค้า</th><th>ประเภท</th><th>ยอดใหม่ (ดอกเบี้ย)</th><th>ยอดค้าง (ส่วนต่างเก่า)</th><th>ยอดปรับ (ค่าปรับ)</th><th>หมายเหตุ</th><th>ผู้บันทึก</th><th class='text-center'>ตรวจสอบ / จัดการ</th>"
    else:
        return redirect(url_for('index'))

    content = f"""
    <div class="card p-4 shadow-sm border-warning">
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <h4 class="mb-0 fs-5 text-danger fw-bold">{title_text}</h4>
            <a href="/" class="btn btn-sm btn-secondary fw-bold">⬅️ กลับหน้าหลัก</a>
        </div>
        <div class="table-responsive">
            <table class="table table-striped align-middle text-nowrap">
                <thead class="table-dark">
                    <tr>{table_headers}</tr>
                </thead>
                <tbody>{rows if rows else "<tr><td colspan='9' class='text-center text-muted'>ไม่พบข้อมูลรายการ</td></tr>"}</tbody>
            </table>
        </div>
    </div>
    """
    html = BASE_LAYOUT.replace('{% block header %}รายละเอียดที่มา{% endblock %}', 'รายละเอียดที่มาของยอด').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title="รายละเอียดที่มา", page="dashboard")
