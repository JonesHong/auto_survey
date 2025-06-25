# server.py - 精簡版 (含日誌 API)
import uvicorn
import os
import json
import csv
import sys
import subprocess
import asyncio
import time
from typing import List, Optional
from pathlib import Path

from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Depends, Query
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pretty_loguru import setup_fastapi_logging, configure_uvicorn
from pydantic import BaseModel, HttpUrl, EmailStr

from src.utils.logger_manager import app_logger
from src.config.manager import ConfigManager

# 在現有導入後添加
from src.utils.graceful_shutdown import GracefulShutdown

# 初始化優雅關閉管理器
graceful_shutdown = GracefulShutdown()
# 初始化
config = ConfigManager()

app = FastAPI(
    title="自動化任務啟動器 API", description="透過 Web 介面啟動簽到與測驗自動化腳本"
)
# 靜態檔案和模板
app.mount("/static", StaticFiles(directory="static"), name="static")
app.mount("/auto_survey/static", StaticFiles(directory="static"), name="static_proxy")
templates = Jinja2Templates(directory="templates")


# ========== 資料模型 ==========
class AutomationRequest(BaseModel):
    attend_url: HttpUrl
    quiz_url: HttpUrl


class PersonalAutomationRequest(BaseModel):
    company_name: str
    name: str
    email: str
    attend_url: HttpUrl
    quiz_url: HttpUrl


class User(BaseModel):
    name: str
    email: EmailStr


class UserResponse(BaseModel):
    id: int
    name: str
    email: str


