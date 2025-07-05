import os
import signal
import sys
import atexit
from threading import Thread
import time
# from src.utils.decorators.singleton import singleton
from src.utils.logger_manager import app_logger as logger

# @singleton
class GracefulShutdown:
    def __init__(self):
        self.running_threads = []
        self.callback_list = []  # 用於存放回調函數
        self.is_shutdown = False  # 用於防止重複執行
        self._setup_signals()

    def add_call_back_list(self, callback):
        """
        添加回調函數到回調列表中，避免重複添加。
        """
        if callback and callback not in self.callback_list:
            self.callback_list.append(callback)
            logger.info(f"Callback {callback.__name__} added to the callback list.")

    def register_thread(self, thread: Thread):
        """
        註冊需要管理的執行緒。
        """
        if thread not in self.running_threads:
            self.running_threads.append(thread)

    def cleanup(self):
        """
        清理所有執行緒和執行回調函數。
        """
        if self.is_shutdown:  # 如果已經執行過清理，直接返回
            return
        self.is_shutdown = True

        # 執行回調函數
        for callback in self.callback_list:
            try:
                logger.info(f"Executing callback {callback.__name__}...")
                callback()
            except Exception as e:
                logger.error(f"Error executing callback {callback.__name__}: {e}")

        # 清理執行緒
        if self.running_threads:
            logger.info("Executing cleanup for all threads...")
            for thread in self.running_threads:
                if hasattr(thread, "stop"):
                    thread.stop()
                if thread.is_alive():
                    logger.info(f"Stopping thread {thread.name}...")
                    thread.join(timeout=1)
            logger.info("All threads successfully stopped.")

    def signal_handler(self, signum, frame):
        """
        信號處理函數，執行清理操作並退出。
        """
        if not self.is_shutdown:
            logger.info(f"Received signal {signum}, shutting down...")
            try:
                self.cleanup()
                logger.info("Exiting gracefully...")
                sys.exit(0)
            except Exception as e:
                logger.error(f"Error during shutdown: {e}. Forcing exit.")
                os._exit(0)

    def _setup_signals(self):
        """
        註冊信號處理程序和退出時的清理操作。
        """
        if not hasattr(self, "_signals_setup_done"):
            # 在 Docker 容器中禁用信號處理，避免與 uvicorn 衝突
            if not os.getenv("DOCKER_CONTAINER", False):
                signal.signal(signal.SIGINT, self.signal_handler)
                signal.signal(signal.SIGTERM, self.signal_handler)
            atexit.register(self.cleanup)
            self._signals_setup_done = True


# 初始化 GracefulShutdown 實例
# graceful_shutdown = GracefulShutdown()
