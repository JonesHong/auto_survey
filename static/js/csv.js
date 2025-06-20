// csv.js - CSV 頁面專用 JavaScript

// *** MODIFIED: 從 HTML 傳遞的全局變量 ***
const ROOT_PATH = window.ROOT_PATH || '';
const ADMIN_MODE = window.ADMIN_MODE || false; // 從 HTML 獲取 admin 模式狀態

// 全局變數
let users = [];
// editingUserId 這個變量在您的原始碼中已定義但未使用，我將其移除以保持整潔
// let editingUserId = null; 

// 初始化
document.addEventListener('DOMContentLoaded', function () {
    updateClock();
    setInterval(updateClock, 1000);
    loadUsers();
    setupEventListeners();
});

// 更新時鐘 (不變)
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

// 設置事件監聽器 (不變)
function setupEventListeners() {
    document.getElementById('automation-form').addEventListener('submit', handleAutomationSubmit);

    // 只有在 admin 模式下才需要這些監聽器
    if (ADMIN_MODE) {
        document.getElementById('new-name').addEventListener('keypress', function (e) {
            if (e.key === 'Enter') addUser();
        });
        document.getElementById('new-email').addEventListener('keypress', function (e) {
            if (e.key === 'Enter') addUser();
        });
        document.getElementById('edit-name').addEventListener('keypress', function (e) {
            if (e.key === 'Enter') saveUser();
        });
        document.getElementById('edit-email').addEventListener('keypress', function (e) {
            if (e.key === 'Enter') saveUser();
        });
        document.getElementById('edit-modal').addEventListener('click', function (e) {
            if (e.target === this) closeEditModal();
        });
    }
}

// *** NEW: 新增權限參數輔助函數 ***
/**
 * 從當前瀏覽器 URL 獲取權限參數
 * @returns {string} - 返回 "?editor=user&password=root" 這樣的查詢字符串，如果不存在則返回空字符串
 */
function getAuthParams() {
    const urlParams = new URLSearchParams(window.location.search);
    const editor = urlParams.get('editor');
    const password = urlParams.get('password');
    if (editor && password) {
        return `?editor=${encodeURIComponent(editor)}&password=${encodeURIComponent(password)}`;
    }
    return '';
}

// 載入用戶資料
async function loadUsers() {
    try {
        const response = await fetch(`${ROOT_PATH}/api/users`);
        if (response.ok) {
            users = await response.json();
            renderUserTable(); // renderUserTable 內部會處理 admin 模式
            updateUserStats();
        } else {
            throw new Error('載入用戶資料失敗');
        }
    } catch (error) {
        console.error('載入用戶資料錯誤:', error);
        const colspan = ADMIN_MODE ? 4 : 3;
        document.getElementById('user-table-body').innerHTML =
            `<tr><td colspan="${colspan}" class="no-data">載入用戶資料失敗，請檢查伺服器連線</td></tr>`;
    }
}

// *** MODIFIED: 渲染用戶表格，根據 ADMIN_MODE 顯示/隱藏操作欄 ***
function renderUserTable() {
    const tbody = document.getElementById('user-table-body');
    const colspan = ADMIN_MODE ? 4 : 3;

    if (users.length === 0) {
        tbody.innerHTML = `<tr><td colspan="${colspan}" class="no-data">尚無用戶資料</td></tr>`;
        return;
    }

    tbody.innerHTML = users.map((user, index) => `
        <tr>
            <td>${index + 1}</td>
            <td>${escapeHtml(user.name)}</td>
            <td>${escapeHtml(user.email)}</td>
            ${ADMIN_MODE ? `
            <td>
                <div class="action-buttons">
                    <button onclick="editUser(${user.id})" class="btn-edit">✏️ 編輯</button>
                    <button onclick="deleteUser(${user.id}, '${escapeHtml(user.name)}')" class="btn-delete">🗑️ 刪除</button>
                </div>
            </td>
            ` : ''}
        </tr>
    `).join('');
}


// 更新用戶統計 (不變)
function updateUserStats() {
    document.getElementById('user-count').textContent = `共 ${users.length} 位用戶`;
}

