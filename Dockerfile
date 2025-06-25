# 使用官方 Python 映像檔作為基礎
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 複製 requirements.txt 並安裝相依套件
# 這一步驟獨立出來可以利用 Docker 的快取機制，如果 requirements.txt 沒有變更，就不會重新安裝
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install
# 複製整個專案的程式碼到工作目錄
COPY . .

# 向 Docker 聲明容器在執行時會監聽的網路連接埠
# 這與您在 server.py 中設定的 PORT=51000 相符
EXPOSE 51000

# 容器啟動時要執行的命令
# 直接執行 server.py，因為在該檔案的 __main__ 區塊中已經定義了 uvicorn 的啟動方式
CMD ["python", "server.py"]
