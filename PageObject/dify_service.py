# PageObject/dify_service.py
import os
import json
import mimetypes
from typing import Generator, Dict, Any, List, Union, Optional

# 导入底层 API 和日志工具
from BasePage.base_api import BaseApiClient
from utils.logger import logger


class DifyService(BaseApiClient):
    """
    Dify 业务服务层
    封装所有具体的 API 调用逻辑，不包含 HTTP 底层细节
    """

    # Dify 支持的文件后缀映射表
    FILE_TYPE_MAPPING = {
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.bmp', '.tiff'],
        'video': ['.mp4', '.mov', '.mpeg', '.mpga', '.webm', '.avi'],
        'audio': ['.mp3', '.m4a', '.wav', '.amr', '.wma', '.aac', '.flac'],
        'document': ['.pdf', '.txt', '.md', '.markdown', '.html', '.htm',
                     '.xlsx', '.xls', '.docx', '.doc', '.csv', '.pptx', '.ppt', '.xml', '.epub']
    }

    def _determine_dify_file_type(self, filename: str) -> str:
        """根据文件名后缀判断 Dify 需要的 type 字段"""
        ext = os.path.splitext(filename)[1].lower()
        for file_type, extensions in self.FILE_TYPE_MAPPING.items():
            if ext in extensions:
                return file_type
        return 'document'  # 默认兜底类型

    # ==========================
    # 1. 核心：对话与消息
    # ==========================

    def send_chat_message(self, query: str, conversation_id: str = "", inputs: Dict = None, files: List[Dict] = None,
                          stream: bool = True, user: str = None) -> Union[Dict, Generator]:
        """
        发送对话消息
        :param files: 已上传并格式化好的文件列表 (由 prepare_files_for_chat 生成)
        """
        payload = {
            "inputs": inputs or {},
            "query": query,
            "response_mode": "streaming" if stream else "blocking",
            "user": user or self.default_user,
            "conversation_id": conversation_id,
            "files": files or []
        }

        logger.info(f"发送消息: {query[:20]}... (Files: {len(files or [])})")
        response = self.post("/chat-messages", json=payload, stream=stream)

        if stream:
            return self._handle_sse_stream(response)
        else:
            return response.json()

    def stop_generation(self, task_id: str, user: str = None):
        """停止生成"""
        payload = {"user": user or self.default_user}
        return self.post(f"/chat-messages/{task_id}/stop", json=payload).json()

    def message_feedback(self, message_id: str, rating: str, content: str = "", user: str = None):
        """消息反馈 (like/dislike)"""
        payload = {
            "rating": rating,
            "user": user or self.default_user,
            "content": content
        }
        logger.info(f"提交反馈: {rating} -> msg_id: {message_id}")
        return self.post(f"/messages/{message_id}/feedbacks", json=payload).json()

    def get_history_messages(self, conversation_id: str, user: str = None, limit: int = 20):
        """获取历史消息"""
        params = {
            "conversation_id": conversation_id,
            "user": user or self.default_user,
            "limit": limit
        }
        return self.get("/messages", params=params).json()

    # ==========================
    # 2. 核心：文件管理 (增强版)
    # ==========================

    def upload_file(self, file_path: str, user: str = None) -> Dict:
        """单文件上传"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        # 自动猜测 MIME 类型
        mime_type, _ = mimetypes.guess_type(file_path)
        if not mime_type:
            mime_type = 'application/octet-stream'

        logger.info(f"正在上传文件: {os.path.basename(file_path)}")

        # 使用 with 确保文件句柄关闭
        try:
            with open(file_path, 'rb') as f:
                files = {
                    'file': (os.path.basename(file_path), f, mime_type)
                }
                data = {'user': user or self.default_user}
                res = self.post_form("/files/upload", data=data, files=files)
                result = res.json()
                logger.info(f"✅ 上传成功 ID: {result.get('id')}")
                return result
        except Exception as e:
            logger.error(f"❌ 上传失败: {file_path} | {e}")
            raise

    def prepare_files_for_chat(self, file_paths: Optional[List[str]] = None, user: str = None) -> List[Dict]:
        """
        【业务逻辑封装】批量处理文件：
        1. 检查数量限制 (Max 6)
        2. 自动上传
        3. 自动识别类型并构造 payload
        """
        if not file_paths:
            return []

        if len(file_paths) > 6:
            logger.warning(f"文件数量超限: {len(file_paths)} > 6")
            raise ValueError("最多允许上传 6 个文件")

        uploaded_payload = []
        logger.info(f"开始批量处理 {len(file_paths)} 个文件...")

        for path in file_paths:
            try:
                # 1. 上传
                res = self.upload_file(path, user)
                file_id = res.get('id')
                file_name = res.get('name')

                # 2. 判断类型
                dify_type = self._determine_dify_file_type(file_name)

                # 3. 构造参数
                uploaded_payload.append({
                    "type": dify_type,
                    "transfer_method": "local_file",
                    "upload_file_id": file_id
                })
            except Exception:
                # 这里选择抛出异常中断，也可以选择 continue 跳过
                raise

        return uploaded_payload

    # ==========================
    # 3. 会话管理
    # ==========================

    def get_conversations(self, limit: int = 20, user: str = None):
        """获取会话列表"""
        params = {"user": user or self.default_user, "limit": limit}
        return self.get("/conversations", params=params).json()

    def rename_conversation(self, conversation_id: str, name: str, user: str = None):
        """重命名会话"""
        payload = {"name": name, "user": user or self.default_user}
        return self.post(f"/conversations/{conversation_id}/name", json=payload).json()

    def delete_conversation(self, conversation_id: str, user: str = None):
        """删除会话"""
        payload = {"user": user or self.default_user}
        self.delete(f"/conversations/{conversation_id}", json=payload)
        logger.info(f"会话已删除: {conversation_id}")
        return True

    # ==========================
    # 4. 音频与多模态
    # ==========================

    def audio_to_text(self, file_path: str, user: str = None):
        """语音转文字 (STT)"""
        if not os.path.exists(file_path):
            raise FileNotFoundError(file_path)

        with open(file_path, 'rb') as f:
            files = {'file': f}
            data = {'user': user or self.default_user}
            res = self.post_form("/audio-to-text", data=data, files=files)
            return res.json()

    def text_to_audio(self, text: str, user: str = None, save_path: str = "output.mp3"):
        """文字转语音 (TTS)"""
        payload = {"text": text, "user": user or self.default_user}
        logger.info("正在合成语音...")
        res = self.post("/text-to-audio", json=payload)

        with open(save_path, 'wb') as f:
            f.write(res.content)
        logger.info(f"语音已保存: {save_path}")
        return save_path

    # ==========================
    # 5. 应用信息与辅助
    # ==========================

    def get_app_info(self):
        return self.get("/info").json()

    def get_app_meta(self):
        return self.get("/meta").json()

    def _handle_sse_stream(self, response) -> Generator[Dict, None, None]:
        """处理 SSE 流式响应"""
        for line in response.iter_lines():
            if line:
                decoded_line = line.decode('utf-8')
                if decoded_line.startswith('data: '):
                    json_str = decoded_line[6:]
                    try:
                        data = json.loads(json_str)
                        yield data
                    except json.JSONDecodeError:
                        continue