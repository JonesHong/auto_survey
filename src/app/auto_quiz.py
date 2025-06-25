"""
自動問卷填寫程式 - 簡化版
遵循 KISS 原則：Keep It Simple, Stupid
"""
from openai import OpenAI
import json
import re
import asyncio
import random
from datetime import datetime
from src.utils.survey_utils import CacheManager, batch_process_forms, batch_process_forms_from_manager
from playwright.async_api import async_playwright

from src.config.manager import ConfigManager
from src.utils.logger_manager import app_logger

config = ConfigManager()

# 配置
OPENAI_API_KEY = config.system.openai_api_key
CSV_PATH = config.system.csv_path
openai_model = config.system.openai_model
company_name = config.system.company_name

class QuizCacheManager(CacheManager):
    """問卷專用的快取管理器"""
    
    def load_quiz_analysis(self, url):
        """載入問卷分析結果"""
        data = self.load_json_file("quiz_analysis.json")
        url_hash = self.get_url_hash(url)
        return data.get(url_hash)
    
    def save_quiz_analysis(self, url, questions, answers):
        """儲存問卷分析結果 - 只存必要資訊"""
        data = self.load_json_file("quiz_analysis.json")
        url_hash = self.get_url_hash(url)
        data[url_hash] = {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "questions": questions,  # LLM識別的題目和選項
            "answers": answers       # LLM給出的答案
        }
        self.save_json_file("quiz_analysis.json", data)

async def extract_html_content(url, cache_manager):
    """抓取並清理HTML內容"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(url)
        await page.wait_for_timeout(3000)
        
        # 獲取純文字內容
        body_content = await page.locator('body').text_content()
        await browser.close()
        
        # 簡單清理
        cleaned = re.sub(r'\s+', ' ', body_content).strip()
        app_logger.info(f"抓取完成，內容長度: {len(cleaned)}")
        return cleaned

def analyze_quiz_with_llm(url, html_content, cache_manager):
    """使用LLM分析問卷"""
    # 檢查快取
    cached = cache_manager.load_quiz_analysis(url)
    if cached:
        app_logger.info("✅ 從快取載入分析結果")
        return cached["questions"], cached["answers"]
    
    app_logger.info("🤖 開始LLM分析...")
    
    client = OpenAI(api_key=OPENAI_API_KEY)
    
    # 步驟1: 提取題目和選項
    analysis_prompt = f"""
請分析HTML內容，提取測驗題目（忽略公司選擇、姓名、Email、同意書等）。

以JSON格式回傳：
{{
  "questions": [
    {{
      "id": 5,  # 題目ID，從5開始
      "question": "題目內容",
      "options": [
        {{"letter": "A", "text": "選項A"}},
        {{"letter": "B", "text": "選項B"}},
        {{"letter": "C", "text": "選項C"}},
        {{"letter": "D", "text": "選項D"}}
      ]
    }}
  ]
}}

HTML內容：{html_content}
"""
    
    # 獲取題目結構
    response1 = client.chat.completions.create(
        model=openai_model,
        messages=[{"role": "user", "content": analysis_prompt}]
    )
    
    # 清理並解析JSON
    result = response1.choices[0].message.content
    result = re.sub(r'```json|```', '', result).strip()
    
    try:
        questions = json.loads(result)["questions"]
        app_logger.info(f"✅ 識別出 {len(questions)} 道測驗題目")
    except:
        raise ValueError("無法解析LLM回應")
    
    # 步驟2: 獲取答案
    questions_text = ""
    for q in questions:
        questions_text += f"{q['id']}. {q['question']}\n"
        for opt in q['options']:
            questions_text += f"{opt['letter']}. {opt['text']}\n"
        questions_text += "\n"
    
    answer_prompt = f"""
請回答以下測驗題目，以JSON格式回傳答案(題號從5開始，只需填寫選項字母)：
{{"5": "A", "6": "B", "7": "C", ...}}