// *** MODIFIED: 新增用戶，加入權限驗證 ***
async function addUser() {
    const authParams = getAuthParams();
    if (!authParams) {
        alert('權限不足！請確保 URL 中包含正確的 editor 和 password 參數。');
        return;
    }

    const name = document.getElementById('new-name').value.trim();
    const email = document.getElementById('new-email').value.trim();

    if (!name || !email) {
        alert('請填寫姓名和 Email');
        return;
    }

    if (!isValidEmail(email)) {
        alert('請輸入有效的 Email 地址');
        return;
    }

    if (users.some(user => user.email === email)) {
        alert('此 Email 已存在');
        return;
    }

    try {
        const response = await fetch(`${ROOT_PATH}/api/users${authParams}`, { // 附加權限參數
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, email })
        });

        if (response.ok) {
            const newUser = await response.json();
            users.push(newUser);
            renderUserTable();
            updateUserStats();
            document.getElementById('new-name').value = '';
            document.getElementById('new-email').value = '';
            showMessage('用戶新增成功', 'success');
        } else {
            const error = await response.json();
            throw new Error(error.detail || '新增用戶失敗');
        }
    } catch (error) {
        console.error('新增用戶錯誤:', error);
        showMessage('新增用戶失敗: ' + error.message, 'error');
    }
}

// 編輯用戶 (不變)
function editUser(userId) {
    const user = users.find(u => u.id === userId);
    if (!user) return;
    
    document.getElementById('edit-user-id').value = userId;
    document.getElementById('edit-name').value = user.name;
    document.getElementById('edit-email').value = user.email;
    document.getElementById('edit-modal').style.display = 'block';
}

// *** MODIFIED: 保存用戶，加入權限驗證 ***
async function saveUser() {
    const authParams = getAuthParams();
    if (!authParams) {
        alert('權限不足！');
        closeEditModal();
        return;
    }

    const userId = parseInt(document.getElementById('edit-user-id').value);
    const name = document.getElementById('edit-name').value.trim();
    const email = document.getElementById('edit-email').value.trim();

    if (!name || !email) {
        alert('請填寫姓名和 Email');
        return;
    }

    if (!isValidEmail(email)) {
        alert('請輸入有效的 Email 地址');
        return;
    }

    if (users.some(user => user.id !== userId && user.email === email)) {
        alert('此 Email 已被其他用戶使用');
        return;
    }

    try {
        const response = await fetch(`${ROOT_PATH}/api/users/${userId}${authParams}`, { // 附加權限參數
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name, email })
        });

        if (response.ok) {
            const updatedUser = await response.json();
            const index = users.findIndex(u => u.id === userId);
            if (index !== -1) {
                users[index] = updatedUser;
                renderUserTable();
                closeEditModal();
                showMessage('用戶更新成功', 'success');
            }
        } else {
            const error = await response.json();
            throw new Error(error.detail || '更新用戶失敗');
        }
    } catch (error) {
        console.error('更新用戶錯誤:', error);
        showMessage('更新用戶失敗: ' + error.message, 'error');
    }
}

// *** MODIFIED: 刪除用戶，加入權限驗證 ***
async function deleteUser(userId, userName) {
    const authParams = getAuthParams();
    if (!authParams) {
        alert('權限不足！');
        return;
    }
    
    if (!confirm(`確定要刪除用戶「${userName}」嗎？此操作無法復原。`)) {
        return;
    }

    try {
        const response = await fetch(`${ROOT_PATH}/api/users/${userId}${authParams}`, { // 附加權限參數
            method: 'DELETE'
        });

        if (response.ok) {
            users = users.filter(u => u.id !== userId);
            renderUserTable();
            updateUserStats();
            showMessage('用戶刪除成功', 'success');
        } else {
            const error = await response.json();
            throw new Error(error.detail || '刪除用戶失敗');
        }
    } catch (error) {
        console.error('刪除用戶錯誤:', error);
        showMessage('刪除用戶失敗: ' + error.message, 'error');
    }
}

// 關閉編輯彈窗 (不變)
function closeEditModal() {
    document.getElementById('edit-modal').style.display = 'none';
}

// *** MODIFIED: 重新載入用戶列表，考慮 colspan ***
function refreshUserList() {
    const colspan = ADMIN_MODE ? 4 : 3;
    document.getElementById('user-table-body').innerHTML =
        `<tr><td colspan="${colspan}" class="loading">重新載入中...</td></tr>`;
    loadUsers();
}


