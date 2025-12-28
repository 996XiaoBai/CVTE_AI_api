import streamlit as st
import os
import time
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

# 导入业务层
from utils.logger import logger
from utils.file_parser import FileParser
from conf.config import Config

# 导入新拆分的模块
from web.session import init_session_states
from web.sidebar import render_sidebar

# ================= 1. 全局配置与生命周期 =================

# 定义临时上传目录
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


# 执行启动逻辑
init_application()

# 页面基础配置
st.set_page_config(
    page_title="Dify 全能助手 (Ultra)",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ================= 2. 状态与界面初始化 =================

# 1. 初始化 Session 状态 (调用 web/session.py)
init_session_states()

# 2. 渲染侧边栏 (调用 web/sidebar.py)
# 这里处理了 App 切换、Bot 初始化、历史记录加载
render_sidebar()


# ================= 3. 核心工具函数 (保留在主文件) =================

def save_uploaded_file(uploaded_file):
    """保存文件到专属临时目录"""
    try:
        # 使用 uuid 防止文件名冲突
        unique_name = f"{uuid.uuid4().hex}_{uploaded_file.name}"
        save_path = os.path.join(TEMP_UPLOAD_DIR, unique_name)
        with open(save_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
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


# ================= 4. 主聊天界面区域 =================

# 动态显示当前 App 名称
current_app_name = st.session_state.get("current_app_name", "Dify 助手")
st.subheader(f"💬 {current_app_name}")

if not st.session_state.messages:
    st.info("👋 欢迎使用！支持 PDF/Excel/PPT/XMind 并行解析与多轮对话。", icon="✨")

# 渲染消息历史
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg["role"] == "assistant":
            with st.expander("📄 复制 Markdown", expanded=False):
                st.code(msg["content"], language="markdown")

# ================= 5. 输入区与文件上传 =================

# 文件挂载区
with st.popover("📎 挂载文件", use_container_width=True):
    st.markdown("### 📂 文件上传")
    # key 使用 session 中的 uploader_key，以便在“新对话”时重置控件
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

# 状态提示
if st.session_state.files_to_send:
    st.info(f"📎 待发送: {len(st.session_state.files_to_send)} 个文件", icon="📌")

# 检查文件状态
has_files = len(st.session_state.files_to_send) > 0
manual_trigger = False

# 如果有文件，显示“立即分析”按钮
if has_files:
    cols = st.columns([0.85, 0.15])
    with cols[1]:
        if st.button("📤 立即分析文件", use_container_width=True, type="primary"):
            manual_trigger = True

# 聊天输入框
user_input = st.chat_input("请输入... (或者点击上方按钮直接分析文件)")

# ================= 6. 业务处理逻辑 =================

if user_input or (has_files and manual_trigger):

    # 防御性编程：确保 Bot 已连接
    if "bot" not in st.session_state or not st.session_state.bot:
        st.error("服务未连接，请在侧边栏选择应用并重试。")
        st.stop()

    # 确定 Prompt
    final_prompt = user_input if user_input else "请详细分析以上上传的文件内容，并提取关键信息。"

    # 显示用户输入
    with st.chat_message("user"):
        st.markdown(final_prompt)
    st.session_state.messages.append({"role": "user", "content": final_prompt})

    # 处理 AI 回复
    with st.chat_message("assistant"):
        placeholder = st.empty()
        full_res = ""
        status = st.status("正在处理...", expanded=True)

        current_temp_files = []

        try:
            # 锁定当前要发送的文件
            if st.session_state.files_to_send:
                current_temp_files = st.session_state.files_to_send.copy()
            st.session_state.files_to_send = []  # 发送后清空 UI 状态

            media_files = []
            doc_files_to_parse = []
            text_context = ""
            MEDIA_EXTS = ['.jpg', '.jpeg', '.png', '.webp', '.gif', '.mp3', '.mp4']

            # 1. 快速分类文件
            for f_obj in current_temp_files:
                ext = os.path.splitext(f_obj['path'])[1].lower()
                if ext in MEDIA_EXTS:
                    media_files.append(f_obj['path'])
                else:
                    doc_files_to_parse.append(f_obj)

            # 2. 并行解析文档 (Text/PDF/Excel等)
            if doc_files_to_parse:
                status.write(f"⚡️ 正在并行解析 {len(doc_files_to_parse)} 个文档...")
                # 从 Session 获取配置的字符上限
                max_chars = st.session_state.get("config_max_chars", 30000)

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

            # 3. 构造 Prompt
            if text_context:
                with st.expander("👀 解析内容预览"):
                    with st.container(height=200):
                        st.code(text_context, language="markdown")

                # 将文件内容嵌入 Prompt
                final_query = f"<context>\n{text_context}\n</context>\n\n<instruction>\n{final_prompt}\n</instruction>"
            else:
                final_query = final_prompt

            # 4. 上传多媒体文件 (Image/Audio/Video)
            final_files_payload = []
            if media_files:
                status.write("📤 上传多媒体文件...")
                # 调用 Bot 服务上传并获取 ID
                final_files_payload = st.session_state.bot.prepare_files_for_chat(media_files)

            # 5. 发送流式请求
            status.write("🧠 AI 思考中...")
            stream = st.session_state.bot.send_chat_message(
                query=final_query,
                conversation_id=st.session_state.conversation_id,
                files=final_files_payload
            )

            # 6. 处理流式响应
            for data in stream:
                event = data.get('event')

                if event in ['message', 'agent_message']:
                    chunk = data.get('answer', '')
                    full_res += chunk
                    placeholder.markdown(full_res + "▌")
                    # 更新会话 ID
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

            # 记录助手回复
            st.session_state.messages.append({"role": "assistant", "content": full_res})

            # 刷新页面以准备下一轮（并重置文件上传控件 ID）
            st.session_state.uploader_key += 1
            time.sleep(0.5)
            st.rerun()

        except Exception as e:
            st.error(f"Error: {e}")
            logger.error(f"UI Processing Error: {e}", exc_info=True)

        finally:
            # 清理本次上传的临时文件
            if current_temp_files:
                cleanup_temp_files(current_temp_files)