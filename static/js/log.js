// log.js - 日誌查看器 JavaScript

class LogViewer {
    constructor() {
        this.rootPath = window.ROOT_PATH || '';
        this.isRealtime = false;
        this.autoScroll = true;
        this.eventSource = null;
        this.logs = [];
        this.maxLogs = 1000; // 最大保留日誌數量

        this.initializeElements();
        this.bindEvents();
        this.loadInitialLogs();
        this.updateLogInfo();

        // 檢測是否在 iframe 中
        if (window.self !== window.top) {
            document.body.classList.add('iframe-mode');
        }
    }

    initializeElements() {
        this.logBody = document.getElementById('log-body');
        this.refreshBtn = document.getElementById('refresh-btn');
        this.clearBtn = document.getElementById('clear-btn');
        this.exportBtn = document.getElementById('export-btn');
        this.realtimeBtn = document.getElementById('realtime-btn');
        this.tailInput = document.getElementById('tail-input');
        this.scrollToBottomBtn = document.getElementById('scroll-to-bottom');
        this.autoScrollToggle = document.getElementById('auto-scroll-toggle');
        this.connectionStatus = document.getElementById('connection-status');
        this.lastUpdate = document.getElementById('last-update');
        this.logStatus = document.getElementById('log-status');
        this.logSize = document.getElementById('log-size');
        this.logLines = document.getElementById('log-lines');
        this.searchInput = document.getElementById('search-input');
        this.searchBtn = document.getElementById('search-btn');
        this.clearSearchBtn = document.getElementById('clear-search-btn');
    }

