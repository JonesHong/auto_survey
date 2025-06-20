// 日誌查看器小工具 JavaScript
class LogWidget {
    constructor() {
        this.isVisible = false;
        this.isMinimized = false;
        this.initializeElements();
        this.bindEvents();
    }

    initializeElements() {
        this.toggleBtn = document.getElementById('log-toggle-btn');
        this.panel = document.getElementById('log-panel');
        this.minimizeBtn = document.getElementById('log-minimize-btn');
        this.closeBtn = document.getElementById('log-close-btn');
        this.iframe = document.getElementById('log-iframe');
    }

    bindEvents() {
        this.toggleBtn.addEventListener('click', () => this.toggle());
        this.minimizeBtn.addEventListener('click', () => this.minimize());
        this.closeBtn.addEventListener('click', () => this.hide());
        
        // iframe 載入錯誤處理
        this.iframe.addEventListener('error', () => {
            console.error('日誌 iframe 載入失敗');
            this.showError();
        });
        
        this.makeDraggable();
    }

    toggle() {
        if (this.isVisible) {
            this.hide();
        } else {
            this.show();
        }
    }

    // 在 LogWidget 的 show() 方法中動態設定 src
    show() {
        this.panel.classList.add('show');
        this.isVisible = true;
        this.toggleBtn.style.transform = 'rotate(180deg)';

        // 動態設定 iframe src
        if (!this.iframe.src) {
            const rootPath = window.ROOT_PATH || '';
            this.iframe.src = `${rootPath}/log`;
        }
    }

    showError() {
        this.iframe.style.display = 'none';
        const errorDiv = document.createElement('div');
        errorDiv.innerHTML = `
            <div style="padding: 20px; text-align: center; color: #f44336;">
                ❌ 日誌載入失敗<br>
                <button onclick="window.open('${window.ROOT_PATH || ''}/log', '_blank')" 
                        style="margin-top: 10px; padding: 8px 16px; background: #667eea; color: white; border: none; border-radius: 4px; cursor: pointer;">
                    在新視窗中開啟
                </button>
            </div>
        `;
        this.panel.querySelector('.log-panel-content').appendChild(errorDiv);
    }

    hide() {
        this.panel.classList.remove('show');
        this.panel.classList.remove('minimized');
        this.isVisible = false;
        this.isMinimized = false;
        this.toggleBtn.style.transform = 'rotate(0deg)';
    }

    minimize() {
        this.panel.classList.toggle('minimized');
        this.isMinimized = !this.isMinimized;
        this.minimizeBtn.textContent = this.isMinimized ? '□' : '─';
    }

    makeDraggable() {
        const header = this.panel.querySelector('.log-panel-header');
        let isDragging = false;
        let currentX, currentY, initialX, initialY;

        header.addEventListener('mousedown', (e) => {
            isDragging = true;
            initialX = e.clientX - this.panel.offsetLeft;
            initialY = e.clientY - this.panel.offsetTop;
            this.panel.style.position = 'fixed';
        });

        document.addEventListener('mousemove', (e) => {
            if (isDragging) {
                e.preventDefault();
                currentX = e.clientX - initialX;
                currentY = e.clientY - initialY;
                this.panel.style.left = currentX + 'px';
                this.panel.style.top = currentY + 'px';
                this.panel.style.right = 'auto';
                this.panel.style.bottom = 'auto';
            }
        });

        document.addEventListener('mouseup', () => {
            isDragging = false;
        });
    }
}

// 初始化日誌小工具
document.addEventListener('DOMContentLoaded', () => {
    new LogWidget();
});