# ========== 用戶管理器 ==========
class UserManager:
    def __init__(self, csv_path: str = config.system.csv_path):
        self.csv_path = csv_path
        app_logger.info(f"用戶管理器初始化，CSV 檔案路徑: {self.csv_path}")
        self.ensure_csv_directory()
        self.users = self.load_users()
        self.next_id = max([user["id"] for user in self.users], default=0) + 1

    def ensure_csv_directory(self):
        os.makedirs(os.path.dirname(self.csv_path), exist_ok=True)
        if not os.path.exists(self.csv_path):
            with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
                writer = csv.writer(f)
                writer.writerow(["name", "email"])

    def load_users(self) -> List[dict]:
        users = []
        try:
            with open(self.csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for i, row in enumerate(reader, 1):
                    if row.get("name") and row.get("email"):
                        users.append(
                            {
                                "id": i,
                                "name": row["name"].strip(),
                                "email": row["email"].strip(),
                            }
                        )
        except FileNotFoundError:
            pass
        return users

    def save_users(self):
        with open(self.csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["name", "email"])
            for user in self.users:
                writer.writerow([user["name"], user["email"]])

    def get_all_users(self) -> List[dict]:
        return self.users.copy()

    def get_user_by_id(self, user_id: int) -> Optional[dict]:
        return next((user.copy() for user in self.users if user["id"] == user_id), None)

    def get_user_by_email(self, email: str) -> Optional[dict]:
        return next(
            (user.copy() for user in self.users if user["email"] == email), None
        )

    def add_user(self, name: str, email: str) -> dict:
        if self.get_user_by_email(email):
            raise ValueError("Email 已存在")
        new_user = {"id": self.next_id, "name": name, "email": email}
        self.users.append(new_user)
        self.next_id += 1
        self.save_users()
        return new_user.copy()

    def update_user(self, user_id: int, name: str, email: str) -> dict:
        user = self.get_user_by_id(user_id)
        if not user:
            raise ValueError("用戶不存在")
        existing_user = self.get_user_by_email(email)
        if existing_user and existing_user["id"] != user_id:
            raise ValueError("Email 已被其他用戶使用")

        for i, u in enumerate(self.users):
            if u["id"] == user_id:
                self.users[i].update({"name": name, "email": email})
                self.save_users()
                return self.users[i].copy()
        raise ValueError("用戶不存在")

    def delete_user(self, user_id: int) -> bool:
        for i, user in enumerate(self.users):
            if user["id"] == user_id:
                del self.users[i]
                self.save_users()
                return True
        return False


user_manager = UserManager()


# ========== 日誌管理器 ==========
class LogManager:
    def __init__(self, log_dir: str = "logs"):
        self.log_dir = Path(log_dir)
        self.log_file = self.log_dir / "[auto_survey]daily_latest.temp.log"

    def get_log_path(self) -> Path:
        """獲取日誌文件路徑"""
        return self.log_file

    def file_exists(self) -> bool:
        """檢查日誌文件是否存在"""
        return self.log_file.exists()

    def get_file_size(self) -> int:
        """獲取文件大小（字節）"""
        return self.log_file.stat().st_size if self.file_exists() else 0

    def get_total_lines(self) -> int:
        """獲取總行數"""
        if not self.file_exists():
            return 0
        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                return sum(1 for _ in f)
        except Exception:
            return 0

    def read_lines(
        self, start_line: int = 0, limit: int = 100
    ) -> tuple[list[str], bool]:
        """
        讀取指定範圍的行
        返回: (行列表, 是否還有更多行)
        """
        if not self.file_exists():
            return [], False

        lines = []
        has_more = False

        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                # 跳過前面的行
                for _ in range(start_line):
                    if not f.readline():
                        break

                # 讀取指定數量的行
                for i in range(limit):
                    line = f.readline()
                    if not line:
                        break
                    lines.append(line.rstrip("\n\r"))

                # 檢查是否還有更多行
                has_more = bool(f.readline())

        except Exception as e:
            app_logger.error(f"讀取日誌文件錯誤: {e}")
            return [], False

        return lines, has_more

    def tail_lines(self, num_lines: int = 100) -> list[str]:
        """獲取最後 N 行"""
        if not self.file_exists():
            return []

        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                lines = f.readlines()
                return [line.rstrip("\n\r") for line in lines[-num_lines:]]
        except Exception as e:
            app_logger.error(f"讀取日誌尾部錯誤: {e}")
            return []

    async def watch_file(self, start_pos: int = 0):
        """
        監控文件變化，yield 新增的行
        用於 SSE 即時日誌追蹤
        """
        if not self.file_exists():
            yield f"data: {json.dumps({'error': '日誌文件不存在'})}\n\n"
            return

        try:
            with open(self.log_file, "r", encoding="utf-8") as f:
                # 移動到指定位置
                f.seek(start_pos)

                while True:
                    line = f.readline()
                    if line:
                        # 發送新行
                        yield f"data: {json.dumps({'type': 'log', 'content': line.rstrip()})}\n\n"
                    else:
                        # 沒有新行，發送心跳
                        yield f"data: {json.dumps({'type': 'heartbeat', 'timestamp': time.time()})}\n\n"
                        await asyncio.sleep(1)  # 每秒檢查一次

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


log_manager = LogManager()


# ========== 工具函數 ==========
def get_root_path_from_headers(request: Request) -> str:
    """檢測代理環境並返回根路徑"""
    host = request.headers.get("host", "")
    forwarded_for = request.headers.get("x-forwarded-for")
    return "/auto_survey" if (":7777" in host or forwarded_for) else ""


def verify_editor_access(
    editor: str = Query(None, description="編輯者帳號"),
    password: str = Query(None, description="編輯者密碼"),
):
    """權限驗證"""
    if not editor or not password:
        raise HTTPException(
            status_code=403, detail="權限不足：需要提供 editor 和 password 參數"
        )

    if editor != config.system.editor_user or password != config.system.editor_password:
        raise HTTPException(
            status_code=403, detail="權限不足：editor 或 password 不正確"
        )


def run_task_in_subprocess(task_type: str, url: str, personal_info: dict = None):
    """執行子進程任務 - 實時輸出版本"""
    command = [sys.executable, "playwright_worker.py", task_type, "--url", url]
    if personal_info:
        command.extend(["--personal_info", json.dumps(personal_info)])

    app_logger.info(f"主進程：準備執行子進程命令: {' '.join(command)}")
    
    try:
        # 方案1：讓子進程直接輸出到控制台（實時顯示）
        result = subprocess.run(
            command, 
            check=False,
            text=True, 
            encoding="utf-8"
            # 不使用 capture_output=True，讓輸出直接顯示
        )
        
        if result.returncode != 0:
            app_logger.error(f"❌ 子進程任務 '{task_type}' 執行失敗，返回碼: {result.returncode}")
        else:
            app_logger.info(f"✅ 子進程任務 '{task_type}' 執行成功。")

    except FileNotFoundError:
        app_logger.error("❌ 錯誤：找不到 'playwright_worker.py'")
    except Exception as e:
        app_logger.error(f"❌ 執行子進程時發生錯誤: {e}")


def run_tasks_in_background(attend_url: str, quiz_url: str):
    """批次處理背景任務"""
    app_logger.info("🚀 批次背景任務已啟動")
    try:
        if attend_url:
            run_task_in_subprocess("batch_attendance", attend_url)
        if quiz_url:
            run_task_in_subprocess("batch_quiz", quiz_url)
        app_logger.info("✅ 所有批次背景任務觸發完畢")
    except Exception as e:
        app_logger.error(f"❌ 批次背景任務發生錯誤: {e}")


def run_personal_tasks_in_background(
    company_name: str, name: str, email: str, attend_url: str, quiz_url: str
):
    """個人處理背景任務"""
    app_logger.info(f"🧑‍💼 個人背景任務已啟動 - {name} ({email}) - {company_name}")
    personal_info = {"name": name, "email": email, "company_name": company_name}

    try:
        if attend_url:
            run_task_in_subprocess("personal_attendance", attend_url, personal_info)
        if quiz_url:
            run_task_in_subprocess("personal_quiz", quiz_url, personal_info)
        app_logger.info(f"✅ {name} 的個人任務觸發完畢")
    except Exception as e:
        app_logger.error(f"❌ {name} 的個人任務發生錯誤: {e}")


# ========== 路由註冊器 ==========
def register_routes():
    """統一註冊所有路由，避免重複程式碼"""

    # 頁面路由
    page_routes = [
        ("", "/", "index.html"),
        ("_proxy", "/auto_survey/", "index.html"),
        ("", "/csv", "csv_page.html"),
        ("_proxy", "/auto_survey/csv", "csv_page.html"),
        ("", "/personal", "personal_page.html"),
        ("_proxy", "/auto_survey/personal", "personal_page.html"),
        ("", "/log", "log.html"),
        ("_proxy", "/auto_survey/log", "log.html"),
    ]

    for suffix, path, template in page_routes:
        # 在頁面路由的處理函數中修改
        @app.get(path, response_class=HTMLResponse)
        async def page_handler(request: Request, admin_show: bool = False, template_name=template):
            root_path = get_root_path_from_headers(request)
            context = {"request": request, "root_path": root_path}
            if template_name == "csv_page.html":
                context["admin_mode"] = admin_show
            
            response = templates.TemplateResponse(template_name, context)
            
            # 如果是 log 頁面，添加允許 iframe 的頭
            if template_name == "log.html":
                response.headers["X-Frame-Options"] = "SAMEORIGIN"
                response.headers["Content-Security-Policy"] = "frame-ancestors 'self'"
            
            return response

    # 日誌 API 路由
    @app.get("/api/log/info")
    async def get_log_info():
        """獲取日誌文件基本資訊"""
        return {
            "file_exists": log_manager.file_exists(),
            "file_size": log_manager.get_file_size(),
            "total_lines": log_manager.get_total_lines(),
            "file_path": str(log_manager.get_log_path()),
        }

    @app.get("/api/log")
    async def get_log_content(
        page: int = Query(1, ge=1, description="頁碼，從1開始"),
        limit: int = Query(100, ge=1, le=1000, description="每頁行數，最大1000"),
        tail: Optional[int] = Query(None, ge=1, le=5000, description="獲取最後N行"),
    ):
        """
        分頁獲取日誌內容
        - page: 頁碼
        - limit: 每頁行數
        - tail: 如果指定，則忽略分頁，直接返回最後N行
        """
        if not log_manager.file_exists():
            raise HTTPException(status_code=404, detail="日誌文件不存在")

        if tail:
            # 返回最後 N 行
            lines = log_manager.tail_lines(tail)
            return {
                "mode": "tail",
                "lines": lines,
                "count": len(lines),
                "total_lines": log_manager.get_total_lines(),
            }

        # 分頁模式
        start_line = (page - 1) * limit
        lines, has_more = log_manager.read_lines(start_line, limit)

        return {
            "mode": "paginated",
            "page": page,
            "limit": limit,
            "lines": lines,
            "count": len(lines),
            "has_more": has_more,
            "total_lines": log_manager.get_total_lines(),
        }

    @app.get("/api/log/stream")
    async def stream_log_content(
        start_line: int = Query(0, ge=0, description="開始行數"),
        chunk_size: int = Query(50, ge=1, le=200, description="每次傳送行數"),
    ):
        """
        串流方式傳送日誌內容（非即時）
        適合一次性讀取大型日誌文件
        """
        if not log_manager.file_exists():
            raise HTTPException(status_code=404, detail="日誌文件不存在")

        async def generate_log_chunks():
            current_line = start_line

            while True:
                lines, has_more = log_manager.read_lines(current_line, chunk_size)

                if not lines:
                    break

                chunk_data = {
                    "lines": lines,
                    "start_line": current_line,
                    "count": len(lines),
                    "has_more": has_more,
                }

                yield f"data: {json.dumps(chunk_data)}\n\n"

                if not has_more:
                    break

                current_line += len(lines)
                await asyncio.sleep(0.1)  # 避免阻塞

            # 發送結束信號
            yield f"data: {json.dumps({'type': 'end'})}\n\n"

        return StreamingResponse(
            generate_log_chunks(),
            media_type="text/plain",
            headers={"Cache-Control": "no-cache"},
        )

    @app.get("/api/log/watch")
    async def watch_log_realtime(
        tail: int = Query(10, ge=0, le=100, description="初始顯示最後N行")
    ):
        """
        SSE 即時監控日誌
        會先發送最後 N 行，然後即時推送新增的日誌
        """
        if not log_manager.file_exists():
            raise HTTPException(status_code=404, detail="日誌文件不存在")

        async def generate_realtime_logs():
            # 先發送 SSE 標頭
            yield f"data: {json.dumps({'type': 'connected', 'message': '已連接到日誌監控'})}\n\n"

            # 發送最後 N 行作為歷史記錄
            if tail > 0:
                history_lines = log_manager.tail_lines(tail)
                for line in history_lines:
                    yield f"data: {json.dumps({'type': 'history', 'content': line})}\n\n"

            # 獲取當前文件大小作為起始位置
            start_pos = log_manager.get_file_size()

            # 開始即時監控
            async for event in log_manager.watch_file(start_pos):
                yield event

        return StreamingResponse(
            generate_realtime_logs(),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # 對 Nginx 代理有用
            },
        )

    # 為代理訪問添加日誌 API
    @app.get("/auto_survey/api/log/info")
    async def get_log_info_proxy():
        return await get_log_info()

    @app.get("/auto_survey/api/log")
    async def get_log_content_proxy(
        page: int = Query(1, ge=1),
        limit: int = Query(100, ge=1, le=1000),
        tail: Optional[int] = Query(None, ge=1, le=5000),
    ):
        return await get_log_content(page, limit, tail)

    @app.get("/auto_survey/api/log/stream")
    async def stream_log_content_proxy(
        start_line: int = Query(0, ge=0), chunk_size: int = Query(50, ge=1, le=200)
    ):
        return await stream_log_content(start_line, chunk_size)

    @app.get("/auto_survey/api/log/watch")
    async def watch_log_realtime_proxy(tail: int = Query(10, ge=0, le=100)):
        return await watch_log_realtime(tail)

    # API 路由
    api_prefixes = ["", "/auto_survey"]

    for prefix in api_prefixes:
        # 用戶 CRUD
        @app.get(f"{prefix}/api/users", response_model=List[UserResponse])
        async def get_users():
            return user_manager.get_all_users()

        @app.post(f"{prefix}/api/users", response_model=UserResponse)
        async def create_user(user: User, _=Depends(verify_editor_access)):
            try:
                return user_manager.add_user(user.name, user.email)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @app.get(f"{prefix}/api/users/{{user_id}}", response_model=UserResponse)
        async def get_user(user_id: int):
            user = user_manager.get_user_by_id(user_id)
            if not user:
                raise HTTPException(status_code=404, detail="用戶不存在")
            return user

        @app.put(f"{prefix}/api/users/{{user_id}}", response_model=UserResponse)
        async def update_user(
            user_id: int, user: User, _=Depends(verify_editor_access)
        ):
            try:
                return user_manager.update_user(user_id, user.name, user.email)
            except ValueError as e:
                raise HTTPException(status_code=400, detail=str(e))

        @app.delete(f"{prefix}/api/users/{{user_id}}")
        async def delete_user(user_id: int, _=Depends(verify_editor_access)):
            if not user_manager.delete_user(user_id):
                raise HTTPException(status_code=404, detail="用戶不存在")
            return {"message": "用戶已刪除"}

        # 自動化任務
        @app.post(f"{prefix}/run-automation")
        async def start_automation(
            payload: AutomationRequest, background_tasks: BackgroundTasks
        ):
            attend_url, quiz_url = str(payload.attend_url), str(payload.quiz_url)
            if not attend_url or not quiz_url:
                raise HTTPException(
                    status_code=400, detail="簽到與測驗 URL 皆為必填項。"
                )

            users = user_manager.get_all_users()
            if not users:
                raise HTTPException(
                    status_code=400, detail="請先新增用戶資料才能啟動批次任務。"
                )

            app_logger.info(
                f"收到批次請求: 簽到 URL='{attend_url}', 測驗 URL='{quiz_url}', 用戶數={len(users)}"
            )
            background_tasks.add_task(run_tasks_in_background, attend_url, quiz_url)

            return {
                "status": "success",
                "message": f"批次請求已接收 (共 {len(users)} 位用戶)，自動化任務已在背景子進程開始執行。",
            }

        @app.post(f"{prefix}/run-personal-automation")
        async def start_personal_automation(
            payload: PersonalAutomationRequest, background_tasks: BackgroundTasks
        ):
            data = [
                payload.company_name.strip(),
                payload.name.strip(),
                payload.email.strip(),
                str(payload.attend_url),
                str(payload.quiz_url),
            ]

            if not all(data):
                raise HTTPException(status_code=400, detail="所有欄位皆為必填項。")

            company_name, name, email, attend_url, quiz_url = data
            app_logger.info(f"收到個人請求: {name} ({email}) - {company_name}")

            background_tasks.add_task(
                run_personal_tasks_in_background,
                company_name,
                name,
                email,
                attend_url,
                quiz_url,
            )

            return {
                "status": "success",
                "message": f"個人請求已接收，{name} 的自動化任務已在背景子進程開始執行。",
            }


