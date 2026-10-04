<script>
    function toggleSidebar() {
        const sidebar = document.getElementById('sidebarMenu');
        const backdrop = document.getElementById('sidebarBackdrop');
        if (sidebar && backdrop) {
            sidebar.classList.toggle('show');
            backdrop.classList.toggle('show');
        }
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
        let typeSelect = document.getElementById('txTypeSelect');
        let instDiv = document.getElementById('installmentDiv');
        if (typeSelect && instDiv) {
            if (typeSelect.value === 'ยอดค้างเก่า') { 
                instDiv.style.display = 'block'; 
            } else { 
                instDiv.style.display = 'none'; 
            }
        }
    }

    function handleScheduleChange() {
        let scheduleSelect = document.getElementById('scheduleTypeSelect');
        let dayDiv = document.getElementById('dueDayDiv');
        if (scheduleSelect && dayDiv) {
            // ถ้าเลือก "กำหนดจ่ายประจำเดือน" ให้แสดงช่องเลือกวันทันที แบบ block เต็มแถว
            if (scheduleSelect.value === 'กำหนดจ่ายประจำเดือน') { 
                dayDiv.style.display = 'block'; 
            } else { 
                dayDiv.style.display = 'none'; 
            }
        }
    }

    function handleLockInterestCheck() {
        let chk = document.getElementById('isLockedInterestAdd');
        let box = document.getElementById('lockedInterestBoxAdd');
        if (chk && box) {
            box.style.display = chk.checked ? 'block' : 'none';
        }
    }

    function handleModalLockInterestChange(txId) {
        let chk = document.getElementById('is_locked_interest' + txId);
        let box = document.getElementById('lockedInterestBox' + txId);
        if (chk && box) {
            box.style.display = chk.checked ? 'block' : 'none';
        }
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

    // รันการตรวจสอบทันทีเมื่อเปิดหน้าเว็บ
    document.addEventListener("DOMContentLoaded", function() {
        handleScheduleChange();
        handleTypeChange();
        
        let scheduleSelect = document.getElementById('scheduleTypeSelect');
        if (scheduleSelect) {
            scheduleSelect.addEventListener('change', handleScheduleChange);
        }
    });
    </script>
