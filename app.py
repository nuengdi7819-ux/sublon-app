@app.route('/monthly_details/<ym>')
def monthly_details(ym):
    if 'admin' not in session: return redirect(url_for('login'))
    
    try:
        year_val, month_val = ym.split('-')
        year_i, month_i = int(year_val), int(month_val)
    except:
        return redirect(url_for('monthly_summary'))

    # ดึง ID ของรายการที่มีการจ่ายเงินจริงในเดือนนั้นๆ อย่างถูกต้อง
    tx_ids_from_history = [h.transaction_id for h in PaymentHistory.query.all() if h.payment_date and h.payment_date.strftime('%Y-%m') == ym]

    txs = Transaction.query.filter(
        db.or_(
            db.and_(db.extract('year', Transaction.start_date) == year_i, db.extract('month', Transaction.start_date) == month_i),
            Transaction.id.in_(tx_ids_from_history) if tx_ids_from_history else False
        )
    ).order_by(Transaction.start_date.desc()).all()

    rows = ""
    for tx in txs:
        calculate_tx_values(tx)
        badge_color = 'bg-success' if tx.principal <= 0 else ('bg-info text-dark' if tx.status == 'ตัดยอดบางส่วน' else 'bg-success')
        if tx.principal <= 0 or tx.status == 'คืนแล้ว': badge_color = 'bg-danger'

        start_date_str = tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'
        last_pay_str = tx.last_payment_date.strftime('%d/%m/%Y') if tx.last_payment_date else '-'
        
        rows += f"""
        <tr>
            <td style="font-weight: 500;">
                <a href="/customer_details/{tx.customer_name}" class="text-dark text-decoration-none fw-bold">{tx.customer_name}</a>
            </td>
            <td>{tx.phone or '-'}</td>
            <td><span class="badge bg-secondary">{tx.type}</span></td>
            <td>{start_date_str}</td>
            <td>{last_pay_str}</td>
            <td>{tx.original_principal:,.2f}</td>
            <td>{tx.principal:,.2f}</td>
            <td><strong class="text-primary">{tx.total_paid:,.2f}</strong></td>
            <td>{tx.daily_interest:,.2f}</td>
            <td><span class="badge {badge_color}">{'คืนแล้ว' if tx.principal <= 0 else tx.status}</span></td>
            <td class="text-center">
                <a href="/" class="btn btn-sm btn-lime fw-bold">อัพเดทยอด</a>
            </td>
        </tr>
        """

    content = f"""
    <div class="card p-4 shadow-sm border-warning">
        <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
            <h4 class="mb-0 fs-5 text-danger fw-bold">📋 รายการลูกค้าประจำเดือน: {ym}</h4>
            <a href="/monthly_summary" class="btn btn-sm btn-secondary fw-bold">⬅️ กลับไปหน้าสรุปรายเดือน</a>
        </div>
        <div class="table-responsive">
            <table class="table table-striped align-middle text-nowrap">
                <thead class="table-dark">
                    <tr>
                        <th>ชื่อลูกค้า</th>
                        <th>เบอร์โทร</th>
                        <th>ประเภท</th>
                        <th>วันที่กู้</th>
                        <th>ชำระล่าสุด</th>
                        <th>เงินลงทุน</th>
                        <th>ต้นคงค้าง</th>
                        <th>ชำระแล้ว</th>
                        <th>ดอก/วัน</th>
                        <th>สถานะ</th>
                        <th class="text-center">จัดการ</th>
                    </tr>
                </thead>
                <tbody>{rows if rows else "<tr><td colspan='11' class='text-center text-muted'>ไม่มีรายการลูกค้าในเดือนนี้</td></tr>"}</tbody>
            </table>
        </div>
    </div>
    """
    html = BASE_LAYOUT.replace('{% block header %}รายละเอียดประจำเดือน {ym}{% endblock %}', f'รายละเอียดประจำเดือน {ym}').replace('{% block content %}{% endblock %}', content)
    return render_template_string(html, title=f"รายละเอียด {ym}", page="monthly")
