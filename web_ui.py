# web_ui.py
import streamlit as st
import os
import tempfile
import time  # 用于延时

# 导入业务层
from PageObject.dify_service import DifyService
from utils.logger import logger
from utils.file_parser import FileParser
from conf.config import Config

# ================= 1. 页面配置 =================
st.set_page_config(
    page_title="Dify 全能助手 (Pro)",
    page_icon="🚀",
    layout="wide"
)

# ================= 2. Session 初始化 =================
if "messages" not in st.session_state:
    st.session_state.messages = []
if "conversation_id" not in st.session_state:
    st.session_state.conversation_id = ""
if "files_to_send" not in st.session_state:
    st.session_state.files_to_send = []
if "uploader_key" not in st.session_state:
    st.session_state.uploader_key = 0

if "bot" not in st.session_state:
    try:
        st.session_state.bot = DifyService()
        info = st.session_state.bot.get_app_info()
        st.toast(f"已连接: {info.get('name')}", icon="✅")
    except Exception as e:
        st.error(f"连接失败: {e}")


# ================= 3. 辅助函数 =================

def save_uploaded_file(uploaded_file):
    """保存临时文件"""
    try:
        file_ext = os.path.splitext(uploaded_file.name)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as tmp_file:
            tmp_file.write(uploaded_file.getvalue())
            return tmp_file.name
    except Exception as e:
        st.error(f"保存失败: {e}")
        return None


@st.cache_data(show_spinner=False)
def cached_parse_file(file_path):
    return FileParser.parse(file_path)


# ================= 4. 侧边栏 =================
with st.sidebar:
    st.title("🛠️ 控制台")
    st.caption(
        f"Session: {st.session_state.conversation_id[:8]}..." if st.session_state.conversation_id else "Session: New")

    if st.button("🗑️ 新开对话", use_container_width=True):
        st.session_state.conversation_id = ""
        st.session_state.messages = []
        st.session_state.files_to_send = []
        st.session_state.uploader_key += 1
        st.rerun()

    st.divider()
    st.markdown("### ⚙️ 高级设置")
    dynamic_max_chars = st.slider(
        "单次文档字数限制",
        min_value=10000,
        max_value=500000,
        value=getattr(Config, 'MAX_CONTEXT_CHARS', 30000),
        step=10000,
        help="控制本地解析文档后发送给 AI 的最大长度，防止 Token 溢出。"
    )

# ================= 5. 主界面 =================
st.subheader("💬 Dify 全能助手")

# A. 渲染历史消息
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # [优化点 1] 为历史回复增加复制按钮 (仅针对 AI 回复)
        if msg["role"] == "assistant":
            with st.expander("📄 复制 Markdown 源码", expanded=False):
                st.code(msg["content"], language="markdown")

# B. 文件上传区
with st.popover("📎 挂载文件", use_container_width=True):
    st.markdown("### 📂 支持格式")
    st.info("💡 图片直接上传；文档(PDF/Office/Code)自动解析转文字。")

    uploaded_files = st.file_uploader(
        "选择或粘贴文件 (Ctrl+V)",
        accept_multiple_files=True,
        label_visibility="collapsed",
        key=f"uploader_{st.session_state.uploader_key}",
        type=['png', 'jpg', 'jpeg', 'webp', 'gif', 'mp3', 'mp4',
              'pdf', 'pptx', 'xlsx', 'xls', 'xmind',
              'txt', 'md', 'py', 'java', 'js', 'html', 'css', 'json', 'csv', 'sql', 'sh']
    )

    if uploaded_files:
        paths = []
        for f in uploaded_files:
            p = save_uploaded_file(f)
            if p: paths.append(p)
        if paths:
            st.session_state.files_to_send = paths
            st.success(f"已就绪 {len(paths)} 个文件")

if st.session_state.files_to_send:
    st.info(f"📎 待发送: {len(st.session_state.files_to_send)} 个文件", icon="📌")

# C. 输入与发送
if prompt := st.chat_input("请输入..."):
    # 1. 用户消息
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 2. AI 回复
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        status = st.status("正在处理...", expanded=True)

        try:
            # === 文件预处理 ===
            media_files = []
            text_context = ""
            MEDIA_EXTS = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.mp3', '.mp4']

            for path in st.session_state.files_to_send:
                ext = os.path.splitext(path)[1].lower()
                if ext in MEDIA_EXTS:
                    media_files.append(path)
                else:
                    status.write(f"📄 解析文档: {os.path.basename(path)}")
                    text_context += cached_parse_file(path)

            # Token 截断
            if len(text_context) > dynamic_max_chars:
                status.warning(f"⚠️ 文档过长，已截断至 {dynamic_max_chars} 字。")
                text_context = text_context[:dynamic_max_chars] + "\n\n...[截断]..."

            # [优化点 2] 使用带滚动条的容器预览文档内容
            # height=300 表示固定高度 300px，内容多了内部滚动，不会拉长页面
            if text_context:
                with st.expander("👀 发送内容预览 (点击展开)"):
                    with st.container(height=300):
                        st.code(text_context, language="markdown")

            final_query = prompt + text_context
            final_files_payload = []
            if media_files:
                status.write("📤 上传多媒体...")
                final_files_payload = st.session_state.bot.prepare_files_for_chat(media_files)

            # === 发送请求 ===
            status.write("🧠 AI 思考中...")
            stream = st.session_state.bot.send_chat_message(
                query=final_query,
                conversation_id=st.session_state.conversation_id,
                files=final_files_payload
            )

            st.session_state.files_to_send = []

            for data in stream:
                event = data.get('event')
                if event in ['message', 'agent_message']:
                    chunk = data.get('answer', '')
                    full_res += chunk
                    placeholder.markdown(full_res + "▌")
                    if 'conversation_id' in data:
                        st.session_state.conversation_id = data['conversation_id']
                elif event == 'agent_thought':
                    thought = data.get('thought')
                    tool = data.get('tool')
                    if thought: status.write(f"🤔 {thought}")
                    if tool: status.write(f"🔧 调用: {tool}")
                elif event == 'error':
                    st.error(data.get('message'))

            # 完成状态
            status.update(label="完成", state="complete", expanded=False)
            placeholder.markdown(full_res)

            # [优化点 3] 生成完成后，立即显示一个复制按钮
            with st.expander("📄 复制全文", expanded=False):
                st.code(full_res, language="markdown")

            st.session_state.messages.append({"role": "assistant", "content": full_res})

            st.session_state.uploader_key += 1
            time.sleep(0.5)  # 防止 DOM 刷新冲突
            st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")
            logger.error(f"UI Error: {e}", exc_info=True)