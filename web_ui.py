# web_ui.py
import streamlit as st
import os
import time
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入业务层
from PageObject.dify_service import DifyService
from utils.logger import logger
from utils.file_parser import FileParser
from conf.config import Config

# ================= 1. 全局配置与生命周期管理 =================

# 定义一个专属的临时上传目录
TEMP_UPLOAD_DIR = os.path.join(Config.BASE_DIR, "temp_uploads")


@st.cache_resource
def init_application():
    """
    应用启动初始化：清理旧的僵尸文件
    """
    if os.path.exists(TEMP_UPLOAD_DIR):
        try:
            shutil.rmtree(TEMP_UPLOAD_DIR)
            logger.info("🧹 启动自检：已清理旧的临时文件目录。")
        except Exception as e:
            logger.error(f"清理临时目录失败: {e}")
    os.makedirs(TEMP_UPLOAD_DIR, exist_ok=True)
    return True


init_application()

st.set_page_config(
    page_title="Dify 全能助手 (Ultra)",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
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
if "config_max_chars" not in st.session_state:
    st.session_state.config_max_chars = getattr(Config, 'MAX_CONTEXT_CHARS', 30000)

if "bot" not in st.session_state:
    try:
        st.session_state.bot = DifyService()
        info = st.session_state.bot.get_app_info()
        st.toast(f"已连接: {info.get('name')}", icon="✅")
    except Exception as e:
        st.error(f"连接失败: {e}")


# ================= 3. 核心工具函数 =================

def save_uploaded_file(uploaded_file):
    """保存文件到专属临时目录"""
    try:
        # 使用 uuid 防止文件名冲突
        unique_name = f"{uuid.uuid4().hex}_{uploaded_file.name}"
        save_path = os.path.join(TEMP_UPLOAD_DIR, unique_name)
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        # 返回路径和原始文件名
        return {"path": save_path, "name": uploaded_file.name}
    except Exception as e:
        st.error(f"文件写入失败: {e}")
        return None


def parse_file_safe(file_path, original_name, limit):
    """封装解析器"""
    try:
        return FileParser.parse(file_path, max_chars=limit, original_filename=original_name)
    except Exception as e:
        return f"\n[解析异常 {original_name}: {e}]\n"


def cleanup_temp_files(file_objs):
    """清理临时文件"""
    if not file_objs: return
    for item in file_objs:
        try:
            if os.path.exists(item['path']):
                os.remove(item['path'])
        except Exception as e:
            logger.warning(f"清理失败: {e}")


@st.cache_data(ttl=60, show_spinner=False)
def get_cached_conversations(_bot, limit=20):
    return _bot.get_conversations(limit=limit)


def load_history_session(conv_id):
    """加载历史会话"""
    try:
        st.session_state.conversation_id = conv_id
        st.session_state.messages = []
        history = st.session_state.bot.get_history_messages(conversation_id=conv_id, limit=100)
        for item in reversed(history.get('data', [])):
            if item.get('query'):
                st.session_state.messages.append({"role": "user", "content": item.get('query')})
            if item.get('answer'):
                st.session_state.messages.append({"role": "assistant", "content": item.get('answer')})
        st.session_state.files_to_send = []
        st.session_state.uploader_key += 1
    except Exception as e:
        st.error(f"加载历史失败: {e}")


# ================= 4. 侧边栏 =================
with st.sidebar:
    st.title("🗂️ 历史会话")
    col1, col2 = st.columns([3, 1])
    with col1:
        if st.button("➕ 新对话", use_container_width=True, type="primary"):
            st.session_state.conversation_id = ""
            st.session_state.messages = []
            st.session_state.files_to_send = []
            st.session_state.uploader_key += 1
            st.rerun()
    with col2:
        if st.button("🔄", use_container_width=True):
            get_cached_conversations.clear()
            st.rerun()

    st.markdown("---")
    try:
        if "bot" in st.session_state:
            conv_list = get_cached_conversations(st.session_state.bot, limit=20)
            data_list = conv_list.get('data', [])
            if not data_list:
                st.caption("暂无历史记录")
            else:
                for conv in data_list:
                    c_id = conv.get('id')
                    c_name = conv.get('name', '未命名会话')
                    is_active = (c_id == st.session_state.conversation_id)
                    label = f"🟢 {c_name}" if is_active else f"💬 {c_name}"
                    if st.button(label, key=c_id, use_container_width=True):
                        load_history_session(c_id)
                        st.rerun()
    except Exception as e:
        st.warning("获取列表失败")

    st.divider()
    with st.expander("⚙️ 高级设置"):
        st.session_state.config_max_chars = st.slider(
            "文档截断长度",
            min_value=10000, max_value=500000,
            value=st.session_state.config_max_chars, step=10000
        )
        st.caption(f"Session: {st.session_state.conversation_id}")

# ================= 5. 主界面 =================
st.subheader("💬 Dify 全能助手")

if not st.session_state.messages:
    st.info("👋 支持 PDF/Excel/PPT/XMind 并行解析与多轮对话。", icon="✨")

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            with st.expander("📄 复制 Markdown", expanded=False):
                st.code(msg["content"], language="markdown")

with st.popover("📎 挂载文件", use_container_width=True):
    st.markdown("### 📂 文件上传")
    uploaded_files = st.file_uploader(
        "选择文件", accept_multiple_files=True, label_visibility="collapsed",
        key=f"uploader_{st.session_state.uploader_key}",
        type=['png', 'jpg', 'jpeg', 'webp', 'gif', 'mp3', 'mp4',
              'pdf', 'pptx', 'xlsx', 'xls', 'xmind',
              'txt', 'md', 'py', 'java', 'js', 'html', 'css', 'json', 'csv', 'sql', 'sh']
    )
    if uploaded_files:
        file_objs = []
        for f in uploaded_files:
            res = save_uploaded_file(f)
            if res: file_objs.append(res)
        if file_objs:
            st.session_state.files_to_send = file_objs
            st.success(f"已就绪 {len(file_objs)} 个文件")

if st.session_state.files_to_send:
    st.info(f"📎 待发送: {len(st.session_state.files_to_send)} 个文件", icon="📌")

# ================= 6. 输入与发送逻辑 (含一键分析) =================

# 状态检查
has_files = len(st.session_state.files_to_send) > 0
manual_trigger = False  # 是否点击了手动发送按钮

# 如果有文件，显示一个“一键分析”按钮
if has_files:
    cols = st.columns([0.85, 0.15])
    with cols[1]:
        if st.button("📤 立即分析文件", use_container_width=True, type="primary"):
            manual_trigger = True

# 聊天输入框
user_input = st.chat_input("请输入... (或者点击上方按钮直接分析文件)")

# 触发条件：有输入文字 OR (有文件且点击了按钮)
if user_input or (has_files and manual_trigger):

    # 确定 Prompt：如果有输入则用输入，否则用默认提示词
    final_prompt = user_input if user_input else "请详细分析以上上传的文件内容，并提取关键信息。"

    with st.chat_message("user"):
        st.markdown(final_prompt)
    st.session_state.messages.append({"role": "user", "content": final_prompt})

    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        status = st.status("正在处理...", expanded=True)

        current_temp_files = []

        try:
            if st.session_state.files_to_send:
                current_temp_files = st.session_state.files_to_send.copy()
            st.session_state.files_to_send = []  # 清空UI状态

            media_files = []
            doc_files_to_parse = []
            text_context = ""
            MEDIA_EXTS = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.mp3', '.mp4']

            # 1. 快速分类
            for f_obj in current_temp_files:
                ext = os.path.splitext(f_obj['path'])[1].lower()
                if ext in MEDIA_EXTS:
                    media_files.append(f_obj['path'])
                else:
                    doc_files_to_parse.append(f_obj)

            # 2. 并行解析文档
            if doc_files_to_parse:
                status.write(f"⚡️ 正在并行解析 {len(doc_files_to_parse)} 个文档...")
                max_chars = st.session_state.config_max_chars

                with ThreadPoolExecutor(max_workers=4) as executor:
                    future_to_file = {
                        executor.submit(parse_file_safe, f['path'], f['name'], max_chars): f['name']
                        for f in doc_files_to_parse
                    }
                    for future in as_completed(future_to_file):
                        fname = future_to_file[future]
                        try:
                            result = future.result()
                            if len(text_context) + len(result) > max_chars:
                                status.warning(f"⚠️ 总文本量超限，文件 {fname} 及后续内容已截断。")
                                text_context += result[:(max_chars - len(text_context))]
                                break
                            text_context += result
                        except Exception as exc:
                            logger.error(f"{fname} 解析异常: {exc}")

            if text_context:
                with st.expander("👀 解析内容预览"):
                    with st.container(height=200):
                        st.code(text_context, language="markdown")

            # 3. 结构化 Prompt
            final_query = final_prompt
            if text_context:
                final_query = f"<context>\n{text_context}\n</context>\n\n<instruction>\n{final_prompt}\n</instruction>"

            # 4. 上传多媒体
            final_files_payload = []
            if media_files:
                status.write("📤 上传多媒体...")
                final_files_payload = st.session_state.bot.prepare_files_for_chat(media_files)

            # 5. 发送请求
            status.write("🧠 AI 思考中...")
            stream = st.session_state.bot.send_chat_message(
                query=final_query,
                conversation_id=st.session_state.conversation_id,
                files=final_files_payload
            )

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

            status.update(label="完成", state="complete", expanded=False)
            placeholder.markdown(full_res)
            st.session_state.messages.append({"role": "assistant", "content": full_res})

            st.session_state.uploader_key += 1
            time.sleep(0.5)
            st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")
            logger.error(f"UI Error: {e}", exc_info=True)

        finally:
            if current_temp_files:
                cleanup_temp_files(current_temp_files)