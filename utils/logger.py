# utils/logger.py
import logging
import os
import time
from conf.config import Config
from utils.path_manager import PathManager


# ================= 1. 独立的清理函数 (已修复参数问题) =================
def auto_clean_logs(days=None):
    """
    [维护函数] 清理过期日志
    :param days: (可选) 指定保留天数。如果不传，则读取 Config.LOG_Retention_Days
    """
    log_dir = os.path.dirname(PathManager.get_log_file("test.log"))  # 获取日志目录

    # 修改点：优先使用传入的 days，如果没有传，则使用 Config 配置，默认 7 天
    if days is not None:
        days_to_keep = days
    else:
        days_to_keep = getattr(Config, 'LOG_Retention_Days', 7)

    if not os.path.exists(log_dir):
        return

    now = time.time()
    # 转换为秒
    seconds_limit = days_to_keep * 86400

    try:
        count = 0
        for filename in os.listdir(log_dir):
            file_path = os.path.join(log_dir, filename)
            # 只处理 .log 文件
            if os.path.isfile(file_path) and filename.endswith('.log'):
                # 检查文件最后修改时间
                if now - os.path.getmtime(file_path) > seconds_limit:
                    try:
                        os.remove(file_path)
                        count += 1
                    except PermissionError:
                        # 防止文件正在被占用（Windows常见）
                        pass

        if count > 0:
            print(f"🧹 [System] 已清理 {count} 个过期日志文件 (保留最近 {days_to_keep} 天)")

    except Exception as e:
        print(f"⚠️ 日志清理检查失败: {e}")


# ================= 2. 日志类 (优化后) =================
class LogHandler:
    def __init__(self, logger_name="CVTE_AI"):
        self.logger = logging.getLogger(logger_name)
        # 防止多次初始化导致重复打印
        self.logger.propagate = False
        self.logger.setLevel(Config.LOG_LEVEL)

        if not self.logger.handlers:
            self._add_stream_handler()
            self._add_file_handler()

            # 🔥 关键点：在日志初始化时，调用清理函数（不传参，使用 Config 默认值）
            auto_clean_logs()

    def _get_log_path(self):
        # 保持你喜欢的按日期命名
        timestamp = time.strftime("%Y-%m-%d", time.localtime())
        return PathManager.get_log_file(f"{timestamp}.log")

    def _get_formatter(self):
        return logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def _add_stream_handler(self):
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(self._get_formatter())
        self.logger.addHandler(stream_handler)

    def _add_file_handler(self):
        file_path = self._get_log_path()

        file_handler = logging.FileHandler(
            filename=file_path,
            mode='a',
            encoding='utf-8'
        )
        file_handler.setFormatter(self._get_formatter())
        self.logger.addHandler(file_handler)

    def get_logger(self):
        return self.logger


# 单例导出
logger = LogHandler().get_logger()