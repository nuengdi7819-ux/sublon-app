# ปรับการคำนวณกำไรสะสมบนหน้า Dashboard (เดือนปัจจุบัน) ให้ยึดตาม payment_date ใน PaymentHistory เช่นเดียวกับหน้าแฟ้มรายเดือน
        profit_items = []
        current_month_profit = 0.0
        all_histories = PaymentHistory.query.all()
        
        tx_histories_map = defaultdict(list)
        for h in all_histories:
            if h.transaction_id:
                tx_histories_map[h.transaction_id].append(h)

        for tx in all_txs_ever:
            hist_list = tx_histories_map.get(tx.id, [])
            
            item_current_month_profit = 0.0
            total_net_earned = 0.0
            total_fine_sum = 0.0
            total_discount_sum = 0.0
            latest_h_date = tx.start_date

            if hist_list:
                for h in hist_list:
                    h_profit = h.interest_paid + h.fine_amount - h.discount_amount
                    total_net_earned += h.interest_paid
                    total_fine_sum += h.fine_amount
                    total_discount_sum += h.discount_amount
                    
                    if h.payment_date:
                        if not latest_h_date or h.payment_date > latest_h_date:
                            latest_h_date = h.payment_date
                        # เช็กเฉพาะรายการที่ชำระในเดือนและปีปัจจุบัน
                        if h.payment_date.year == current_year and h.payment_date.month == current_month:
                            current_month_profit += h_profit
                            item_current_month_profit += h_profit
            else:
                if tx.type == 'ยอดค้างเก่า':
                    net_earned = max(0.0, (tx.original_principal - tx.principal))
                else:
                    net_earned = max(tx.paid_interest, 0.0)
                total_net_earned = net_earned
                total_item_profit = net_earned
                if latest_h_date and latest_h_date.year == current_year and latest_h_date.month == current_month:
                    current_month_profit += total_item_profit
                    item_current_month_profit = total_item_profit

            total_item_profit = total_net_earned + total_fine_sum - total_discount_sum
            if total_item_profit != 0 or total_net_earned > 0 or total_fine_sum > 0 or total_discount_sum > 0:
                profit_items.append({
                    'customer_name': tx.customer_name,
                    'type': tx.type,
                    'net_earned': total_net_earned,
                    'fine_amount': total_fine_sum,
                    'discount_amount': total_discount_sum,
                    'total_item_profit': total_item_profit,
                    'latest_date': latest_h_date
                })

        profit_items.sort(key=lambda x: x['latest_date'] if x['latest_date'] else thai_today, reverse=True)