題目：
{questions_text}
"""
    
    response2 = client.chat.completions.create(
        model=openai_model,
        messages=[{"role": "user", "content": answer_prompt}]
    )
    
    # 解析答案
    answer_result = response2.choices[0].message.content
    answer_result = re.sub(r'```json|```', '', answer_result).strip()
    
    try:
        answers = json.loads(answer_result)
        app_logger.info(f"✅ 獲得 {len(answers)} 道題目的答案")
    except:
        raise ValueError("無法解析LLM答案")
    
    # 儲存到快取
    cache_manager.save_quiz_analysis(url, questions, answers)
    
    return questions, answers

async def fill_quiz_simple(page, questions, answers):
    """簡單的問卷填寫邏輯"""
    app_logger.info("開始填寫測驗題目...")
    
    for question in questions:
        q_id = str(question["id"])
        if q_id not in answers:
            continue
            
        selected_letter = answers[q_id]
        
        # 找到選項文字
        option_text = None
        for opt in question["options"]:
            if opt["letter"] == selected_letter:
                option_text = opt["text"]
                break
        
        if not option_text:
            continue
        
        # 嘗試點擊選項
        success = await click_option_simple(page, q_id, selected_letter, option_text)
        
        if success:
            app_logger.info(f"✅ 題目 {q_id} 選擇 {selected_letter}: {option_text}")
            await page.wait_for_timeout(500)  # 短暫延遲
        else:
            app_logger.warning(f"❌ 題目 {q_id} 點擊失敗: {option_text}")

async def click_option_simple(page, question_id, letter, option_text):
    """簡單的選項點擊策略"""
    
    # 策略1: 使用XPATH（最精確）
    try:
        # 根據真實XPATH規律：題目5對應div[6]，題目7對應div[8]，題目9對應div[10]
        question_div = int(question_id) + 1  # 題目N對應div[N+1]
        option_div = ord(letter) - ord('A') + 1  # A=1, B=2, C=3, D=4
        
        xpath = f"//div[1]/div[{question_div}]/div/div[2]/div[2]/div[2]/div/div[{option_div}]//span[2]"
        
        app_logger.debug(f"嘗試XPATH: {xpath} (題目{question_id}, 選項{letter})")
        
        element = page.locator(f"xpath={xpath}")
        if await element.count() > 0:
            await element.click(timeout=3000)
            app_logger.debug(f"✅ XPATH點擊成功")
            return True
    except Exception as e:
        app_logger.debug(f"XPATH策略失敗: {e}")
        pass
    
    # 策略2: data-qa選擇器（如果唯一）
    try:
        selector = f'[data-qa="option-{option_text}"]'
        elements = await page.locator(selector).all()
        
        if len(elements) == 1:  # 只有唯一元素才點擊
            await elements[0].click(timeout=2000)
            return True
    except:
        pass
    
    # 策略3: 文字匹配（如果唯一）
    try:
        elements = await page.locator(f'text="{option_text}"').all()
        
        if len(elements) == 1:  # 只有唯一元素才點擊
            await elements[0].click(timeout=2000)
            return True
    except:
        pass
    
    return False

async def fill_basic_fields(page, name, email, company_name):
    """填寫基本欄位"""
    try:
        # 選擇「其他」公司
        await page.click('[data-qa="option-其他"]')
        app_logger.info("已選擇公司：其他")
        
        # 填入公司名稱（第一個文字輸入框）
        await page.fill('input[placeholder="請填入文字"]', company_name)
        app_logger.info(f"已填入公司名稱：{company_name}")
        
        # 填入姓名（第二個文字輸入框）
        await page.fill('input[placeholder="請填入文字"] >> nth=1', name)
        app_logger.info(f"已填入姓名：{name}")
        
        # 填入Email
        await page.fill('input[type="email"]', email)
        app_logger.info(f"已填入Email：{email}")
        
        # 勾選同意書
        await page.click('[data-qa*="本人已詳閱"]')
        app_logger.info("已勾選同意書")
        
    except Exception as e:
        app_logger.error(f"填寫基本欄位失敗: {e}")
        raise

async def submit_form_simple(page, name):
    """提交表單並等待成績顯示"""
    try:
        # 隨機等待
        wait_time = random.randint(0, 5)
        app_logger.info(f"等待 {wait_time} 秒後提交...")
        await asyncio.sleep(wait_time)
        
        # 點擊送出
        await page.click('button:has-text("送出")')
        app_logger.info("已點擊送出按鈕")
        
        # 等待並處理確認彈窗
        await page.wait_for_timeout(1000)
        
        # 嘗試點擊確認按鈕
        confirm_selectors = ['button:has-text("確定")', 'button:has-text("確認")', 'button:has-text("確定送出")']
        
        confirmed = False
        for selector in confirm_selectors:
            try:
                await page.click(selector, timeout=3000)
                app_logger.info(f"已點擊確認按鈕: {selector}")
                confirmed = True
                break
            except:
                continue
        
        if not confirmed:
            app_logger.warning("未找到確認按鈕，嘗試繼續等待成績...")
        
        # 等待成績顯示
        score = await wait_for_score_display(page, name)
        
        return True, score
        
    except Exception as e:
        app_logger.error(f"提交表單失敗: {e}")
        return False, None

async def wait_for_score_display(page, name):
    """等待並提取成績顯示"""
    app_logger.info(f"等待 {name} 的成績顯示...")
    
    try:
        # 等待成績文字出現（最多等待30秒）
        score_selectors = [
            'text="本次課後測驗，成績為"',
            'text*="本次課後測驗"',
            'text*="成績為"',
            'text*="分數"'
        ]
        
        score_found = False
        for selector in score_selectors:
            try:
                await page.wait_for_selector(selector, timeout=10000)
                score_found = True
                app_logger.info("✅ 檢測到成績顯示")
                break
            except:
                continue
        
        if not score_found:
            app_logger.warning("未檢測到成績顯示，嘗試提取頁面內容...")
        
        # 提取成績
        score = await extract_score_from_page(page)
        
        if score:
            app_logger.info(f"🎉 {name} 的測驗成績：{score} 分")
            
            # 等待用戶確認看到成績（額外等待幾秒）
            await page.wait_for_timeout(3000)
            app_logger.info("成績顯示完成，準備關閉瀏覽器")
        else:
            app_logger.warning("無法提取到具體成績")
        
        await page.wait_for_timeout(1000)
        return score
        
    except Exception as e:
        app_logger.error(f"等待成績顯示時發生錯誤: {e}")
        return None

async def extract_score_from_page(page):
    """從頁面提取成績"""
    try:
        # 獲取頁面文字內容
        page_text = await page.locator('body').text_content()
        
        if not page_text:
            return None
        
        # 使用正則表達式提取成績
        patterns = [
            r'本次課後測驗，成績為\s*(\d+)',
            r'成績為\s*(\d+)',
            r'分數：\s*(\d+)',
            r'得分：\s*(\d+)',
            r'您的成績：\s*(\d+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, page_text)
            if match:
                score = int(match.group(1))
                app_logger.info(f"成功提取成績：{score} 分")
                return score
        
        # 如果正則表達式找不到，嘗試查找包含數字的成績相關文字
        lines = page_text.split('\n')
        for line in lines:
            line = line.strip()
            if '成績' in line or '分數' in line:
                # 提取該行中的數字
                numbers = re.findall(r'\d+', line)
                if numbers:
                    # 取最可能是分數的數字（通常是0-100之間）
                    for num in numbers:
                        score = int(num)
                        if 0 <= score <= 100:
                            app_logger.info(f"從文字中提取成績：{score} 分")
                            return score
        
        app_logger.warning("未能從頁面提取到成績")
        return None
        
    except Exception as e:
        app_logger.error(f"提取成績時發生錯誤: {e}")
        return None

async def process_single_quiz(url, name, email, company_name, cache_manager):
    """處理單個問卷 - 包含成績記錄"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            await page.goto(url)
            await page.wait_for_timeout(3000)
            
            # 檢查是否已經提交過
            submitted, timestamp = cache_manager.is_user_submitted(url, name, email)
            if submitted:
                app_logger.info(f"⏭️ {name} ({email}) 已於 {timestamp} 成功提交過表單，跳過")
                return
            
            # 填寫基本欄位
            await fill_basic_fields(page, name, email, company_name)
            
            # 獲取問卷分析
            html_content = await extract_html_content(url, cache_manager)
            questions, answers = analyze_quiz_with_llm(url, html_content, cache_manager)
            
            # 填寫測驗題目
            await fill_quiz_simple(page, questions, answers)
            
            # 提交表單並獲取成績
            success, score = await submit_form_simple(page, name)
            
            if success:
                app_logger.info(f"✅ {name} 的問卷填寫完成")
                # 記錄提交成功，包含成績
                cache_manager.log_user_submission_with_score(url, name, email, success=True, score=score)
            else:
                app_logger.warning(f"⚠️ {name} 的問卷提交失敗")
                cache_manager.log_user_submission_with_score(url, name, email, success=False, score=None)
                
        except Exception as e:
            app_logger.error(f"{name} 的問卷處理失敗: {e}")
            cache_manager.log_user_submission_with_score(url, name, email, success=False, score=None)
            
        finally:
            await browser.close()

