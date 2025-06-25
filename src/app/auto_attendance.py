# auto_attendance.py

"""
自動簽到程式 - 重構版
使用共用模組，專注於簽到特有功能，並加入快取系統
"""
import asyncio
from src.utils.survey_utils import CacheManager, batch_process_forms, batch_process_forms_from_manager

from src.utils.logger_manager import app_logger
from src.config.manager import ConfigManager
config = ConfigManager()

# 配置 (從設定檔讀取，不再需要硬編碼 URL)
CSV_PATH = config.system.csv_path
company_name = config.system.company_name

# ========== 簽到專用填表函數 ==========
async def fill_attendance_form(page, name):
    """
    簽到表單的自定義填表邏輯
    由於簽到表單通常只需要填基本資料，這個函數可以是空的
    或者可以加入簽到特有的欄位處理
    """
    # 簽到表單通常只需要基本欄位（姓名、Email、公司、同意書）
    # 這些已經在 fill_basic_form_fields 和 fill_agreement_checkbox 中處理
    app_logger.info(f"{name} 的簽到表單特有邏輯處理完成")
    pass

# ========== 主流程函式 (可被外部呼叫) ==========
async def run_attendance_automation(survey_url: str):
    """
    執行自動簽到流程的主函式。

    Args:
        survey_url (str): 要處理的簽到問卷網址。
    """
    app_logger.info(f"=== 開始自動簽到流程（目標 URL: {survey_url}）===")
    
    # 初始化快取管理器
    cache_manager = CacheManager()
    
    # 嘗試使用新的用戶管理系統
    try:
        # 動態導入 UserManager（避免循環導入）
        import sys
        import os
        
        # 確保可以導入 server 模組
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        try:
            from server import user_manager
            app_logger.info("\n使用用戶管理系統進行批次簽到處理...")
            await batch_process_forms_from_manager(
                url=survey_url,
                user_manager=user_manager,
                company_name=company_name,
                cache_manager=cache_manager,
                custom_fill_func=fill_attendance_form
            )
        except ImportError:
            # 如果無法導入用戶管理器，回退到 CSV 模式
            app_logger.info("\n無法使用用戶管理系統，回退到 CSV 模式...")
            await batch_process_forms(
                url=survey_url,
                csv_path=CSV_PATH,
                company_name=company_name,
                cache_manager=cache_manager,
                custom_fill_func=fill_attendance_form
            )
    except Exception as e:
        app_logger.error(f"簽到處理過程中發生錯誤: {e}")
        # 回退到 CSV 模式
        app_logger.info("回退到 CSV 模式...")
        await batch_process_forms(
            url=survey_url,
            csv_path=CSV_PATH,
            company_name=company_name,
            cache_manager=cache_manager,
            custom_fill_func=fill_attendance_form
        )
    
    app_logger.info(f"\n=== 自動簽到完成！快取檔案位置: {cache_manager.cache_dir} ===")

# 這個區塊現在只用於獨立測試此檔案
if __name__ == "__main__":
    # 用於獨立測試此模組的預設 URL
    DEFAULT_ATTENDANCE_URL = "https://www.surveycake.com/s/oGmnK"
    app_logger.info(">> 正在以獨立模式執行 auto_attendance.py 進行測試...")
    asyncio.run(run_attendance_automation(DEFAULT_ATTENDANCE_URL))