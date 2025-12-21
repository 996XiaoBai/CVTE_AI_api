# mian.py
import sys
import time
import os

# 导入业务层
from PageObject.dify_service import DifyService
# 导入工具层
from utils.logger import logger
from utils.path_manager import PathManager


def clean_path(path_str):
    """
    清理拖入终端的文件路径
    解决 Mac/Windows 拖入终端时自动带引号或空格的问题
    """
    path_str = path_str.strip()
    # 去除首尾的单引号或双引号
    if (path_str.startswith("'") and path_str.endswith("'")) or \
            (path_str.startswith('"') and path_str.endswith('"')):
        return path_str[1:-1]
    return path_str


def main():
    logger.info("=== 🤖 Dify 智能助手启动中... ===")

    # 1. 实例化业务对象
    try:
        bot = DifyService()
        # 获取应用信息作为连接测试
        app_info = bot.get_app_info()
        logger.info(f"✅ 已连接到应用: {app_info.get('name', 'Unknown')}")
        logger.info(f"📍 运行模式: {app_info.get('mode', 'Unknown')}")
    except Exception as e:
        logger.critical(f"❌ 初始化失败，请检查网络或配置: {e}")
        return

    # 初始化会话变量
    current_conversation_id = ""

    # === 📎 文件暂存区 (存放当前轮次要发送的文件) ===
    # 无论是代码里写死的，还是聊天时拖进去的，都存这里
    current_files_payload = []

    # ==========================================
    # 📂 1. 静态配置加载 (启动时自动加载的文件)
    # ==========================================
    # 只要把文件放在根目录的 files/ 文件夹下，这里填文件名即可
    static_file_names = [
        # "cat.png",      # 在此处取消注释以启用启动时自动上传
        # "report.pdf",
    ]

    if static_file_names:
        logger.info(f"检测到配置中有 {len(static_file_names)} 个静态文件等待上传...")
        try:
            # 获取绝对路径
            file_paths = [PathManager.get_upload_file(name) for name in static_file_names]
            # 调用 Service 层处理
            payloads = bot.prepare_files_for_chat(file_paths)
            current_files_payload.extend(payloads)
            logger.info("📂 静态文件预处理完成。")
        except FileNotFoundError as e:
            logger.error(f"❌ 静态文件未找到: {e}")
        except Exception as e:
            logger.error(f"❌ 静态文件上传出错: {e}")

    # ==========================================
    # 💬 对话循环
    # ==========================================
    print("\n" + "=" * 60)
    print("💡 操作指南：")
    print("   1. 正常聊天：直接输入文字，按回车发送。")
    print("   2. 上传图片：输入 '/add'，然后把文件拖进来。")
    print("   3. 清空文件：输入 '/clear' 清空当前已挂载的文件。")
    print("   4. 退出程序：输入 'q' 或 'exit'。")
    print("=" * 60 + "\n")

    while True:
        try:
            # 动态提示符：显示当前挂载了多少个文件
            prompt_prefix = "👉 你"
            if current_files_payload:
                prompt_prefix = f"👉 你 (已挂载 {len(current_files_payload)} 个文件)"

            user_input = input(f"{prompt_prefix}: ").strip()

            # --- 指令处理区域 ---

            # 1. 退出检测
            if user_input.lower() in ['exit', 'quit', 'q']:
                logger.info("用户请求退出。")
                print("👋 再见！")
                break

            # 2. 动态添加文件 (/add)
            elif user_input.lower() == '/add':
                print("\n📂 [上传模式] 请将文件拖入此窗口，或粘贴绝对路径 (直接回车取消):")
                raw_path = input("   文件路径 > ").strip()

                if not raw_path:
                    print("   已取消操作。\n")
                    continue

                # 清理路径
                file_path = clean_path(raw_path)

                try:
                    # 调用 Service 上传
                    # 注意：prepare_files_for_chat 接收列表，返回列表
                    new_payloads = bot.prepare_files_for_chat([file_path])
                    if new_payloads:
                        current_files_payload.extend(new_payloads)
                        print(f"   ✅ 已成功挂载: {os.path.basename(file_path)}")
                        print("   (文件将随下一条消息一起发送)\n")
                except Exception as e:
                    print(f"   ❌ 添加失败: {e}\n")
                continue

            # 3. 清空暂存 (/clear)
            elif user_input.lower() == '/clear':
                current_files_payload = []
                print("🗑️ 已清空暂存文件。\n")
                continue

            # --- 正常发送逻辑 ---

            if not user_input:
                continue

            print("🤖 Bot: ", end="", flush=True)

            # 3. 发送消息 (带上暂存的文件)
            stream = bot.send_chat_message(
                query=user_input,
                conversation_id=current_conversation_id,
                files=current_files_payload
            )

            # 发送后清空文件列表 (根据业务惯例，文件只随当前消息发一次)
            if current_files_payload:
                current_files_payload = []

            # 4. 处理流式响应
            has_answer = False
            for data in stream:
                event = data.get('event')

                # 监听 'message' (基础对话) 和 'agent_message' (Agent推理对话)
                if event in ['message', 'agent_message']:
                    answer = data.get('answer', '')
                    print(answer, end="", flush=True)
                    has_answer = True

                    # 自动更新会话 ID
                    if 'conversation_id' in data:
                        current_conversation_id = data['conversation_id']

                # 监听错误
                elif event == 'error':
                    error_msg = data.get('message')
                    print(f"\n[API Error]: {error_msg}")
                    logger.error(f"API 返回错误: {error_msg}")

            if not has_answer:
                logger.warning("Bot 没有返回任何文本内容。")

            print("\n")  # 换行准备下一轮

        except KeyboardInterrupt:
            print("\n程序已强制停止")
            logger.info("程序被用户强制停止 (Ctrl+C)")
            break
        except Exception as e:
            logger.error(f"对话循环中发生未捕获异常: {e}", exc_info=True)
            print(f"\n❌ 系统出错，请查看日志。")


if __name__ == "__main__":
    main()