# BasePage/base_api.py
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
from typing import Dict, Optional, Any, Union

# 导入配置和日志模块
from conf.config import Config
from utils.logger import logger


class BaseApiClient:
    """
    基础 API 客户端
    封装了 HTTP 请求的通用逻辑：鉴权、会话保持、重试机制、日志记录、错误处理
    """

    def __init__(self):
        self.base_url = Config.API_BASE_URL
        self.api_key = Config.API_KEY
        self.default_user = Config.USER_ID

        # 1. 初始化 Session (长连接池)
        self.session = requests.Session()

        # 2. 配置重试策略 (Retry Strategy)
        # total=3: 最多重试3次
        # backoff_factor=1: 重试间隔 1s, 2s, 4s...
        # status_forcelist: 遇到这些状态码时自动重试
        retries = Retry(
            total=Config.MAX_RETRIES,
            backoff_factor=1,
            status_forcelist=[500, 502, 503, 504],
            allowed_methods=["GET", "POST", "PUT", "DELETE"]
        )

        # 将重试策略挂载到 http:// 和 https:// 协议上
        adapter = HTTPAdapter(max_retries=retries)
        self.session.mount('https://', adapter)
        self.session.mount('http://', adapter)

    def _get_headers(self, file_upload: bool = False) -> Dict[str, str]:
        """
        统一组装请求头
        :param file_upload: 是否为文件上传 (上传时不指定 Content-Type)
        """
        if not self.api_key:
            logger.critical("API Key 未配置，请检查 conf/config.py")
            raise ValueError("API Key is missing")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }

        # 普通请求需要 JSON 类型，文件上传由 requests 自动处理 boundary
        if not file_upload:
            headers["Content-Type"] = "application/json"

        return headers

    def _handle_error(self, response: requests.Response):
        """
        统一错误处理
        尝试解析 Dify 返回的具体 JSON 错误信息
        """
        try:
            error_data = response.json()
            code = error_data.get('code', 'Unknown Code')
            message = error_data.get('message', 'Unknown Error')
            # 记录详细的业务错误日志
            logger.error(f"❌ API 业务报错 [{response.status_code}]: {code} - {message}")
        except Exception:
            # 如果解析失败（例如返回 HTML 报错页），则记录原始文本
            logger.error(f"❌ API HTTP 报错 [{response.status_code}]: {response.text[:200]}")

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """
        核心请求方法
        """
        url = f"{self.base_url}{endpoint}"

        # 自动注入 Headers
        # 如果调用方没有传 headers，我们生成默认的
        if 'headers' not in kwargs:
            is_file = kwargs.pop('is_file', False)  # 弹出自定义标志位
            kwargs['headers'] = self._get_headers(file_upload=is_file)

        # 处理超时 (流式请求通常不需要严格的读取超时)
        if 'timeout' not in kwargs:
            kwargs['timeout'] = Config.TIMEOUT if not kwargs.get('stream') else None

        try:
            # Debug 日志 (仅开发调试时看)
            # logger.debug(f"Request: {method} {url}")

            # 使用 Session 发送请求
            response = self.session.request(method, url, **kwargs)

            # 检查 HTTP 状态码 (4xx, 5xx)
            if not response.ok:
                self._handle_error(response)
                response.raise_for_status()  # 抛出异常

            return response

        except requests.exceptions.RetryError:
            logger.error(f"❌ 连接超时，重试 {Config.MAX_RETRIES} 次仍失败: {url}")
            raise
        except requests.exceptions.RequestException as e:
            logger.error(f"❌ 网络请求异常: {method} {url} | Error: {e}")
            raise

    # ==========================================
    # 对外暴露的 HTTP 方法
    # ==========================================

    def get(self, endpoint: str, params: Dict = None, stream: bool = False) -> requests.Response:
        return self._request("GET", endpoint, params=params, stream=stream)

    def post(self, endpoint: str, json: Dict = None, stream: bool = False) -> requests.Response:
        return self._request("POST", endpoint, json=json, stream=stream)

    def put(self, endpoint: str, json: Dict = None) -> requests.Response:
        return self._request("PUT", endpoint, json=json)

    def delete(self, endpoint: str, json: Dict = None) -> requests.Response:
        return self._request("DELETE", endpoint, json=json)

    def post_form(self, endpoint: str, data: Dict = None, files: Dict = None) -> requests.Response:
        """
        专门处理 multipart/form-data (文件上传)
        """
        # is_file=True 告诉 _request 方法不要加 Content-Type: application/json
        return self._request("POST", endpoint, data=data, files=files, is_file=True)