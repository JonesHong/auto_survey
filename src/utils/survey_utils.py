"""
共用的問卷/簽到工具模組
包含快取管理、CSV處理、瀏覽器操作等共用功能
"""

import json
import os
import hashlib
import csv
import random
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright
from src.utils.logger_manager import app_logger

# ========== 快取管理系統 ==========
class CacheManager:
    def __init__(self, cache_dir="survey_cache"):
        self.cache_dir = cache_dir
        self.ensure_cache_directory()
    
    def ensure_cache_directory(self):
        """確保快取目錄存在"""
        if not os.path.exists(self.cache_dir):
            os.makedirs(self.cache_dir)
            app_logger.info(f"建立快取目錄: {self.cache_dir}")
    
    def get_url_hash(self, url):
        """生成網址的唯一識別碼"""
        return hashlib.md5(url.encode()).hexdigest()
    
    def load_json_file(self, filename):
        """載入 JSON 檔案，如果檔案不存在則回傳空字典"""
        file_path = os.path.join(self.cache_dir, filename)
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
        except Exception as e:
            app_logger.error(f"載入檔案 {file_path} 時發生錯誤: {e}")
        return {}
    
    def save_json_file(self, filename, data):
        """儲存資料到 JSON 檔案"""
        file_path = os.path.join(self.cache_dir, filename)
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            app_logger.info(f"資料已儲存到: {file_path}")
        except Exception as e:
            app_logger.error(f"儲存檔案 {file_path} 時發生錯誤: {e}")
    
    def is_user_submitted(self, url, name, email):
        """檢查使用者是否已經提交過表單"""
        data = self.load_json_file("submission_log.json")
        url_hash = self.get_url_hash(url)
        if url_hash in data:
            for submission in data[url_hash].get("submissions", []):
                if submission["name"] == name and submission["email"] == email:
                    return True, submission["timestamp"]
        return False, None
    
    def log_user_submission(self, url, name, email, success=True):
        """記錄使用者提交狀態"""
        data = self.load_json_file("submission_log.json")
        url_hash = self.get_url_hash(url)
        
        if url_hash not in data:
            data[url_hash] = {
                "url": url,
                "submissions": []
            }
        
        data[url_hash]["submissions"].append({
            "name": name,
            "email": email,
            "timestamp": datetime.now().isoformat(),
            "success": success
        })
        
        self.save_json_file("submission_log.json", data)

