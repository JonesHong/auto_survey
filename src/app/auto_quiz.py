# auto_quiz.py

"""
自動問卷填寫程式 - 重構版
使用共用模組，專注於問卷特有的 GPT 分析功能
"""
import openai
import json
import re
import asyncio
from datetime import datetime
from utils.survey_utils import CacheManager, batch_process_forms, batch_process_forms_from_manager
from playwright.async_api import async_playwright

from src.config.manager import ConfigManager
from src.utils.logger_manager import app_logger
config = ConfigManager()

# 配置 (從設定檔讀取，不再需要硬編碼 URL)
OPENAI_API_KEY = config.system.openai_api_key
CSV_PATH = config.system.csv_path
openai_model = config.system.openai_model
company_name = config.system.company_name

# ========== 問卷特有功能 ==========
def generate_option_letters(count):
    """動態生成選項字母 A, B, C, D, E, F, G, H..."""
    return [chr(ord('A') + i) for i in range(count)]

async def should_skip_question(q_title, question_container):
    """判斷是否應該跳過此題目（固定欄位）"""
    # 檢查題目文字關鍵字
    skip_keywords = ["公司", "友達", "達擎", "達運", "港務公司", "本人已詳閱", "同意", "個人資料", "交由"]
    if any(keyword in q_title for keyword in skip_keywords):
        return True
    
    # 檢查選項內容
    try:
        options = []
        for option_div in await question_container.locator('[data-qa^="option-"]').all():
            option_text = (await option_div.text_content()).strip()
            if option_text:
                options.append(option_text)
        
        # 檢查公司相關選項
        company_keywords = ["友達", "達擎", "達運", "港務公司", "其他"]
        company_count = sum(1 for option in options if any(keyword in option for keyword in company_keywords))
        if company_count >= 3:
            return True
        
        # 檢查同意書選項
        if any("本人已詳閱" in option or "同意" in option for option in options):
            return True
            
    except Exception:
        pass
    
    return False

class QuizCacheManager(CacheManager):
    """問卷專用的快取管理器"""
    
    def load_survey_data(self, url):
        """載入問卷資料"""
        data = self.load_json_file("survey_data.json")
        url_hash = self.get_url_hash(url)
        return data.get(url_hash)
    
    def save_survey_data(self, url, all_qa, option_texts):
        """儲存問卷資料"""
        data = self.load_json_file("survey_data.json")
        url_hash = self.get_url_hash(url)
        data[url_hash] = {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "all_qa": all_qa,
            "option_texts": option_texts
        }
        self.save_json_file("survey_data.json", data)
    
    def load_gpt_answers(self, url):
        """載入 GPT 答案"""
        data = self.load_json_file("gpt_answers.json")
        url_hash = self.get_url_hash(url)
        return data.get(url_hash)
    
    def save_gpt_answers(self, url, answers):
        """儲存 GPT 答案"""
        data = self.load_json_file("gpt_answers.json")
        url_hash = self.get_url_hash(url)
        data[url_hash] = {
            "url": url,
            "timestamp": datetime.now().isoformat(),
            "answers": answers
        }
        self.save_json_file("gpt_answers.json", data)

# ========== 問卷資料擷取 ==========
async def extract_survey_data_with_cache(url, cache_manager):
    """帶快取的問卷資料擷取"""
    cached_data = cache_manager.load_survey_data(url)
    if cached_data:
        app_logger.info("✅ 從快取載入問卷資料")
        return cached_data["all_qa"], cached_data["option_texts"]
    
    app_logger.info("🔄 快取中無資料，開始爬取問卷...")
    
    all_qa = ""
    option_texts = {}
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto(url)
        await page.wait_for_timeout(2500)
        
        question_containers = await page.locator('[aria-label="subject answer container"]').all()
        actual_question_idx = 0
        
        for qc in question_containers:
            q_title = (await qc.locator('div[class^="css-"]').first.text_content()).strip()
            
            if await should_skip_question(q_title, qc):
                app_logger.info(f"跳過題目: {q_title}")
                continue
                
            actual_question_idx += 1
            app_logger.info(f"處理題目 {actual_question_idx}: {q_title}")
            
            # 獲取選項
            options = []
            option_divs = await qc.locator('[data-qa^="option-"]').all()
            for option_div in option_divs:
                option_text = (await option_div.text_content()).strip()
                if option_text:
                    options.append(option_text)
            
            if options:
                opt_letters = generate_option_letters(len(options))
                
                # 為 GPT 準備題目文字
                opt_lines = [f"{opt_letters[i]}. {opt}" for i, opt in enumerate(options)]
                opt_text = "\n".join(opt_lines)
                all_qa += f"{actual_question_idx}. {q_title}\n{opt_text}\n\n"
                
                # 為自動填寫準備選項對應表
                question_options = {opt_letters[i]: option_text for i, option_text in enumerate(options) if i < len(opt_letters)}
                option_texts[str(actual_question_idx)] = question_options
        
        await browser.close()
    
    cache_manager.save_survey_data(url, all_qa, option_texts)
    app_logger.info("💾 問卷資料已儲存到快取")
    
    return all_qa, option_texts