// 匯出 CSV (不變)
function exportToCSV() {
    if (users.length === 0) {
        alert('沒有用戶資料可以匯出');
        return;
    }
    const csvContent = 'name,email\n' +
        users.map(user => `"${user.name}","${user.email}"`).join('\n');
    const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `users_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    showMessage('CSV 檔案已匯出', 'success');
}

// *** MODIFIED: 匯入 CSV，加入權限驗證 ***
async function importFromCSV(event) {
    const authParams = getAuthParams();
    if (!authParams) {
        alert('權限不足，無法匯入！');
        event.target.value = ''; // 清空檔案選擇
        return;
    }
    
    const file = event.target.files[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith('.csv')) {
        alert('請選擇 CSV 檔案');
        return;
    }

    try {
        const text = await file.text();
        const lines = text.split('\n').filter(line => line.trim());
        if (lines.length < 2) {
            alert('CSV 檔案格式不正確，至少需要標題行和一筆資料');
            return;
        }

        const headers = lines[0].toLowerCase().split(',').map(h => h.trim().replace(/"/g, ''));
        if (!headers.includes('name') || !headers.includes('email')) {
            alert('CSV 檔案必須包含 name 和 email 欄位');
            return;
        }

        const nameIndex = headers.indexOf('name');
        const emailIndex = headers.indexOf('email');
        const importData = [];
        const errors = [];

        for (let i = 1; i < lines.length; i++) {
            const values = lines[i].split(',').map(v => v.trim().replace(/"/g, ''));
            const name = values[nameIndex]?.trim();
            const email = values[emailIndex]?.trim();
            if (!name || !email) {
                errors.push(`第 ${i + 1} 行: 姓名或 Email 為空`);
                continue;
            }
            if (!isValidEmail(email)) {
                errors.push(`第 ${i + 1} 行: Email 格式不正確 (${email})`);
                continue;
            }
            if (users.some(user => user.email === email) || importData.some(data => data.email === email)) {
                errors.push(`第 ${i + 1} 行: Email 已存在 (${email})`);
                continue;
            }
            importData.push({ name, email });
        }

        if (importData.length === 0) {
            alert('沒有有效的資料可以匯入\n\n錯誤:\n' + errors.join('\n'));
            return;
        }

        const confirmMessage = `準備匯入 ${importData.length} 筆資料${errors.length > 0 ? `\n\n跳過 ${errors.length} 筆錯誤資料` : ''}`;
        if (!confirm(confirmMessage)) return;

        let successCount = 0;
        for (const userData of importData) {
            try {
                // *** 這裡也加上權限參數 ***
                const response = await fetch(`${ROOT_PATH}/api/users${authParams}`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(userData)
                });
                if (response.ok) {
                    const newUser = await response.json();
                    users.push(newUser);
                    successCount++;
                } else {
                    const error = await response.json();
                    errors.push(`${userData.name}: ${error.detail}`);
                }
            } catch (error) {
                errors.push(`${userData.name}: ${error.message}`);
            }
        }

        renderUserTable();
        updateUserStats();

        let message = `成功匯入 ${successCount} 筆資料`;
        if (errors.length > 0) {
            message += `\n\n錯誤 (${errors.length} 筆):\n${errors.join('\n')}`;
        }
        showMessage(message, successCount > 0 ? 'success' : 'error');

    } catch (error) {
        console.error('匯入 CSV 錯誤:', error);
        showMessage('匯入 CSV 失敗: ' + error.message, 'error');
    } finally {
        event.target.value = '';
    }
}

// 表單提交處理 (不變)
async function handleAutomationSubmit(e) {
    e.preventDefault();
    if (users.length === 0) {
        alert('請先新增用戶資料才能啟動批次任務');
        return;
    }
    const submitBtn = document.getElementById('submit-btn');
    const statusMessage = document.getElementById('status-message');
    const attendUrl = document.getElementById('attend_url').value;
    const quizUrl = document.getElementById('quiz_url').value;
    submitBtn.disabled = true;
    submitBtn.textContent = '⏳ 處理中...';
    statusMessage.innerHTML = '<div class="status loading">⏳ 正在啟動批次自動化任務...</div>';
    try {
        const apiUrl = `${ROOT_PATH}/run-automation`;
        const response = await fetch(apiUrl, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
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
                    • 用戶數量: ${users.length} 位<br>
                    • 簽到 URL: ${escapeHtml(attendUrl)}<br>
                    • 測驗 URL: ${escapeHtml(quizUrl)}<br>
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
        submitBtn.disabled = false;
        submitBtn.textContent = '🚀 啟動批次自動化任務';
    }
}

// 工具函數 (不變)
function isValidEmail(email) {
    const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    return emailRegex.test(email);
}

function escapeHtml(text) {
    if (typeof text !== 'string') return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showMessage(message, type) {
    const statusMessage = document.getElementById('status-message');
    statusMessage.innerHTML = `<div class="status ${type}">${message.replace(/\n/g, '<br>')}</div>`;
    if (type === 'success') {
        setTimeout(() => {
            if (statusMessage.innerHTML.includes(message.split('\n')[0])) {
                statusMessage.innerHTML = '';
            }
        }, 5000);
    }
}