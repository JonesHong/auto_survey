# Playwright 自動化專案

本專案使用 Playwright 來實現自動化的網頁操作，主要包含自動簽到和自動測驗功能。

## ✨ 功能

- **自動簽到 (`auto_attendance.py`)**: 自動執行網頁簽到流程。
- **自動測驗 (`auto_quiz.py`)**: 自動完成指定的網頁測驗。
- **問卷工具 (`survey_utils.py`)**: 提供處理問卷相關的輔助功能。

## 📂 專案結構

```
.
├── main.py                 # 主執行腳本 (推薦)
├── server.py               # Web 伺服器，提供前端介面
├── auto_attendance.py      # 自動簽到腳本 (舊版)
├── auto_quiz.py            # 自動測驗腳本 (舊版)
├── survey_utils.py         # 問卷相關輔助函式
├── name_list.csv           # 用於自動化腳本的名稱列表
├── config/
│   ├── config.sample.ini   # 設定檔範本
│   └── config.ini          # 您的本地設定檔
├── src/
│   └── config/
│       ├── manager.py      # 設定檔管理模組
│       └── schema.py       # 設定檔結構定義
├── survey_cache/           # 問卷相關的快取資料
└── backup/                 # 備份檔案
```

## 🚀 如何開始

### 1. 安裝依賴

建議您建立一個 `requirements.txt` 檔案來管理專案的依賴套件。

```bash
# 建立 requirements.txt (範例)
echo "playwright" > requirements.txt
echo "pandas" >> requirements.txt
echo "uvicorn" >> requirements.txt
echo "ini2py" >> requirements.txt
```

然後透過 pip 安裝：

```bash
pip install -r requirements.txt
```

### 2. 安裝 Playwright 瀏覽器

第一次使用 Playwright 需要安裝所需的瀏覽器核心。

```bash
playwright install
```

### 3. 進行設定

1.  **複製設定檔**：
    將 `config/config.sample.ini` 複製一份，並重新命名為 `config.ini` (或其他您喜歡的名稱)。這個 `config.ini` 將會是您的本地設定，且已被 `.gitignore` 忽略，不會被上傳到版本控制中。

    ```bash
    copy config\config.sample.ini config\config.ini
    ```

2.  **編輯設定**：
    根據您的需求，修改 `config.ini` 檔案中的設定值，例如網站帳號、密碼等資訊。

3.  **(可選) 將 INI 轉換為 Python Class**：
    本專案使用 `ini2py` 套件來將 `.ini` 設定檔轉換為強型別的 Python Class，方便在程式碼中以物件導向的方式存取設定值，並獲得自動完成的提示。

    如果您修改了 `config.ini` 的結構 (例如新增 section 或 key)，可以執行以下指令來重新生成對應的 Python schema 檔案：

    ```bash
    ini2py --input config/config.ini --output src/config/schema.py --class-name ConfigSchema
    ```

    這將確保您的程式碼與設定檔保持同步。

### 4. 準備資料

將需要用於自動化腳本的姓名或帳號等資料填入 `name_list.csv`。

### 5. 執行腳本

您可以透過以下三種方式來執行自動化任務：

#### 方法一：使用主腳本 `main.py` (推薦)

此方法最為靈活，您可以透過指令列參數指定要執行的任務和 URL。

- **僅執行簽到**:
  ```bash
  python main.py --task attend --attend_url "您的簽到問卷網址"
  ```

- **僅執行測驗**:
  ```bash
  python main.py --task quiz --quiz_url "您的測驗問卷網址"
  ```

- **同時執行簽到與測驗**:
  ```bash
  python main.py --task all --attend_url "您的簽到網址" --quiz_url "您的測驗網址"
  ```

- **互動模式**:
  如果您不提供任何參數，腳本會進入互動模式，引導您輸入必要的資訊。
  ```bash
  python main.py
  ```

#### 方法二：啟動 Web 伺服器 `server.py`

此方法會啟動一個本地的 Web 服務，讓您可以透過瀏覽器介面來操作。

1.  **安裝 uvicorn**:
    ```bash
    pip install uvicorn
    ```

2.  **啟動伺服器**:
    ```bash
    uvicorn server:app --reload
    ```

3.  **開啟瀏覽器**:
    在瀏覽器中開啟 `http://127.0.0.1:8000`，您將會看到一個操作介面，可以在上面填入 URL 並啟動自動化任務。

#### 方法三：(舊版) 直接執行腳本

原本直接執行 `auto_attendance.py` 和 `auto_quiz.py` 的方式已不再是主要的使用方法，建議改用 `main.py`。

## 📝 注意事項

- 執行前請確保已完成所有設定。
- 本專案僅為學習和測試目的，請勿用於非法用途。