# 擴展QuizCacheManager以支持成績記錄
class QuizCacheManager(CacheManager):
    """問卷專用的快取管理器"""
    
    def load_quiz_analysis(self, url):
        """載入問卷分析結果"""
        data = self.load_json_file("quiz_analysis.json")
        url_hash = self.get_url_hash(url)
        return data.get(url_hash)
    
    def save_quiz_analysis(self, url, questions, answers):
        """儲存問卷分析結果 - 只存必要資訊"""
        data = self.load_json_file("quiz_analysis.json")
        url_hash = self.get_url_hash(url)
        data[url_hash] = {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "questions": questions,  # LLM識別的題目和選項
            "answers": answers       # LLM給出的答案
        }
        self.save_json_file("quiz_analysis.json", data)
    
    def log_user_submission_with_score(self, url, name, email, success=True, score=None):
        """記錄使用者提交狀態，包含成績"""
        data = self.load_json_file("submission_log.json")
        url_hash = self.get_url_hash(url)
        
        if url_hash not in data:
            data[url_hash] = {
                "url": url,
                "submissions": []
            }
        
        submission_data = {
            "name": name,
            "email": email,
            "timestamp": datetime.now().isoformat(),
            "success": success
        }
        
        # 如果有成績，則記錄
        if score is not None:
            submission_data["score"] = score
            app_logger.info(f"📊 記錄 {name} 的測驗成績：{score} 分")
        
        data[url_hash]["submissions"].append(submission_data)
        self.save_json_file("submission_log.json", data)

