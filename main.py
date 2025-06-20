# main.py
import argparse
import asyncio

# 從你的腳本中導入重構後的函式
from src.utils.logger_manager import app_logger
from src.app.auto_attendance import run_attendance_automation
from src.app.auto_quiz import run_quiz_automation

def get_mandatory_input(prompt_message: str) -> str:
    """
    重複提示使用者，直到輸入非空字串為止。

    Args:
        prompt_message (str): 顯示給使用者的提示訊息。

    Returns:
        str: 使用者輸入的非空字串。
    """
    while True:
        user_input = input(prompt_message).strip()
        if user_input:
            return user_input
        else:
            # 如果使用者只按 Enter，提示錯誤並重新要求輸入
            app_logger.remove("❌ 輸入不可為空，請重新輸入。")

async def main():
    """
    主程式進入點，處理使用者輸入並分派任務。
    """
    parser = argparse.ArgumentParser(
        description="自動化問卷簽到與測驗系統。",
        formatter_class=argparse.RawTextHelpFormatter # 保持換行格式
    )
    parser.add_argument(
        '--attend_url', 
        type=str, 
        help="簽到問卷的網址。"
    )
    parser.add_argument(
        '--quiz_url', 
        type=str, 
        help="測驗問卷的網址。"
    )
    # 新增一個參數，讓使用者可以選擇只執行一個任務
    parser.add_argument(
        '--task',
        type=str,
        choices=['attend', 'quiz', 'all'],
        help="指定要執行的任務：'attend' (僅簽到), 'quiz' (僅測驗), 'all' (兩者皆執行)。"
    )
    args = parser.parse_args()

    # 從參數或互動式輸入獲取 URL
    attend_url = args.attend_url
    quiz_url = args.quiz_url
    task_to_run = args.task

    # 如果沒有透過 --task 參數指定任務，則預設為全部執行
    if not task_to_run:
        task_to_run = 'all'

    # --- 處理簽到 URL ---
    run_attend = task_to_run in ['attend', 'all']
    if run_attend and not attend_url:
        # 如果需要執行簽到，且沒有提供 attend_url 參數，則要求使用者輸入 (必填)
        attend_url = get_mandatory_input("👉 請輸入 [簽到] 問卷的網址 (此項必填): ")

    # --- 處理測驗 URL ---
    run_quiz = task_to_run in ['quiz', 'all']
    if run_quiz and not quiz_url:
        # 如果需要執行測驗，且沒有提供 quiz_url 參數，則要求使用者輸入 (必填)
        quiz_url = get_mandatory_input("👉 請輸入 [測驗] 問卷的網址 (此項必填): ")


    # --- 根據提供的 URL 執行對應的任務 ---
    if run_attend and attend_url:
        app_logger.info("\n" + "="*20 + " 🚀 開始執行簽到流程 " + "="*20)
        await run_attendance_automation(attend_url)
        app_logger.info("="*20 + " ✅ 簽到流程執行完畢 " + "="*20 + "\n")
    elif run_attend and not attend_url:
        app_logger.warning("\n⏩ 未提供簽到 URL，已跳過簽到流程。\n")


    if run_quiz and quiz_url:
        app_logger.info("\n" + "="*20 + " 🚀 開始執行測驗流程 " + "="*20)
        await run_quiz_automation(quiz_url)
        app_logger.info("="*20 + " ✅ 測驗流程執行完畢 " + "="*20 + "\n")
    elif run_quiz and not quiz_url:
        app_logger.warning("\n⏩ 未提供測驗 URL，已跳過測驗流程。\n")
        
    app_logger.info("🎉 所有指定任務已完成！")

if __name__ == "__main__":
    asyncio.run(main())