import tkinter as tk
from gui.app import BilibiliCommentDownloaderApp
from config import BASE_DIR
from version import get_app_name

def main():
    """主入口函数"""
    root = tk.Tk()
    root.title(get_app_name())

    # 确保资源目录存在
    ensure_resource_dirs()

    # 创建主应用
    app = BilibiliCommentDownloaderApp(root)

    # 启动GUI事件循环
    root.mainloop()


def ensure_resource_dirs():
    """确保必要的资源目录存在"""

    dirs = [
        BASE_DIR,
        BASE_DIR / "output",
    ]

    for directory in dirs:
        directory.mkdir(parents=True, exist_ok=True)


if __name__ == "__main__":
    main()
