document.addEventListener("DOMContentLoaded", () => {
    const cartItemList = document.getElementById("cart-item-list");
    const totalPriceEl = document.getElementById("total-price");
    const btnBuySelected = document.getElementById("btn-buy-selected");
    const chkAll = document.getElementById("chk-all");
    const btnDeleteSelected = document.getElementById("btn-delete-selected");

    // localStorage에서 기존 장바구니 목록 꺼내기
    let cart = JSON.parse(localStorage.getItem("cart")) || [];

    // 1. 장바구니 화면 그리기 (렌더링)
    const renderCart = () => {
        cartItemList.innerHTML = "";

        if (cart.length === 0) {
            cartItemList.innerHTML = `<li class="cart-empty">장바구니가 비어 있습니다.</li>`;
            totalPriceEl.textContent = "0";
            chkAll.checked = false;
            return;
        }

        cart.forEach((item, index) => {
            const li = document.createElement("li");
            li.className = "cart-item";
            
            // 이미지 주소 결측치 기본 핸들링
            const imgUrl = item.image_url || 'images/sample_image.jpg';

            li.innerHTML = `
                <input type="checkbox" class="cart-checkbox" data-index="${index}" checked>
                <div class="cart-item-img">
                    <img src="${imgUrl}" alt="${item.prod_name}" onerror="this.src='https://via.placeholder.com/100?text=No+Image'">
                </div>
                <div class="cart-item-info">
                    <p class="cart-item-name">${item.prod_name}</p>
                    <p class="cart-item-price">${parseInt(item.price).toLocaleString()}원</p>
                </div>
                <button class="btn-item-delete" data-index="${index}">삭제</button>
            `;
            cartItemList.appendChild(li);
        });

        calculateTotal();
        setupItemEvents();
        updateSelectAllCheckboxState();
    };

    // 2. 체크된 상품 금액 합산 계산
    const calculateTotal = () => {
        let total = 0;
        const checkboxes = document.querySelectorAll(".cart-checkbox:checked");
        checkboxes.forEach((cb) => {
            const index = parseInt(cb.dataset.index, 10);
            const item = cart[index];
            if (item) {
                total += parseInt(item.price, 10) * (item.quantity || 1);
            }
        });
        totalPriceEl.textContent = total.toLocaleString();
    };

    // 3. 개별 아이템 내부 이벤트 바인딩 (체크박스 토글 / 단일 삭제)
    const setupItemEvents = () => {
        // 체크 박스 클릭 시 총액 다시 계산
        const checkboxes = document.querySelectorAll(".cart-checkbox");
        checkboxes.forEach((cb) => {
            cb.addEventListener("change", () => {
                calculateTotal();
                updateSelectAllCheckboxState();
            });
        });

        // 우측 개별 삭제 버튼 이벤트
        const deleteButtons = document.querySelectorAll(".btn-item-delete");
        deleteButtons.forEach((btn) => {
            btn.addEventListener("click", (e) => {
                const index = parseInt(e.target.dataset.index, 10);
                cart.splice(index, 1); // 해당 인덱스 데이터 삭제
                localStorage.setItem("cart", JSON.stringify(cart));
                renderCart(); // 리렌더링
            });
        });
    };

    // 4. 개별 체크박스 상태에 따라 상단 '전체 선택' 체크박스 동기화
    const updateSelectAllCheckboxState = () => {
        const checkboxes = document.querySelectorAll(".cart-checkbox");
        if (checkboxes.length === 0) {
            chkAll.checked = false;
            return;
        }
        const checkedBoxes = document.querySelectorAll(".cart-checkbox:checked");
        chkAll.checked = (checkboxes.length === checkedBoxes.length);
    };

    // 5. 상단 '전체 선택' 클릭 제어
    chkAll.addEventListener("change", (e) => {
        const isChecked = e.target.checked;
        const checkboxes = document.querySelectorAll(".cart-checkbox");
        checkboxes.forEach((cb) => {
            cb.checked = isChecked;
        });
        calculateTotal();
    });

    // 6. 상단 '선택 삭제' 버튼 클릭 제어
    btnDeleteSelected.addEventListener("click", () => {
        const checkboxes = document.querySelectorAll(".cart-checkbox");
        // 인덱스 꼬임 방지를 위해 역순으로 순회하며 삭제
        for (let i = checkboxes.length - 1; i >= 0; i--) {
            if (checkboxes[i].checked) {
                cart.splice(i, 1);
            }
        }
        localStorage.setItem("cart", JSON.stringify(cart));
        renderCart();
    });

    // 7. 하단 '구매하기' 버튼 클릭 시 로그 적재 및 주문 처리
    btnBuySelected.addEventListener("click", () => {
        const checkedBoxes = document.querySelectorAll(".cart-checkbox:checked");
        if (checkedBoxes.length === 0) {
            alert("구매할 상품을 선택해 주세요.");
            return;
        }

        const itemsToBuy = Array.from(checkedBoxes).map(cb => cart[parseInt(cb.dataset.index, 10)]);
        
        // 백엔드 파이프라인 연동: api.js의 로그 수집 API 호출 (purchase 이벤트 전송)
        if (typeof sendLog === "function") {
            itemsToBuy.forEach(item => {
                sendLog({
                    session_id: localStorage.getItem("session_id") || "test_session_123",
                    user_id: localStorage.getItem("user_id") || "test_user_456",
                    article_id: item.article_id,
                    event_type: "purchase",
                    timestamp: new Date().toISOString()
                });
            });
        }

        alert(`${itemsToBuy.length}개의 상품 구매가 완료되었습니다.\n실시간 파이프라인으로 purchase 로그가 정상 전송되었습니다.`);
        
        // 구매 완료된 아이템만 장바구니 리스트에서 차감 제거
        cart = cart.filter((_, index) => {
            const cb = document.querySelector(`.cart-checkbox[data-index="${index}"]`);
            return cb ? !cb.checked : true;
        });
        localStorage.setItem("cart", JSON.stringify(cart));
        renderCart();
    });

    // 첫 진입 시 실행
    renderCart();
});