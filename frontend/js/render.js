const SESSION_ID = sessionStorage.getItem("session_id") || (() => {
    const id = crypto.randomUUID();
    sessionStorage.setItem("session_id", id);
    return id;
})();

const USER_ID = new URLSearchParams(window.location.search).get("user_id") || "ea8715ba-355e-4410-91de-a95038cb4c5e";

function getRandomPriceData() {
    const min = 20000;
    const max = 150000;
    const price = Math.floor(Math.random() * (max - min + 1)) + min;
    const isDiscounted = Math.random() > 0.3;
    const discountRate = isDiscounted ? Math.floor(Math.random() * 50) + 10 : 0;
    return {
        price: price.toLocaleString() + "원",
        discount: discountRate > 0 ? `${discountRate}%` : ""
    };
}

function createProductCard(product) {
    const card = document.createElement("div");
    card.className = "product-card";

    const priceData = getRandomPriceData();
    const mockBrands = ["가까이 유니언즈", "미쏘", "레더리", "바운더리", "다미쉬", "아디다스"];
    const brandName = mockBrands[Math.floor(Math.random() * mockBrands.length)];

    const articleId = String(product.article_id).padStart(10, '0');
    const imageUrl = product.image_url || `images/products/${articleId}.jpg`;

    card.innerHTML = `
        <div class="product-img-box">
            <img src="${imageUrl}"
                 onerror="this.src='images/mainpage_banner.png'"
                 alt="${product.prod_name}">
        </div>
        <div class="brand-name">${brandName}</div>
        <div class="product-name">${product.prod_name}</div>
        <div class="price-box">
            ${priceData.discount ? `<span class="discount">${priceData.discount}</span>` : ""}
            <span class="price">${priceData.price}</span>
        </div>
    `;

    card.onclick = () => {
        sendLog({
            user_id:    USER_ID,
            session_id: SESSION_ID,
            event_type: "click",
            article_id: product.article_id,
            timestamp:  new Date().toISOString()
        });
        window.location.href = `detail.html?id=${product.article_id}`;
    };

    return card;
}

async function loadInitialProducts() {
    const pRecsContainer = document.getElementById("personalized-recs");
    const gRecsContainer = document.getElementById("general-recs");

    if (!pRecsContainer || !gRecsContainer) return;

    pRecsContainer.innerHTML = "";
    gRecsContainer.innerHTML = "";

    const mainData = await fetchMainRecommendations(USER_ID);
    const articleIds = mainData.data || mainData.recommendations || [];

    if (articleIds.length > 0) {
        for (const articleId of articleIds.slice(0, 10)) {
            try {
                const res = await fetch(`http://localhost:8000/api/articles/${articleId}`);
                const product = await res.json();
                pRecsContainer.appendChild(createProductCard(product));
            } catch (e) {
                console.error(e);
            }
        }
        sendLog({
            user_id:    USER_ID,
            session_id: SESSION_ID,
            event_type: "impression",
            article_id: articleIds.slice(0, 10).join(","),
            timestamp:  new Date().toISOString()
        });
    }

    const generalIds = ["929866001", "767869001", "782758003", "880018003", "786307003",
                        "717759001", "715981002", "824764007", "882925001", "697980002"];
    for (const articleId of generalIds) {
        try {
            const res = await fetch(`http://localhost:8000/api/articles/${articleId}`);
            const product = await res.json();
            gRecsContainer.appendChild(createProductCard(product));
        } catch (e) {
            console.error(e);
        }
    }
}

function setupInfiniteScroll() {
    const anchor = document.getElementById("scroll-anchor");
    if (!anchor) return;

    const observer = new IntersectionObserver((entries) => {
        if (entries[0].isIntersecting) {
            loadMoreProducts();
        }
    });
    observer.observe(anchor);
}

function loadMoreProducts() {
    const gRecsContainer = document.getElementById("general-recs");
    if (!gRecsContainer) return;

    const moreProducts = Array.from({ length: 10 }, (_, i) => ({
        article_id: `more_${Date.now()}_${i}`,
        prod_name: `[추가 추천] 스크롤 추천 상품 ${i + 1}`
    }));
    moreProducts.forEach(prod => {
        gRecsContainer.appendChild(createProductCard(prod));
    });
}

