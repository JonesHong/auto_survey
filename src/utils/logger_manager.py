from pretty_loguru import create_logger

# Create a logger with a specific name and configuration
app_logger = create_logger(
    name="auto_survey",
    service_tag="auto_survey",
    log_name_preset='daily',
)