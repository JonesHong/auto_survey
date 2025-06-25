from pretty_loguru import create_logger

# Create a logger with a specific name and configuration
app_logger = create_logger(
    name="auto_survey",
    service_tag="auto_survey",
    log_name_preset="daily",
    log_file_settings={
        "rotation": "1000 KB",  # 設定輪換大小
        "retention": "1 week",  # 保留時間
        "compression": "zip",  # 壓縮格式
    },
)