async function loadDetailInfo() {
    const params = new URLSearchParams(window.location.search);
    const articleId = params.get("id");

    if (!articleId) return;

    const enter_time = Date.now();
    window.addEventListener("beforeunload", () => {
        const dwell_time = Date.now() - enter_time;
        if (dwell_time < 3000) return;
        sendLog({
            user_id:    USER_ID,
            session_id: SESSION_ID,
            event_type: "dwell",
            article_id: articleId,
            dwell_time: dwell_time,
            timestamp:  new Date().toISOString()
        });
    });

    try {
        const res = await fetch(`http://localhost:8000/api/articles/${articleId}`);
        const product = await res.json();

        if (document.getElementById("detail-image")) {
            const aid = String(articleId).padStart(10, '0');
            document.getElementById("detail-image").src = product.image_url || `images/products/${aid}.jpg`;
            document.getElementById("detail-image").onerror = function() {
                this.src = "images/mainpage_banner.png";
            };
            document.getElementById("detail-title").textContent      = product.prod_name || "";
            document.getElementById("detail-price").textContent      = `₩${(Math.floor(Math.random() * 130000) + 20000).toLocaleString()}`;
            document.getElementById("detail-desc").textContent       = product.detail_desc || "";
            document.getElementById("detail-type").textContent       = product.product_type_name || "";
            document.getElementById("detail-appearance").textContent = product.graphical_appearance_name || "";
            document.getElementById("detail-color").textContent      = product.colour_group_name || "";
        }

        sendLog({
            user_id:    USER_ID,
            session_id: SESSION_ID,
            event_type: "click",
            article_id: articleId,
            timestamp:  new Date().toISOString()
        });

        const addCartBtn = document.getElementById("add-to-cart-btn");
        if (addCartBtn) {
            addCartBtn.addEventListener("click", () => {
                let cart = JSON.parse(localStorage.getItem("cart")) || [];

                const existingIndex = cart.findIndex(item => item.article_id === articleId);

                if (existingIndex > -1) {
                    cart[existingIndex].quantity = (cart[existingIndex].quantity || 1) + 1;
                } else {
                    cart.push({
                        article_id: articleId,
                        prod_name:  product.prod_name,
                        price:      Math.floor(Math.random() * 130000) + 20000,
                        image_url:  product.image_url || "",
                        quantity:   1
                    });
                }

                localStorage.setItem("cart", JSON.stringify(cart));

                sendLog({
                    user_id:    USER_ID,
                    session_id: SESSION_ID,
                    event_type: "add_to_cart",
                    article_id: articleId,
                    timestamp:  new Date().toISOString()
                });

                if (confirm("장바구니에 담겼습니다. 장바구니로 이동하시겠습니까?")) {
                    window.location.href = "cart.html";
                }
            });
        }
    } catch (e) {
        console.error("상품 정보 로드 실패:", e);
    }
}

async function loadDetailRecommendations() {
    const recommendList = document.getElementById("detail-recommend-list");
    if (!recommendList) return;

    const realtimeData = await fetchRealtimeRecommendations(SESSION_ID);
    const articleIds = realtimeData.data || realtimeData.recommendations || realtimeData.recommended_items || [];

    if (articleIds.length > 0) {
        for (const articleId of articleIds.slice(0, 10)) {
            try {
                const res = await fetch(`http://localhost:8000/api/articles/${articleId}`);
                const product = await res.json();
                recommendList.appendChild(createProductCard(product));
            } catch (e) {
                console.error(e);
            }
        }
    } else {
        const fallbackIds = ["929866001", "767869001", "782758003", "880018003", "786307003"];
        for (const articleId of fallbackIds) {
            try {
                const res = await fetch(`http://localhost:8000/api/articles/${articleId}`);
                const product = await res.json();
                recommendList.appendChild(createProductCard(product));
            } catch (e) {
                console.error(e);
            }
        }
    }
}

window.onload = () => {
    if (document.getElementById("detail-title")) {
        loadDetailInfo();
        loadDetailRecommendations();
    } else {
        loadInitialProducts();
        setupInfiniteScroll();
    }
};
