@app.route('/customer_details/<path:cust_name>')
def customer_details(cust_name):
    if 'admin' not in session: return redirect(url_for('login'))
    clean_name = cust_name.strip()
    try:
        with db.session.no_autoflush:
            txs = Transaction.query.filter(db.func.lower(Transaction.customer_name) == clean_name.lower()).order_by(Transaction.start_date.desc()).all()
            if not txs:
                txs = Transaction.query.filter(Transaction.customer_name.ilike(f"%{clean_name}%")).order_by(Transaction.start_date.desc()).all()

            for tx in txs: calculate_tx_values(tx)

        rows, modals_html = "", ""
        for tx in txs:
            badge_color = 'bg-success' if tx.principal <= 0 else ('bg-info text-dark' if tx.status == 'ตัดยอดบางส่วน' else 'bg-success')
            if tx.principal <= 0 or tx.status == 'คืนแล้ว': badge_color = 'bg-danger'
            start_date_str = tx.start_date.strftime('%d/%m/%Y') if tx.start_date else '-'
            last_pay_str = tx.last_payment_date.strftime('%d/%m/%Y') if tx.last_payment_date else '-'
            closed_date_str = tx.closed_date.strftime('%Y-%m-%d') if tx.closed_date else ''

            base_bill_amt = tx.principal + tx.accumulated_interest
            checkbox_elem = f'<input class="form-check-input bill-checkbox" type="checkbox" value="{tx.id}" data-amount="{base_bill_amt}" data-daily-int="{tx.daily_interest}" data-type="{tx.type}" onchange="updateSelectedBillsCalc()" checked>' if tx.principal > 0 else '<span class="text-muted small">ปิดแล้ว</span>'

            id_display = f'<span class="badge bg-dark text-warning border border-warning" style="font-size: 0.8rem;">{tx.id}</span>'

            rows += f"""
            <tr>
                <td class="text-center">{checkbox_elem}</td>
                <td>{id_display}</td>
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
                    <div class="d-flex justify-content-center gap-1 flex-nowrap" style="min-width: 180px;">
                        <button type="button" class="btn btn-sm btn-success-light fw-bold py-1 px-2" style="font-size: 0.8rem;" data-bs-toggle="modal" data-bs-target="#payModal{tx.id}">จัดการยอด</button>
                        <button type="button" class="btn btn-sm btn-outline-warning text-dark fw-bold py-1 px-2" style="font-size: 0.8rem; background-color: #ffc107;" data-bs-toggle="modal" data-bs-target="#billModal{tx.id}">ออกบิล</button>
                        <a href="/delete_tx/{tx.id}" class="btn btn-sm btn-danger fw-bold py-1 px-2" style="font-size: 0.8rem;" onclick="return confirm('ยืนยันการลบบิลนี้?')">ลบ</a>
                    </div>
                </td>
            </tr>
            """

            modals_html += f"""
            <div class="modal fade" id="payModal{tx.id}" tabindex="-1">
                <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
                    <div class="modal-content border-warning">
                        <form action="/update_payment/{tx.id}" method="POST">
                            <div class="modal-header bg-danger text-white py-2">
                                <h5 class="modal-title fs-6">จัดการยอด: {tx.customer_name} (ID: {tx.id})</h5>
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
                                            <option value="adjust">ปรับปรุงยอด (เพิ่ม/ลดต้นโดยไม่อ้างอิงเงินสด)</option>
                                        </select>
                                    </div>
                                    <div class="mb-1" id="amountDiv{tx.id}">
                                        <label class="form-label fw-bold text-primary mb-1" style="font-size: 0.85rem;">💵 จำนวนเงินที่รับชำระจริง (บาท)</label>
                                        <input type="number" step="any" name="pay_amount" class="form-control form-control-sm border-primary shadow-sm bg-white" placeholder="กรอกจำนวนเงินสดที่รับจริง">
                                    </div>
                                    <div class="mb-1" id="adjustContainer{tx.id}" style="display: none;">
                                        <label class="form-label fw-bold text-dark mb-1" style="font-size: 0.85rem;">⚙ จำนวนเงินปรับปรุงต้น (บาท)</label>
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

            modals_html += f"""
            <div class="modal fade" id="billModal{tx.id}" tabindex="-1">
                <div class="modal-dialog modal-dialog-centered modal-dialog-scrollable">
                    <div class="modal-content border-success shadow-lg">
                        <div class="modal-header bg-success text-white py-2">
                            <h5 class="modal-title fw-bold fs-6">ใบแจ้งยอดชำระ</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body bg-light p-2">
                            <div class="text-center mb-1">
                                <h6 class="text-danger fw-bold mb-0" id="billTitleDisplay{tx.id}">📄 ใบแจ้งยอดชำระ - ทรัพย์ล้น.com</h6>
                                <span class="text-muted" style="font-size: 0.75rem;">👤 <b>{tx.customer_name}</b> | <span class="badge bg-secondary">{tx.type}</span></span>
                            </div>

                            <div class="p-3 mb-2 border border-success rounded bg-white text-center shadow-sm">
                                <span class="text-muted d-block mb-1" style="font-size: 0.8rem;">ยอดรวมสุทธิที่ต้องชำระ</span>
                                <h3 class="text-success fw-bold mb-0" id="billTotalDisplay{tx.id}">{base_bill_amt:,.2f} บาท</h3>
                            </div>

                            <div class="p-2 rounded border border-success bg-white text-center shadow-sm mb-2">
                                <div class="bg-light p-1 d-inline-block rounded border mb-1">
                                    <img src="https://raw.githubusercontent.com/nuengdi7819-ux/sublon-app/main/GSB.jpg" alt="QR Code พร้อมเพย์" style="width: 130px; height: 130px; object-fit: contain;">
                                </div>
                                <div class="text-secondary small" style="font-size: 0.72rem; line-height: 1.3;">
                                    🟡 <b>กรุงศรี:</b> 803-931-9819 | 🩷 <b>ออมสิน:</b> 020-409-437-819<br>
                                    <span class="text-muted">* โอนแล้วส่งสลิปทางแชทนี้ได้เลยครับ ขอบคุณครับ 🙏</span>
                                </div>
                            </div>
                        </div>
                        <div class="modal-footer bg-white py-1 justify-content-between">
                            <button type="button" class="btn btn-secondary btn-sm" data-bs-dismiss="modal">ปิด</button>
                        </div>
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
                <div>
                    <a href="/dashboard" class="btn btn-sm btn-secondary fw-bold">⬅ กลับหน้าหลัก</a>
                </div>
            </div>
            <div class="table-responsive">
                <table class="table table-striped align-middle text-nowrap">
                    <thead class="table-dark">
                        <tr><th class="text-center" style="width: 50px;">เลือก</th><th>ID</th><th>ประเภทบัญชี</th><th>บัญชีปล่อยกู้</th><th>วันที่กู้</th><th>ชำระล่าสุด</th><th>เงินลงทุน</th><th>ต้นคงค้าง</th><th>ชำระแล้ว</th><th>ดอก/วัน</th><th>ดอกเบี้ยสะสม</th><th>สถานะ</th><th class="text-center">จัดการ</th></tr>
                    </thead>
                    <tbody>{rows if rows else "<tr><td colspan='13' class='text-center text-muted'>ไม่พบข้อมูลรายการของลูกค้ารายนี้</td></tr>"}</tbody>
                </table>
            </div>
        </div>
        {modals_html}
        """
        html = BASE_LAYOUT.replace('{% block header %}รายละเอียดลูกค้า {cust_name}{% endblock %}', f'รายละเอียดลูกค้า {cust_name}').replace('{% block content %}{% endblock %}', content)
        return render_template_string(html, title=f"ลูกค้า: {cust_name}", page="dashboard")
    finally:
        db.session.remove()