# ========== CSV 資料處理 ==========
def load_and_shuffle_csv_data(csv_path):
    """從 CSV 讀取資料，轉換成 list 並進行隨機排序"""
    user_data = []
    try:
        with open(csv_path, newline='', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row.get('name') and row.get('email'):  # 確保資料完整
                    user_data.append({
                        'name': row['name'].strip(),
                        'email': row['email'].strip()
                    })
        
        random.shuffle(user_data)
        
        app_logger.info(f"從 CSV 讀取了 {len(user_data)} 筆資料，已進行隨機排序")
        app_logger.info("隨機排序後的順序：")
        for i, user in enumerate(user_data, 1):
            app_logger.info(f"  {i}. {user['name']} ({user['email']})")
        
    except FileNotFoundError:
        app_logger.error(f"錯誤: 找不到 CSV 檔案: {csv_path}")
        raise
    except Exception as e:
        app_logger.error(f"讀取 CSV 檔案時發生錯誤: {e}")
        raise
    
    return user_data

def load_users_from_manager(user_manager):
    """從 UserManager 載入用戶資料並隨機排序"""
    users = user_manager.get_all_users()
    user_data = []
    
    for user in users:
        user_data.append({
            'name': user['name'],
            'email': user['email']
        })
    
    random.shuffle(user_data)
    
    app_logger.info(f"從用戶管理器讀取了 {len(user_data)} 筆資料，已進行隨機排序")
    app_logger.info("隨機排序後的順序：")
    for i, user in enumerate(user_data, 1):
        app_logger.info(f"  {i}. {user['name']} ({user['email']})")
    
    return user_data

# ========== 瀏覽器操作工具 ==========
async def fill_basic_form_fields(page, name, email, company_name):
    """填寫基本表單欄位（公司、姓名、Email）"""
    try:
        # 選擇「其他」公司
        await page.wait_for_selector('div[data-qa^="option-其他"]', timeout=5000)
        await page.click('div[data-qa^="option-其他"]')
        app_logger.info("已選擇公司：其他")
        
        # 公司完整名稱
        await page.fill('input[placeholder="請填入文字"]', company_name)
        app_logger.info(f"已填入公司名稱：{company_name}")
        
        # 姓名
        await page.fill('input[placeholder="請填入文字"] >> nth=1', name)
        app_logger.info(f"已填入姓名：{name}")
        
        # Email
        await page.fill('input[type="email"]', email)
        app_logger.info(f"已填入 Email：{email}")
        
    except Exception as e:
        app_logger.error(f"填寫基本欄位時發生錯誤: {e}")
        raise

async def fill_agreement_checkbox(page):
    """勾選同意書"""
    try:
        await page.wait_for_selector('div[data-qa^="option-本人已詳閱"]', timeout=5000)
        await page.click('div[data-qa^="option-本人已詳閱"]')
        app_logger.info("已勾選同意書")
    except Exception as e:
        app_logger.error(f"勾選同意書時發生錯誤: {e}")
        raise

async def submit_form_with_confirmation(page, name):
    """送出表單並處理確認彈窗"""
    try:
        # 隨機等待
        wait_time = random.randint(1, 15)
        app_logger.info(f"{name} 的表單填寫完成，隨機等待 {wait_time} 秒後送出...")
        await asyncio.sleep(wait_time)
        
        # 送出表單
        app_logger.info(f"正在送出 {name} 的表單...")
        submit_selectors = [
            'button:has-text("送出")',
            'button[type="submit"]',
            'input[type="submit"]'
        ]
        
        submitted = False
        for selector in submit_selectors:
            try:
                await page.click(selector)
                submitted = True
                break
            except:
                continue
        
        if not submitted:
            raise Exception("找不到送出按鈕")
        
        # 處理確認彈窗
        return await handle_confirmation_popup(page, name)
        
    except Exception as e:
        app_logger.error(f"送出表單時發生錯誤: {e}")
        return False

async def handle_confirmation_popup(page, name):
    """處理確認彈窗"""
    try:
        # 嘗試常見的確認按鈕文字
        confirm_button_texts = ["確定送出", "確定", "確認", "送出", "提交"]
        button_found = False
        
        for button_text in confirm_button_texts:
            try:
                await page.wait_for_selector(f'button:has-text("{button_text}")', timeout=2000)
                await page.click(f'button:has-text("{button_text}")')
                app_logger.info(f"彈窗已出現，點擊了 '{button_text}' 按鈕")
                button_found = True
                break
            except:
                continue
        
        if not button_found:
            # 嘗試找彈窗容器中的按鈕
            popup_selectors = [
                '[role="dialog"] button',
                '.modal button', 
                '.popup button',
                '[class*="modal"] button',
                '[class*="dialog"] button'
            ]
            
            for selector in popup_selectors:
                try:
                    buttons = await page.locator(selector).all()
                    if len(buttons) >= 2:
                        await buttons[-1].click()
                        app_logger.info(f"點擊了彈窗中的確認按鈕")
                        button_found = True
                        break
                except:
                    continue
        
        if button_found:
            app_logger.info(f"{name} 的表單已確認送出")
            await asyncio.sleep(3)
            return True
        else:
            app_logger.info(f"警告: 無法找到確認按鈕，表單可能未完全送出")
            return False
            
    except Exception as e:
        app_logger.error(f"處理確認彈窗時發生錯誤: {e}")
        return False

# ========== 通用填表函數 ==========
async def fill_form_with_cache_check(url, name, email, company_name, cache_manager, custom_fill_func=None):
    """
    通用的填表函數，包含快取檢查
    
    Args:
        url: 表單網址
        name: 姓名
        email: Email
        company_name: 公司名稱
        cache_manager: 快取管理器實例
        custom_fill_func: 自定義填表函數（可選）
    """
    # 檢查是否已經成功提交過
    submitted, timestamp = cache_manager.is_user_submitted(url, name, email)
    if submitted:
        app_logger.info(f"⏭️  {name} ({email}) 已於 {timestamp} 成功提交過表單，跳過")
        return
    
    app_logger.info(f"📝 {name} 尚未提交或上次提交失敗，開始填寫表單...")
    
    async with async_playwright() as p:
        # 增加重試機制，以應對網路不穩或頁面載入慢的問題
        max_retries = 2
        for attempt in range(max_retries):
            browser = None
            try:
                browser = await p.chromium.launch(headless=False)
                page = await browser.new_page()
                
                await page.goto(url, wait_until="domcontentloaded", timeout=20000)
                await page.wait_for_timeout(2500) # 給予頁面上的 JS 一些載入時間
                app_logger.info(f"第 {attempt + 1} 次嘗試：開始填寫 {name} 的表單...")

                # 填寫基本欄位
                await fill_basic_form_fields(page, name, email, company_name)
                
                # 如果有自定義填表函數，執行它
                if custom_fill_func:
                    await custom_fill_func(page, name)
                
                # 勾選同意書
                await fill_agreement_checkbox(page)
                
                # 送出表單
                success = await submit_form_with_confirmation(page, name)
                
                # **核心修改點：只有在成功提交後才記錄日誌**
                if success:
                    app_logger.info(f"✅ {name} 的表單已成功提交。")
                    cache_manager.log_user_submission(url, name, email, success=True)
                    # 成功後就跳出重試循環
                    break 
                else:
                    app_logger.warning(f"⚠️ {name} 的表單提交未確認成功。")
                    # 如果不是最後一次重試，則準備下一次重試
                    if attempt < max_retries - 1:
                         app_logger.warning(f"準備進行下一次重試...")
                    else:
                         app_logger.error(f"❌ {name} 的表單在所有重試後仍提交失敗。將不會記錄為成功提交。")
                
            except Exception as e:
                app_logger.error(f"❌ {name} 的表單填寫過程中發生錯誤 (第 {attempt + 1} 次嘗試): {e}")
                # 如果不是最後一次重試，則等待後重試
                if attempt < max_retries - 1:
                    app_logger.warning("等待 5 秒後重試...")
                    await asyncio.sleep(5)
                else:
                    # 所有重試都失敗了
                    app_logger.error(f"❌ {name} 的表單在所有重試後均失敗。將不會記錄為成功提交。")
            finally:
                if browser:
                    await browser.close()

# ========== 批次處理函數 ==========
async def batch_process_forms(url, csv_path, company_name, cache_manager, custom_fill_func=None):
    """
    批次處理表單 - 兼容舊版本，仍支援 CSV 路徑
    
    Args:
        url: 表單網址
        csv_path: CSV 檔案路徑（保持兼容性）
        company_name: 公司名稱
        cache_manager: 快取管理器實例
        custom_fill_func: 自定義填表函數（可選）
    """
    app_logger.info("📋 讀取 CSV 資料並隨機排序...")
    user_data_list = load_and_shuffle_csv_data(csv_path)

    app_logger.info("🚀 開始批次填寫表單（檢查提交狀態）...")
    tasks = []
    for user_data in user_data_list:
        tasks.append(
            fill_form_with_cache_check(
                url, 
                user_data['name'], 
                user_data['email'], 
                company_name, 
                cache_manager, 
                custom_fill_func
            )
        )
    
    app_logger.info(f"準備處理 {len(tasks)} 個使用者的表單...")
    await asyncio.gather(*tasks)
    
    app_logger.info("✅ 所有表單處理完成！")

async def batch_process_forms_from_manager(url, user_manager, company_name, cache_manager, custom_fill_func=None):
    """
    批次處理表單 - 使用 UserManager
    
    Args:
        url: 表單網址
        user_manager: 用戶管理器實例
        company_name: 公司名稱
        cache_manager: 快取管理器實例
        custom_fill_func: 自定義填表函數（可選）
    """
    app_logger.info("📋 從用戶管理器讀取資料並隨機排序...")
    user_data_list = load_users_from_manager(user_manager)

    if not user_data_list:
        app_logger.warning("❌ 沒有用戶資料可以處理")
        return

    app_logger.info("🚀 開始批次填寫表單（檢查提交狀態）...")
    tasks = []
    for user_data in user_data_list:
        tasks.append(
            fill_form_with_cache_check(
                url, 
                user_data['name'], 
                user_data['email'], 
                company_name, 
                cache_manager, 
                custom_fill_func
            )
        )
    
    app_logger.info(f"準備處理 {len(tasks)} 個使用者的表單...")
    await asyncio.gather(*tasks)
    
    app_logger.info("✅ 所有表單處理完成！")

# ========== 單一表單處理函數 ==========
async def process_single_form(url, name, email, company_name, cache_manager, custom_fill_func=None):
    """
    處理單一表單
    
    Args:
        url: 表單網址
        name: 姓名
        email: Email
        company_name: 公司名稱
        cache_manager: 快取管理器實例
        custom_fill_func: 自定義填表函數（可選）
    """
    await fill_form_with_cache_check(
        url=url,
        name=name,
        email=email,
        company_name=company_name,
        cache_manager=cache_manager,
        custom_fill_func=custom_fill_func
    )