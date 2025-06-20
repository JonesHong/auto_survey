// personal_script.js
// 獲取根路徑，如果沒有定義則默認為空字串
const ROOT_PATH = window.ROOT_PATH || '';

// 更新時鐘
function updateClock() {
    const now = new Date();
    const timeString = now.toLocaleString('zh-TW', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    });
    document.getElementById('clock').textContent = `現在時間：${timeString}`;
}

// 每秒更新時鐘
setInterval(updateClock, 1000);
updateClock(); // 立即更新一次

// 表單提交處理
document.getElementById('personal-automation-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    const submitBtn = document.getElementById('submit-btn');
    const statusMessage = document.getElementById('status-message');
    const companyName = document.getElementById('company_name').value;
    const name = document.getElementById('name').value;
    const email = document.getElementById('email').value;
    const attendUrl = document.getElementById('attend_url').value;
    const quizUrl = document.getElementById('quiz_url').value;
    
    // 更新按鈕狀態
    submitBtn.disabled = true;
    submitBtn.textContent = '⏳ 處理中...';
    statusMessage.innerHTML = '<div class="status loading">⏳ 正在啟動個人自動化任務...</div>';
    
    try {
        // 使用動態根路徑構建 API 請求 URL
        const apiUrl = `${ROOT_PATH}/run-personal-automation`;
        
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                company_name: companyName,
                name: name,
                email: email,
                attend_url: attendUrl,
                quiz_url: quizUrl
            })
        });
        
        const result = await response.json();
        
        if (response.ok) {
            statusMessage.innerHTML = `
                <div class="status success">
                    ✅ ${result.message}
                    <br><br>
                    <strong>📋 任務詳情：</strong><br>
                    • 姓名: ${name}<br>
                    • Email: ${email}<br>
                    • 公司: ${companyName}<br>
                    • 簽到 URL: ${attendUrl}<br>
                    • 測驗 URL: ${quizUrl}<br>
                    <br>
                    <em>💡 請查看伺服器終端機以獲取詳細執行日誌。</em>
                </div>
            `;
        } else {
            throw new Error(result.detail || '未知錯誤');
        }
    } catch (error) {
        console.error('錯誤:', error);
        statusMessage.innerHTML = `
            <div class="status error">
                ❌ 發生錯誤: ${error.message}
                <br><br>
                <em>請檢查網路連線或伺服器狀態。</em>
            </div>
        `;
    } finally {
        // 恢復按鈕狀態
        submitBtn.disabled = false;
        submitBtn.textContent = '🚀 開始個人自動化任務';
    }
});