# 創建專用的問卷填寫函數
async def fill_quiz_form_complete(url, name, email, company_name, cache_manager):
    """完整的問卷填寫流程，包含成績記錄"""
    await process_single_quiz(url, name, email, company_name, cache_manager)

async def run_quiz_automation(survey_url: str):
    """主執行函數 - 使用專用的問卷填寫流程"""
    app_logger.info(f"=== 開始問卷自動化：{survey_url} ===")
    
    cache_manager = QuizCacheManager()
    
    # 先分析問卷結構
    app_logger.info("分析問卷結構...")
    html_content = await extract_html_content(survey_url, cache_manager)
    questions, answers = analyze_quiz_with_llm(survey_url, html_content, cache_manager)
    
    app_logger.info(f"問卷分析完成：{len(questions)} 道題目")
    app_logger.info(f"LLM答案：{answers}")
    
    # 獲取用戶列表並批次處理
    try:
        from server import user_manager
        users = user_manager.get_all_users()
        app_logger.info(f"從用戶管理器獲取 {len(users)} 位用戶")
    except ImportError:
        # 回退到CSV模式
        import csv
        users = []
        try:
            with open(CSV_PATH, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                users = [{'name': row['name'], 'email': row['email']} for row in reader]
            app_logger.info(f"從CSV獲取 {len(users)} 位用戶")
        except Exception as e:
            app_logger.error(f"無法讀取用戶資料: {e}")
            return
    
    if not users:
        app_logger.warning("沒有用戶資料可處理")
        return
    
    # 隨機排序用戶
    import random
    random.shuffle(users)
    app_logger.info("用戶順序已隨機排列")
    
    # 批次處理每個用戶
    for i, user in enumerate(users, 1):
        try:
            app_logger.info(f"\n=== 處理第 {i}/{len(users)} 位用戶：{user['name']} ===")
            await fill_quiz_form_complete(
                url=survey_url,
                name=user['name'],
                email=user['email'],
                company_name=company_name,
                cache_manager=cache_manager
            )
            
            # 用戶間隨機間隔
            if i < len(users):  # 不是最後一個用戶
                interval = random.randint(1, 4)
                app_logger.info(f"⏳ 等待 {interval} 秒後處理下一位用戶...")
                await asyncio.sleep(interval)
                
        except Exception as e:
            app_logger.error(f"處理 {user['name']} 時發生錯誤: {e}")
            continue
    
    app_logger.info("=== 問卷自動化完成 ===")
    
    # 顯示成績統計
    await show_score_summary(survey_url, cache_manager)

async def show_score_summary(url, cache_manager):
    """顯示成績統計摘要"""
    try:
        data = cache_manager.load_json_file("submission_log.json")
        url_hash = cache_manager.get_url_hash(url)
        
        if url_hash not in data:
            app_logger.info("📊 無提交記錄")
            return
        
        submissions = data[url_hash]["submissions"]
        successful_submissions = [s for s in submissions if s.get("success", False)]
        
        app_logger.info(f"\n📊 === 成績統計摘要 ===")
        app_logger.info(f"總提交人數: {len(submissions)}")
        app_logger.info(f"成功提交人數: {len(successful_submissions)}")
        
        # 統計成績分布
        scores = [s.get("score") for s in successful_submissions if s.get("score") is not None]
        
        if scores:
            app_logger.info(f"有成績記錄人數: {len(scores)}")
            app_logger.info(f"平均成績: {sum(scores)/len(scores):.1f} 分")
            app_logger.info(f"最高成績: {max(scores)} 分")
            app_logger.info(f"最低成績: {min(scores)} 分")
            
            # 通過率統計 (≥80分)
            passed = [s for s in scores if s >= 80]
            app_logger.info(f"通過人數 (≥80分): {len(passed)}/{len(scores)} ({len(passed)/len(scores)*100:.1f}%)")
            
            # 列出所有成績
            app_logger.info("\n📋 詳細成績列表:")
            for submission in successful_submissions:
                if submission.get("score") is not None:
                    status = "✅通過" if submission["score"] >= 80 else "❌未通過"
                    app_logger.info(f"  {submission['name']}: {submission['score']} 分 {status}")
        else:
            app_logger.info("無成績記錄")
            
    except Exception as e:
        app_logger.error(f"生成成績統計時發生錯誤: {e}")

if __name__ == "__main__":
    DEFAULT_QUIZ_URL = "https://www.surveycake.com/s/XGbl0"
    asyncio.run(run_quiz_automation(DEFAULT_QUIZ_URL))