import streamlit as st
from conf.config import Config
from PageObject.dify_service import DifyService
from utils.logger import logger


# ================= 辅助函数 =================

@st.cache_data(ttl=60, show_spinner=False)
def get_cached_conversations(_bot, app_name, limit=20):
    """
    获取历史会话列表（带缓存）
    注意：_bot 参数前的下划线是为了告诉 Streamlit 不要试图对 bot 对象进行 hash
    app_name 用于确保不同应用的缓存隔离
    """
    try:
        return _bot.get_conversations(limit=limit)
    except Exception as e:
        logger.error(f"获取历史会话失败: {e}")
        return {}


def load_history_session(conv_id):
    """
    点击历史会话时，加载具体的聊天记录到 session_state
    """
    try:
        # 1. 设置当前 ID
        st.session_state.conversation_id = conv_id
        st.session_state.messages = []

        # 2. 从 API 获取历史消息
        history = st.session_state.bot.get_history_messages(conversation_id=conv_id, limit=100)

        # 3. 格式化并存入 session (注意 Dify 返回的是倒序，通常需要反转)
        for item in reversed(history.get('data', [])):
            if item.get('query'):
                st.session_state.messages.append({"role": "user", "content": item.get('query')})
            if item.get('answer'):
                st.session_state.messages.append({"role": "assistant", "content": item.get('answer')})

        # 4. 重置文件上传状态，避免旧文件混入新会话
        st.session_state.files_to_send = []
        st.session_state.uploader_key += 1

    except Exception as e:
        st.error(f"加载历史详情失败: {e}")
        logger.error(f"Load History Error: {e}")


# ================= 主渲染函数 =================

def render_sidebar():
    """
    渲染侧边栏的核心逻辑供主程序调用
    """
    with st.sidebar:
        st.title("🤖 智能助手中心")

        # ---------------------------------------
        # 1. 应用切换与 Bot 初始化逻辑
        # ---------------------------------------

        # 获取应用列表 (防御性编程：防止 Config 没配置)
        if hasattr(Config, 'APP_MAP') and Config.APP_MAP:
            app_options = list(Config.APP_MAP.keys())
        else:
            app_options = ["默认应用"]

        # 下拉选择框
        selected_app = st.selectbox(
            "选择当前助手能力",
            options=app_options,
            index=0
        )

        # 核心逻辑：检测是否需要(重新)初始化 Bot
        # 触发条件：Bot 不存在 OR 用户切换了应用选择
        if "bot" not in st.session_state or st.session_state.get("current_app_name") != selected_app:
            try:
                # 获取对应的 Key
                target_key = Config.APP_MAP.get(selected_app, Config.API_KEY)

                # 初始化 Service
                st.session_state.bot = DifyService(api_key=target_key)
                st.session_state.current_app_name = selected_app

                # !!! 切换应用时，彻底清空当前上下文 !!!
                st.session_state.messages = []
                st.session_state.conversation_id = ""
                st.session_state.files_to_send = []
                st.session_state.uploader_key += 1

                # UI 反馈
                info = st.session_state.bot.get_app_info()
                st.toast(f"已连接: {selected_app}", icon="✅")

            except Exception as e:
                st.error(f"连接 {selected_app} 失败，请检查网络或 Key。")
                logger.error(f"Bot Init Error: {e}")

        # ---------------------------------------
        # 2. 历史会话管理区域
        # ---------------------------------------
        st.divider()
        st.subheader("🗂️ 历史会话")

        col1, col2 = st.columns([3, 1])
        with col1:
            # 新建对话按钮
            if st.button("➕ 新对话", use_container_width=True, type="primary"):
                st.session_state.conversation_id = ""
                st.session_state.messages = []
                st.session_state.files_to_send = []
                st.session_state.uploader_key += 1
                st.rerun()
        with col2:
            # 刷新列表按钮
            if st.button("🔄", use_container_width=True):
                get_cached_conversations.clear()
                st.rerun()

        st.markdown("---")

        # 渲染历史会话列表
        try:
            if "bot" in st.session_state and st.session_state.bot:
                # 传入 current_app_name 确保缓存隔离，不同应用的缓存不混用
                conv_list = get_cached_conversations(
                    st.session_state.bot,
                    st.session_state.current_app_name,
                    limit=20
                )
                data_list = conv_list.get('data', [])

                if not data_list:
                    st.caption("暂无历史记录")
                else:
                    # 遍历并生成按钮
                    for conv in data_list:
                        c_id = conv.get('id')
                        c_name = conv.get('name', '未命名会话')

                        # 高亮当前选中的会话
                        is_active = (c_id == st.session_state.conversation_id)
                        label = f"🟢 {c_name}" if is_active else f"💬 {c_name}"

                        if st.button(label, key=c_id, use_container_width=True):
                            load_history_session(c_id)
                            st.rerun()
        except Exception as e:
            st.warning("无法加载历史列表")
            logger.warning(f"History list render error: {e}")

        # ---------------------------------------
        # 3. 高级设置区域
        # ---------------------------------------
        st.divider()
        with st.expander("⚙️ 高级设置"):
            # 确保 config_max_chars 存在
            if "config_max_chars" not in st.session_state:
                st.session_state.config_max_chars = 30000

            st.session_state.config_max_chars = st.slider(
                "文档解析截断长度",
                min_value=10000,
                max_value=500000,
                value=st.session_state.config_max_chars,
                step=10000,
                help="限制单次发送给 AI 的文档上下文长度，防止 Token 溢出。"
            )

            # 显示调试信息
            st.caption(f"App: {st.session_state.get('current_app_name')}")
            st.caption(
                f"SessionID: {st.session_state.conversation_id[:8]}..." if st.session_state.conversation_id else "Session: New")