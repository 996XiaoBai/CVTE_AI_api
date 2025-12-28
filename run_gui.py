# run_gui.py
import sys
import os
import streamlit.web.cli as stcli


def resolve_path(path):
    """获取资源绝对路径"""
    if getattr(sys, "frozen", False):
        # [修改点]
        # 对于 -D (文件夹) 模式，我们要去可执行文件所在的目录找 web_ui.py
        # 而不是去 _internal 临时目录找
        basedir = os.path.dirname(sys.executable)
    else:
        # 开发环境
        basedir = os.path.dirname(__file__)

    return os.path.join(basedir, path)


if __name__ == "__main__":
    # 这里的 web_ui.py 是你的主文件名
    file_path = resolve_path("web_ui.py")

    # 打印一下路径，方便调试（运行没问题后可注释掉）
    print(f"正在尝试启动文件: {file_path}")

    # 构造启动命令
    sys.argv = [
        "streamlit",
        "run",
        file_path,
        "--global.developmentMode=false",
    ]

    sys.exit(stcli.main())