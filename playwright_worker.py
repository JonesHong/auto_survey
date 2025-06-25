# playwright_worker.py - 配合簡化版auto_quiz.py
import asyncio
import sys
import json
import argparse

# 導入核心邏輯
from src.utils.logger_manager import app_logger
from src.utils.survey_utils import CacheManager, fill_form_with_cache_check

async def run_personal_quiz_task(url, name, email, company_name):
    """個人測驗任務 - 支援成績記錄"""
    app_logger.info(f"\n子進程：開始處理 {name} 的測驗...")
    
    try:
        # 導入完整的問卷填寫函數
        from src.app.auto_quiz import fill_quiz_form_complete, QuizCacheManager
        
        quiz_cache_manager = QuizCacheManager()
        
        app_logger.info(f"開始為 {name} 執行完整的問卷填寫流程...")
        
        # 使用新的完整問卷填寫函數（包含成績記錄）
        await fill_quiz_form_complete(
            url=url,
            name=name,
            email=email,
            company_name=company_name,
            cache_manager=quiz_cache_manager
        )
        
        app_logger.info(f"\n子進程：{name} 的測驗任務執行完畢。")
        
    except Exception as e:
        app_logger.error(f"❌ {name} 的測驗處理失敗: {e}")
        import traceback
        traceback.print_exc()
        raise

async def run_personal_attendance_task(url, name, email, company_name):
    """個人簽到任務"""
    app_logger.info(f"\n子進程：開始處理 {name} 的簽到...")
    
    try:
        cache_manager = CacheManager()
        await fill_form_with_cache_check(
            url=url,
            name=name,
            email=email,
            company_name=company_name,
            cache_manager=cache_manager,
            custom_fill_func=None  # 簽到不需要自定義填表函數
        )
        app_logger.info(f"\n子進程：{name} 的簽到任務執行完畢。")
        
    except Exception as e:
        app_logger.error(f"❌ {name} 的簽到處理失敗: {e}")
        import traceback
        traceback.print_exc()
        raise

async def main():
    parser = argparse.ArgumentParser(description="Playwright Task Runner")
    parser.add_argument("task_type", type=str, 
                       help="任務類型: 'batch_attendance', 'batch_quiz', 'personal_attendance', 'personal_quiz'")
    parser.add_argument("--url", type=str, help="表單 URL")
    parser.add_argument("--personal_info", type=str, help="JSON 格式的個人資訊字符串")

    args = parser.parse_args()

    app_logger.info(f"子進程已啟動，執行任務：{args.task_type}")
    app_logger.info(f"目標 URL: {args.url}")

    try:
        if args.task_type == "batch_attendance":
            app_logger.info("開始執行批次簽到任務...")
            # 動態導入避免循環導入
            from src.app.auto_attendance import run_attendance_automation
            await run_attendance_automation(args.url)
            
        elif args.task_type == "batch_quiz":
            app_logger.info("開始執行批次測驗任務...")
            # 動態導入避免循環導入
            from src.app.auto_quiz import run_quiz_automation
            await run_quiz_automation(args.url)
            
        elif args.task_type == "personal_attendance":
            if not args.personal_info:
                raise ValueError("個人簽到任務需要提供 --personal_info 參數")
            
            info = json.loads(args.personal_info)
            required_fields = ['name', 'email', 'company_name']
            
            for field in required_fields:
                if field not in info:
                    raise ValueError(f"個人資訊缺少必要欄位: {field}")
            
            app_logger.info(f"個人簽到：{info['name']} ({info['email']}) - {info['company_name']}")
            await run_personal_attendance_task(
                args.url, 
                info['name'], 
                info['email'], 
                info['company_name']
            )
            
        elif args.task_type == "personal_quiz":
            if not args.personal_info:
                raise ValueError("個人測驗任務需要提供 --personal_info 參數")
            
            info = json.loads(args.personal_info)
            required_fields = ['name', 'email', 'company_name']
            
            for field in required_fields:
                if field not in info:
                    raise ValueError(f"個人資訊缺少必要欄位: {field}")
            
            app_logger.info(f"個人測驗：{info['name']} ({info['email']}) - {info['company_name']}")
            await run_personal_quiz_task(
                args.url, 
                info['name'], 
                info['email'], 
                info['company_name']
            )
            
        else:
            app_logger.error(f"錯誤：未知的任務類型 '{args.task_type}'")
            sys.exit(1)
            
        app_logger.info(f"✅ 子進程任務 {args.task_type} 成功完成。")

    except json.JSONDecodeError as e:
        app_logger.error(f"❌ JSON 解析錯誤: {e}")
        app_logger.error(f"原始個人資訊字符串: {args.personal_info}")
        sys.exit(1)
        
    except ValueError as e:
        app_logger.error(f"❌ 參數錯誤: {e}")
        sys.exit(1)
        
    except Exception as e:
        app_logger.error(f"❌ 子進程執行任務 {args.task_type} 時發生錯誤: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    # Windows 平台事件循環處理
    if sys.platform == "win32":
        pass
    
    asyncio.run(main())