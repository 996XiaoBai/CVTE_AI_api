# utils/logger.py
import logging
import os
import time
from logging.handlers import TimedRotatingFileHandler
from conf.config import Config
from utils.path_manager import PathManager  # 导入路径管理


class LogHandler:
    """
    日志封装类
    """

    def __init__(self, logger_name="CVTE_AI"):
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(Config.LOG_LEVEL)

        # 防止重复添加 Handler (核心逻辑)
        if not self.logger.handlers:
            self._add_stream_handler()
            self._add_file_handler()

    def _get_log_path(self):
        timestamp = time.strftime("%Y-%m-%d", time.localtime())
        return PathManager.get_log_file(f"{timestamp}.log")

    def _get_formatter(self):
        """定义日志输出格式"""
        # 格式：[时间] [级别] [文件名:行号] - 信息
        return logging.Formatter(
            fmt='[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

    def _add_stream_handler(self):
        """添加控制台输出"""
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(self._get_formatter())
        stream_handler.setLevel(Config.LOG_LEVEL)
        self.logger.addHandler(stream_handler)

    def _add_file_handler(self):
        """添加文件输出 (按天切割)"""
        file_path = self._get_log_path()

        # when='MIDNIGHT' 表示每天午夜切割，backupCount=7 表示保留7个旧文件
        file_handler = TimedRotatingFileHandler(
            filename=file_path,
            when='MIDNIGHT',
            interval=1,
            backupCount=Config.LOG_Retention_Days,
            encoding='utf-8'  # 关键：解决中文乱码
        )
        file_handler.setFormatter(self._get_formatter())
        file_handler.setLevel(Config.LOG_LEVEL)
        self.logger.addHandler(file_handler)

    def get_logger(self):
        return self.logger


# 单例模式：直接初始化一个实例供外部调用
logger = LogHandler().get_logger()