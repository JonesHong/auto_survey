# task_runner.py
import asyncio
import sys
import json
import argparse

# 這裡導入您真正的核心邏輯
# 假設這些檔案和函數都存在且可以被導入
from src.utils.logger_manager import app_logger
from src.app.auto_attendance import run_attendance_automation
from src.app.auto_quiz import run_quiz_automation
from util.survey_utils import CacheManager, fill_form_with_cache_check

# 導入測驗相關的輔助函數
from src.app.auto_quiz import (
    extract_survey_data_with_cache, 
    get_answer_by_gpt_with_cache, 
    fill_quiz_questions, 
    QuizCacheManager
)

async def run_personal_quiz_task(url, name, email, company_name):
    """專門處理個人測驗的異步函數"""
    app_logger.info(f"\n子進程：開始處理 {name} 的測驗...")
    
    quiz_cache_manager = QuizCacheManager()
    
    all_qa, option_texts = await extract_survey_data_with_cache(url, quiz_cache_manager)
    answers = get_answer_by_gpt_with_cache(url, all_qa, quiz_cache_manager)
    
    async def custom_quiz_fill(page, name):
        await fill_quiz_questions(page, name, answers, option_texts)
    
    await fill_form_with_cache_check(
        url=url,
        name=name,
        email=email,
        company_name=company_name,
        cache_manager=quiz_cache_manager,
        custom_fill_func=custom_quiz_fill
    )
    app_logger.info(f"\n子進程：{name} 的測驗任務執行完畢。")

async def run_personal_attendance_task(url, name, email, company_name):
    """專門處理個人簽到的異步函數"""
    app_logger.info(f"\n子進程：開始處理 {name} 的簽到...")
    cache_manager = CacheManager()
    await fill_form_with_cache_check(
        url=url,
        name=name,
        email=email,
        company_name=company_name,
        cache_manager=cache_manager,
        custom_fill_func=None
    )
    app_logger.info(f"\n子進程：{name} 的簽到任務執行完畢。")

async def main():
    parser = argparse.ArgumentParser(description="Playwright Task Runner")
    parser.add_argument("task_type", type=str, help="任務類型: 'batch_attendance', 'batch_quiz', 'personal_attendance', 'personal_quiz'")
    parser.add_argument("--url", type=str, help="表單 URL")
    parser.add_argument("--personal_info", type=str, help="JSON 格式的個人資訊字符串")

    args = parser.parse_args()

    app_logger.info(f"子進程已啟動，執行任務：{args.task_type}")

    try:
        if args.task_type == "batch_attendance":
            await run_attendance_automation(args.url)
        elif args.task_type == "batch_quiz":
            await run_quiz_automation(args.url)
        elif args.task_type == "personal_attendance":
            info = json.loads(args.personal_info)
            await run_personal_attendance_task(args.url, info['name'], info['email'], info['company_name'])
        elif args.task_type == "personal_quiz":
            info = json.loads(args.personal_info)
            await run_personal_quiz_task(args.url, info['name'], info['email'], info['company_name'])
        else:
            app_logger.error(f"錯誤：未知的任務類型 '{args.task_type}'", file=sys.stderr)
            sys.exit(1)
            
        app_logger.info(f"子進程任務 {args.task_type} 成功完成。")

    except Exception as e:
        app_logger.error(f"子進程執行任務 {args.task_type} 時發生錯誤: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # 在 Windows 上，ProactorEventLoop 是必要的，以支援子進程
    # 但 asyncio.run() 會自動為我們處理好事件循環的選擇和管理
    # 所以通常不需要手動設置
    if sys.platform == "win32":
        # 如果 asyncio.run() 仍然有問題，可以取消註解這行來強制使用
        # asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        pass
    
    asyncio.run(main())