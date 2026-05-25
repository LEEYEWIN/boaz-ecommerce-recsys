const API_BASE_URL = "http://localhost:8000/api";

async function sendLog(eventData) {
    const ab_group = sessionStorage.getItem("ab_group") || "unknown";
    try {
        fetch(`${API_BASE_URL}/log/event`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ ...eventData, ab_group })
        });
    } catch (error) {
        console.error("Log 전송 실패:", error);
    }
}

async function fetchMainRecommendations(userId) {
    try {
        const response = await fetch(`${API_BASE_URL}/recommend/main?user_id=${userId}`);
        const data = await response.json();
        if (data.ab_group) sessionStorage.setItem("ab_group", data.ab_group);
        return data;
    } catch (error) {
        console.error("메인 추천 조회 실패:", error);
        return { recommendations: [] };
    }
}

async function fetchRealtimeRecommendations(sessionId) {
    try {
        const response = await fetch(`${API_BASE_URL}/recommend/realtime?session_id=${sessionId}`);
        return await response.json();
    } catch (error) {
        console.error("실시간 추천 조회 실패:", error);
        return { recommendations: [] };
    }
}