# 註冊所有路由
register_routes()

# ========== 啟動 ==========
if __name__ == "__main__":
    HOST, PORT = "0.0.0.0", 51000
    
    info_messages = [
        f"🚀 啟動伺服器於 http://{HOST}:{PORT}",
        "🌐 本地訪問: http://localhost:51000 或 http://127.0.0.1:51000",
        "🌐 外部訪問: http://114.33.18.107:7777/auto_survey/",
        "🏠 首頁: / (本地) 或 /auto_survey/ (外部)",
        "📋 批次處理: /csv (本地) 或 /auto_survey/csv (外部)",
        "👤 個人填表: /personal (本地) 或 /auto_survey/personal (外部)",
        "🔗 API 端點: /api/* (本地) 或 /auto_survey/api/* (外部)",
        "📁 用戶資料儲存於: data/users.csv",
        "📁 靜態檔案: /static (本地) 或 /auto_survey/static (外部)",
    ]
    
    for msg in info_messages:
        app_logger.info(msg)
    
    uv_config = uvicorn.Config(
            app, 
            host=HOST, 
            port=PORT,
            log_level="warning",
            access_log=False
    )
    server = uvicorn.Server(uv_config)
    
    configure_uvicorn(logger_instance=app_logger)
    setup_fastapi_logging(
        app, logger_instance=app_logger,
        middleware=False,  # <---- 這裡關掉
        log_request_body=False,
        log_response_body=False
    )
    try:
        server.run()
    except (KeyboardInterrupt, asyncio.exceptions.CancelledError, SystemExit):
        app_logger.info("⚡ 收到 Ctrl+C 中斷信號")
    except Exception as e:
        app_logger.error(f"❌ 伺服器錯誤: {e}")
    finally:
        # 手動觸發清理（因為信號處理器已經執行過了）
        if not graceful_shutdown.is_shutdown:
            graceful_shutdown.cleanup()
        app_logger.info("✅ 伺服器已停止")