# config.py
import os

class Config:
    # 基础配置
    API_BASE_URL = "https://dify.cvte.com/v1"

    # 请填入你的 API Key
    API_KEY = "app-JhpoKtzMJBbcH78FHiIaKZ5f"

    # 用户标识 (建议使用你的域账号)
    USER_ID = "linkangbao"

    # --- 新增配置 ---
    TIMEOUT = 30  # 请求超时时间
    MAX_RETRIES = 3  # 最大重试次数
    LOG_LEVEL = "INFO"  # 日志级别
    LOG_Retention_Days = 7


    # 1. 直接在这里计算根目录，不依赖 PathManager
    # 获取当前文件 (conf/config.py) 的上一级 (conf) 的上一级 (CVTE_AI_api)
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # 2. 定义其他路径
    LOG_DIR = os.path.join(BASE_DIR, "logs")
    FILES_DIR = os.path.join(BASE_DIR, "files")

    # 4. [新增] 安全限制
    # 单次发送给 AI 的文档最大字符数 ，防止 token 溢出或费用爆炸
    MAX_CONTEXT_CHARS = 200000