# ========== GPT 分析 ==========
def get_answer_by_gpt_with_cache(url, all_qa, cache_manager):
    """帶快取的 GPT 答案獲取"""
    cached_answers = cache_manager.load_gpt_answers(url)
    if cached_answers:
        app_logger.info("✅ 從快取載入 GPT 答案")
        return cached_answers["answers"]
    
    app_logger.info("🤖 快取中無 GPT 答案，開始分析...")
    
    openai.api_key = OPENAI_API_KEY
    
    # 第一步：獲取答案
    prompt = f"請針對以下題目選出正確答案，只要回答『題號: 選項字母』即可（不用解釋）：\n{all_qa}"
    resp = openai.ChatCompletion.create(
        model=openai_model,
        messages=[{"role": "user", "content": prompt}]
    )
    gpt_answer_text = resp['choices'][0]['message']['content']
    openai.ChatCompletion.update()
    # 第二步：轉換為 JSON
    prompt2 = f"將下列題號與答案字母整理成 JSON 格式（只輸出 JSON，key 為題號，value 為選項字母）:\n{gpt_answer_text}"
    resp2 = openai.ChatCompletion.create(
        model=openai_model,
        messages=[{"role": "user", "content": prompt2}]
    )
    json_text = resp2['choices'][0]['message']['content']
    
    try:
        json_text = re.sub(r"^```json|```$", "", json_text, flags=re.MULTILINE).strip()
        answers = json.loads(json_text)
    except Exception:
        app_logger.error("JSON parse error:", json_text)
        raise
    
    cache_manager.save_gpt_answers(url, answers)
    app_logger.info("💾 GPT 答案已儲存到快取")
    
    return answers

# ========== 問卷專用填表函數 ==========
async def fill_quiz_questions(page, name, answers, option_texts):
    """填寫問卷選擇題"""
    question_containers = await page.locator('[aria-label="subject answer container"]').all()
    actual_question_idx = 0
    
    for qc in question_containers:
        q_title = (await qc.locator('div[class^="css-"]').first.text_content()).strip()
        
        if await should_skip_question(q_title, qc):
            continue
            
        actual_question_idx += 1
        q_num = str(actual_question_idx)
        
        if q_num in answers and q_num in option_texts:
            option_letter = answers[q_num]
            if option_letter in option_texts[q_num]:
                option_content = option_texts[q_num][option_letter]
                selector = f'div[data-qa^="option-{option_content}"]'
                try:
                    await page.wait_for_selector(selector, timeout=3000)
                    await page.click(selector)
                    app_logger.info(f"已選擇題目 {q_num} 的選項 {option_letter}: {option_content}")
                except Exception as e:
                    app_logger.error(f"無法點擊題目 {q_num} 的選項 {option_letter}: {option_content}, 錯誤: {e}")

# ========== 主流程函式 (可被外部呼叫) ==========
async def run_quiz_automation(survey_url: str):
    """
    執行自動測驗流程的主函式。

    Args:
        survey_url (str): 要處理的測驗問卷網址。
    """
    app_logger.info(f"=== 開始問卷自動化流程（目標 URL: {survey_url}）===")
    
    # 初始化快取管理器
    cache_manager = QuizCacheManager()
    
    # 步驟 1: 擷取問卷資料
    app_logger.info("\n步驟 1: 擷取問卷資料（檢查快取）...")
    all_qa, option_texts = await extract_survey_data_with_cache(survey_url, cache_manager)
    
    app_logger.info("\n======= 問卷題目抽取結果 =======")
    app_logger.info(all_qa)
    
    # 步驟 2: GPT 分析
    app_logger.info("\n步驟 2: 使用 GPT 分析題目（檢查快取）...")
    answers = get_answer_by_gpt_with_cache(survey_url, all_qa, cache_manager)
    app_logger.info("======= GPT 答案（JSON）=======")
    app_logger.info(json.dumps(answers, ensure_ascii=False, indent=2))
    
    # 步驟 3: 定義自定義填表函數
    async def custom_quiz_fill(page, name):
        await fill_quiz_questions(page, name, answers, option_texts)
    
    # 步驟 4: 批次處理
    app_logger.info("\n步驟 3: 開始批次處理...")
    
    # 嘗試使用新的用戶管理系統
    try:
        # 動態導入 UserManager（避免循環導入）
        import sys
        import os
        
        # 確保可以導入 server 模組
        sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        
        try:
            from server import user_manager
            app_logger.info("使用用戶管理系統進行批次測驗處理...")
            await batch_process_forms_from_manager(
                url=survey_url,
                user_manager=user_manager,
                company_name=company_name,
                cache_manager=cache_manager,
                custom_fill_func=custom_quiz_fill
            )
        except ImportError:
            # 如果無法導入用戶管理器，回退到 CSV 模式
            app_logger.error("無法使用用戶管理系統，回退到 CSV 模式...")
            await batch_process_forms(
                url=survey_url,
                csv_path=CSV_PATH,
                company_name=company_name,
                cache_manager=cache_manager,
                custom_fill_func=custom_quiz_fill
            )
    except Exception as e:
        app_logger.error(f"測驗處理過程中發生錯誤: {e}")
        # 回退到 CSV 模式
        app_logger.error("回退到 CSV 模式...")
        await batch_process_forms(
            url=survey_url,
            csv_path=CSV_PATH,
            company_name=company_name,
            cache_manager=cache_manager,
            custom_fill_func=custom_quiz_fill
        )
    
    app_logger.info(f"\n=== 問卷自動化完成！快取檔案位置: {cache_manager.cache_dir} ===")

# 這個區塊現在只用於獨立測試此檔案
if __name__ == "__main__":
    # 用於獨立測試此模組的預設 URL
    DEFAULT_QUIZ_URL = "https://www.surveycake.com/s/XGbl0"
    app_logger.info(">> 正在以獨立模式執行 auto_quiz.py 進行測試...")
    asyncio.run(run_quiz_automation(DEFAULT_QUIZ_URL))