    bindEvents() {
        this.refreshBtn.addEventListener('click', () => this.refreshLogs());
        this.clearBtn.addEventListener('click', () => this.clearLogs());
        this.exportBtn.addEventListener('click', () => this.exportLogs());
        this.realtimeBtn.addEventListener('click', () => this.toggleRealtime());
        this.scrollToBottomBtn.addEventListener('click', () => this.scrollToBottom());
        this.autoScrollToggle.addEventListener('click', () => this.toggleAutoScroll());
        this.tailInput.addEventListener('change', () => this.refreshLogs());

        // 滾動事件監聽
        this.logBody.addEventListener('scroll', () => this.handleScroll());
        this.searchInput.addEventListener('input', () => this.handleSearchInput());
        this.searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.performSearch();
        });
        this.searchBtn.addEventListener('click', () => this.performSearch());
        this.clearSearchBtn.addEventListener('click', () => this.clearSearch());
    }

    async loadInitialLogs() {
        this.showLoading();
        try {
            const tailLines = parseInt(this.tailInput.value) || 50;
            const response = await fetch(`${this.rootPath}/api/log?tail=${tailLines}`);

            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }

            const data = await response.json();
            this.logs = data.lines.map(line => this.parseLogLine(line));
            this.renderLogs();
            this.updateLastUpdate();

        } catch (error) {
            this.showError('載入日誌失敗: ' + error.message);
        }
    }

    async updateLogInfo() {
        try {
            const response = await fetch(`${this.rootPath}/api/log/info`);
            if (response.ok) {
                const info = await response.json();
                this.logStatus.textContent = info.file_exists ? '✅ 存在' : '❌ 不存在';
                this.logSize.textContent = this.formatFileSize(info.file_size);
                this.logLines.textContent = `${info.total_lines} 行`;
            }
        } catch (error) {
            console.error('獲取日誌資訊失敗:', error);
        }

        // 每 30 秒更新一次資訊
        setTimeout(() => this.updateLogInfo(), 30000);
    }

    parseLogLine(line) {
        // 解析日誌行格式: 2025-06-20 10:11:20 | INFO    24368 | auto_survey:setup_fastapi_logging:385 - 訊息內容
        const regex = /^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s*\|\s*(\w+)\s+(\d+)\s*\|\s*([^:]+:[^:]+:\d+)\s*-\s*(.+)$/;
        const match = line.match(regex);

        if (match) {
            return {
                timestamp: match[1],
                level: match[2].trim(),
                process: match[3],
                source: match[4],
                message: match[5],
                raw: line
            };
        }

        // 如果不符合格式，作為普通訊息處理
        return {
            timestamp: new Date().toLocaleString('zh-TW'),
            level: 'INFO',
            process: '-',
            source: 'system',
            message: line,
            raw: line
        };
    }

    renderLogs() {
        if (this.logs.length === 0) {
            this.logBody.innerHTML = '<div class="log-empty">📝 暫無日誌記錄</div>';
            return;
        }

        const html = this.logs.map(log => this.createLogEntryHTML(log)).join('');
        this.logBody.innerHTML = html;

        if (this.autoScroll) {
            this.scrollToBottom();
        }
    }

    createLogEntryHTML(log, isNew = false) {
        const levelClass = log.level.toUpperCase();
        const entryClass = isNew ? 'log-entry new' : 'log-entry';

        return `
            <div class="${entryClass}">
                <div class="log-timestamp">${log.timestamp}</div>
                <div class="log-level ${levelClass}">${log.level}</div>
                <div class="log-source">${this.escapeHtml(log.source)}</div>
                <div class="log-message">${this.escapeHtml(log.message)}</div>
            </div>
        `;
    }

    addNewLog(logLine) {
        const log = this.parseLogLine(logLine);
        this.logs.push(log);

        // 限制日誌數量
        if (this.logs.length > this.maxLogs) {
            this.logs = this.logs.slice(-this.maxLogs);
            this.renderLogs(); // 重新渲染所有日誌
        } else {
            // 只添加新日誌
            const newLogHTML = this.createLogEntryHTML(log, true);
            this.logBody.insertAdjacentHTML('beforeend', newLogHTML);
        }

        if (this.autoScroll) {
            this.scrollToBottom();
        }

        this.updateLastUpdate();
    }

    async refreshLogs() {
        this.refreshBtn.disabled = true;
        this.refreshBtn.textContent = '⏳ 載入中';

        try {
            await this.loadInitialLogs();
        } finally {
            this.refreshBtn.disabled = false;
            this.refreshBtn.textContent = '🔄 重新載入';
        }
    }

    clearLogs() {
        if (confirm('確定要清空日誌顯示嗎？（不會刪除原始日誌文件）')) {
            this.logs = [];
            this.logBody.innerHTML = '<div class="log-empty">📝 日誌已清空</div>';
        }
    }

    exportLogs() {
        if (this.logs.length === 0) {
            alert('沒有日誌可以匯出');
            return;
        }

        const content = this.logs.map(log => log.raw).join('\n');
        const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `logs_${new Date().toISOString().split('T')[0]}.log`;
        a.click();
        URL.revokeObjectURL(url);
    }

    toggleRealtime() {
        if (this.isRealtime) {
            this.stopRealtime();
        } else {
            this.startRealtime();
        }
    }

    async startRealtime() {
        try {
            const tailLines = parseInt(this.tailInput.value) || 10;
            this.eventSource = new EventSource(`${this.rootPath}/api/log/watch?tail=${tailLines}`);

            this.eventSource.onopen = () => {
                this.isRealtime = true;
                this.realtimeBtn.textContent = '⏹️ 停止監控';
                this.realtimeBtn.classList.add('active');
                this.connectionStatus.textContent = '🟢 即時監控中';
                this.connectionStatus.className = 'connected';
            };

            this.eventSource.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);

                    switch (data.type) {
                        case 'connected':
                            console.log('已連接到日誌監控');
                            break;
                        case 'history':
                            // 歷史日誌已在初始載入時處理
                            break;
                        case 'log':
                            this.addNewLog(data.content);
                            break;
                        case 'heartbeat':
                            // 心跳信號，更新連接狀態
                            this.updateLastUpdate();
                            break;
                        case 'error':
                            console.error('日誌監控錯誤:', data.message);
                            break;
                    }
                } catch (error) {
                    console.error('解析 SSE 資料錯誤:', error);
                }
            };

            this.eventSource.onerror = () => {
                this.stopRealtime();
                this.connectionStatus.textContent = '🔴 連接中斷';
                this.connectionStatus.className = 'disconnected';
            };

        } catch (error) {
            this.showError('啟動即時監控失敗: ' + error.message);
        }
    }

    stopRealtime() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }

        this.isRealtime = false;
        this.realtimeBtn.textContent = '📡 即時監控';
        this.realtimeBtn.classList.remove('active');
        this.connectionStatus.textContent = '🔴 離線';
        this.connectionStatus.className = 'disconnected';
    }

    toggleAutoScroll() {
        this.autoScroll = !this.autoScroll;
        this.autoScrollToggle.classList.toggle('active', this.autoScroll);
        this.autoScrollToggle.textContent = this.autoScroll ? '🔄 自動滾動' : '⏸️ 自動滾動';

        if (this.autoScroll) {
            this.scrollToBottom();
        }
    }

    scrollToBottom() {
        this.logBody.scrollTop = this.logBody.scrollHeight;
    }

    handleScroll() {
        const { scrollTop, scrollHeight, clientHeight } = this.logBody;
        const isAtBottom = scrollTop + clientHeight >= scrollHeight - 5;

        // 如果手動滾動到非底部，暫時停止自動滾動
        if (!isAtBottom && this.autoScroll) {
            this.autoScrollToggle.style.opacity = '0.6';
        } else if (isAtBottom && this.autoScroll) {
            this.autoScrollToggle.style.opacity = '1';
        }
    }

    showLoading() {
        this.logBody.innerHTML = `
            <div class="log-loading">
                <div class="loading-spinner"></div>
                <span>載入日誌中...</span>
            </div>
        `;
    }

    showError(message) {
        this.logBody.innerHTML = `
            <div class="log-error">
                ❌ ${message}
                <br><br>
                <button onclick="logViewer.refreshLogs()" class="btn btn-secondary">重試</button>
            </div>
        `;
    }

    updateLastUpdate() {
        const now = new Date().toLocaleTimeString('zh-TW');
        this.lastUpdate.textContent = `最後更新: ${now}`;
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
    handleSearchInput() {
        const query = this.searchInput.value.trim();
        if (query.length === 0) {
            this.clearSearch();
        } else if (query.length >= 2) {
            // 實時搜尋（當輸入2個字符以上時）
            this.performSearch();
        }
    }

    performSearch() {
        const query = this.searchInput.value.trim().toLowerCase();
        if (!query) {
            this.clearSearch();
            return;
        }

        let matchCount = 0;
        const logEntries = this.logBody.querySelectorAll('.log-entry');

        logEntries.forEach(entry => {
            const text = entry.textContent.toLowerCase();
            const isMatch = text.includes(query);

            if (isMatch) {
                matchCount++;
                entry.classList.add('search-match');
                entry.classList.remove('search-hidden');

                // 高亮匹配的文字
                this.highlightText(entry, query);
            } else {
                entry.classList.remove('search-match');
                entry.classList.add('search-hidden');
            }
        });

        // 更新搜尋狀態
        this.updateSearchStatus(query, matchCount, logEntries.length);

        // 滾動到第一個匹配項
        if (matchCount > 0) {
            const firstMatch = this.logBody.querySelector('.log-entry.search-match');
            if (firstMatch) {
                firstMatch.scrollIntoView({ behavior: 'smooth', block: 'center' });
            }
        }
    }

    highlightText(entry, query) {
        // 移除之前的高亮
        this.removeHighlight(entry);

        const walker = document.createTreeWalker(
            entry,
            NodeFilter.SHOW_TEXT,
            null,
            false
        );

        const textNodes = [];
        let node;
        while (node = walker.nextNode()) {
            textNodes.push(node);
        }

        textNodes.forEach(textNode => {
            const text = textNode.textContent;
            const lowerText = text.toLowerCase();
            const lowerQuery = query.toLowerCase();

            if (lowerText.includes(lowerQuery)) {
                const regex = new RegExp(`(${this.escapeRegex(query)})`, 'gi');
                const highlightedHTML = text.replace(regex, '<span class="highlight">$1</span>');

                const wrapper = document.createElement('span');
                wrapper.innerHTML = highlightedHTML;
                textNode.parentNode.replaceChild(wrapper, textNode);
            }
        });
    }

    removeHighlight(entry) {
        const highlights = entry.querySelectorAll('.highlight');
        highlights.forEach(highlight => {
            const parent = highlight.parentNode;
            parent.replaceChild(document.createTextNode(highlight.textContent), highlight);
            parent.normalize();
        });
    }

    clearSearch() {
        this.searchInput.value = '';
        this.searchInput.classList.remove('has-results', 'no-results');
        this.clearSearchBtn.style.display = 'none';

        // 移除搜尋樣式
        const logEntries = this.logBody.querySelectorAll('.log-entry');
        logEntries.forEach(entry => {
            entry.classList.remove('search-match', 'search-hidden');
            this.removeHighlight(entry);
        });

        // 移除搜尋統計
        const existingStats = this.logBody.parentNode.querySelector('.search-stats');
        if (existingStats) {
            existingStats.remove();
        }
    }

    updateSearchStatus(query, matchCount, totalCount) {
        // 更新輸入框樣式
        this.searchInput.classList.remove('has-results', 'no-results');
        this.searchInput.classList.add(matchCount > 0 ? 'has-results' : 'no-results');

        // 顯示/隱藏清除按鈕
        this.clearSearchBtn.style.display = query ? 'block' : 'none';

        // 顯示搜尋統計
        this.showSearchStats(query, matchCount, totalCount);
    }

    showSearchStats(query, matchCount, totalCount) {
        // 移除之前的統計
        const existingStats = this.logBody.parentNode.querySelector('.search-stats');
        if (existingStats) {
            existingStats.remove();
        }

        // 添加新的統計
        const statsDiv = document.createElement('div');
        statsDiv.className = 'search-stats';
        statsDiv.innerHTML = `
        搜尋 "<strong>${this.escapeHtml(query)}</strong>": 
        找到 <strong>${matchCount}</strong> 條匹配記錄 (共 ${totalCount} 條)
        ${matchCount === 0 ? ' - 未找到匹配項' : ''}
    `;

        this.logBody.parentNode.insertBefore(statsDiv, this.logBody);
    }

    escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    // 修改 renderLogs 方法，在渲染後保持搜尋狀態
    renderLogs() {
        const currentQuery = this.searchInput ? this.searchInput.value.trim() : '';

        if (this.logs.length === 0) {
            this.logBody.innerHTML = '<div class="log-empty">📝 暫無日誌記錄</div>';
            return;
        }

        const html = this.logs.map(log => this.createLogEntryHTML(log)).join('');
        this.logBody.innerHTML = html;

        // 如果有搜尋查詢，重新應用搜尋
        if (currentQuery) {
            setTimeout(() => this.performSearch(), 100);
        }

        if (this.autoScroll && !currentQuery) {
            this.scrollToBottom();
        }
    }
}

// 初始化日誌查看器
let logViewer;
document.addEventListener('DOMContentLoaded', () => {
    logViewer = new LogViewer();
});

// 清理資源
window.addEventListener('beforeunload', () => {
    if (logViewer && logViewer.eventSource) {
        logViewer.eventSource.close();
    }
});