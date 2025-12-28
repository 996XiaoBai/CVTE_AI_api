import streamlit as st
from conf.config import Config


def init_session_states():
    """
    初始化所有必要的 Session State 变量。
    只需在应用启动时调用一次即可。
    """

    # 定义所有需要的状态变量及其默认值
    defaults = {
        # 1. 聊天核心数据
        "messages": [],  # 存储聊天记录 [{"role": "user", "content": "..."}]
        "conversation_id": "",  # Dify 的会话 ID (用于多轮对话)

        # 2. 文件上传相关
        "files_to_send": [],  # 已处理好、准备发送给 API 的文件对象列表
        "uploader_key": 0,  # 用于强制重置 file_uploader 组件的 key

        # 3. 应用状态管理
        "current_app_name": None,  # 当前选中的 App 名称 (用于检测切换)
        "bot": None,  # DifyService 实例 (初始化为 None，由 Sidebar 接管)

        # 4. 配置项
        # 优先读取 Config，如果没有定义则使用默认值 30000
        "config_max_chars": getattr(Config, 'MAX_CONTEXT_CHARS', 30000)
    }

    # 遍历并初始化
    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value


def clear_session():
    """
    重置当前会话状态。
    通常用于：点击“新对话”按钮、切换 App 时。
    """
    st.session_state.messages = []
    st.session_state.conversation_id = ""
    st.session_state.files_to_send = []

    # 自增 key 会强制 Streamlit 重新渲染 file_uploader，从而清空 UI 上的文件列表
    if "uploader_key" in st.session_state:
        st.session_state.uploader_key += 1
    else:
        st.session_state.uploader_key = 1


def get_state(key, default=None):
    """
    安全获取 session state 的辅助函数
    """
    return st.session_state.get(key, default)