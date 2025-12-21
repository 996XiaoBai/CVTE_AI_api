# utils/path_manager.py
import os
from conf.config import Config


class PathManager:
    """
    路径管理工具类
    """
    # 直接从 Config 拿路径，保持单向依赖：PathManager -> Config
    BASE_DIR = Config.BASE_DIR
    LOG_DIR = Config.LOG_DIR
    FILES_DIR = Config.FILES_DIR

    @classmethod
    def get_log_file(cls, filename: str) -> str:
        if not os.path.exists(cls.LOG_DIR):
            os.makedirs(cls.LOG_DIR)
        return os.path.join(cls.LOG_DIR, filename)

    @classmethod
    def get_upload_file(cls, filename: str) -> str:
        """获取上传文件路径"""
        # 确保 files 文件夹存在
        if not os.path.exists(cls.FILES_DIR):
            os.makedirs(cls.FILES_DIR)

        file_path = os.path.join(cls.FILES_DIR, filename)

        # 这里不要用 logger.error，直接抛出异常，让调用的地方(main.py)去记录日志
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"文件未找到: {file_path}")

        return file_path