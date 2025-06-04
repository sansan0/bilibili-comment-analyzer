import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
import logging
import datetime
import glob
import os

from config import Config, LOG_DIR
from gui.video_frame import VideoFrame
from gui.up_frame import UpFrame
from gui.settings_frame import SettingsFrame
from gui.browse_frame import BrowseFrame
from gui.about_frame import AboutFrame
from utils.assets_helper import get_icon_path

logger = logging.getLogger(__name__)


class BilibiliCommentDownloaderApp:
    """哔哩哔哩评论下载"""

    def __init__(self, root):
        """初始化应用"""
        self.root = root
        self.config = Config()
        

        # 首先设置日志
        self.setup_logging()

        # 记录应用启动
        logger.info("=" * 60)
        logger.info("哔哩哔哩评论观察者启动")
        logger.info(
            f"启动时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        logger.info(f"Python版本: {os.sys.version}")
        logger.info(f"工作目录: {os.getcwd()}")
        logger.info("=" * 60)

        # 设置窗口大小和位置
        self.root.geometry("800x680")
        self.root.minsize(800, 680)
        

        # 先创建固定高度的状态栏
        self.status_bar = tk.Label(
            self.root,
            text="就绪",
            bd=1,
            relief=tk.SUNKEN,
            anchor=tk.W,
            font=("Microsoft YaHei", 9),
            padx=5,
            pady=2,
            bg="#f0f0f0",
            height=1,  # 固定高度为1行
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X, pady=0)

        # 创建标签页
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        # 添加标签页
        self.video_frame = VideoFrame(self.notebook)
        self.up_frame = UpFrame(self.notebook)
        self.browse_frame = BrowseFrame(self.notebook)
        self.settings_frame = SettingsFrame(self.notebook)
        self.about_frame = AboutFrame(self.notebook)

        self.notebook.add(self.video_frame, text="视频评论下载")
        self.notebook.add(self.up_frame, text="UP主视频批量下载")
        self.notebook.add(self.browse_frame, text="浏览已下载")
        self.notebook.add(self.settings_frame, text="设置")
        self.notebook.add(self.about_frame, text="关于")

        self.notebook.bind("<<NotebookTabChanged>>", self.on_tab_changed)

        # 绑定关闭事件
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 窗口居中显示
        self.center_window()
        
        self.set_window_icon()
        logger.info("应用界面初始化完成")

    def set_window_icon(self):
        """设置窗口图标"""
        try:
            icon_path = get_icon_path()
            if icon_path.exists():
                self.root.iconbitmap(str(icon_path))
                logger.info(f"窗口图标设置成功: {icon_path}")
            else:
                logger.warning(f"图标文件不存在: {icon_path}")
        except Exception as e:
            logger.warning(f"设置窗口图标失败: {e}")

    def center_window(self):
        """将窗口居中显示"""
        # 更新窗口以确保所有组件都已渲染
        self.root.update_idletasks()

        # 获取窗口的实际尺寸
        window_width = self.root.winfo_reqwidth()
        window_height = self.root.winfo_reqheight()

        # 如果窗口尺寸为0（可能还未渲染完成），使用设定的尺寸
        if window_width == 1 or window_height == 1:
            window_width = 800
            window_height = 680

        # 获取屏幕尺寸
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()

        # 计算居中位置
        center_x = int((screen_width - window_width) / 2)
        center_y = int((screen_height - window_height) / 2)

        # 确保窗口不会超出屏幕边界
        if center_x < 0:
            center_x = 0
        if center_y < 0:
            center_y = 0

        # 设置窗口位置
        self.root.geometry(f"{window_width}x{window_height}+{center_x}+{center_y}")

    def on_tab_changed(self, event):
        """处理tab切换事件"""
        try:
            # 获取当前选中的tab索引
            selected_tab = self.notebook.select()
            tab_index = self.notebook.index(selected_tab)

            # 获取tab名称
            tab_text = self.notebook.tab(selected_tab, "text")

            logger.info(f"切换到tab: {tab_text} (索引: {tab_index})")

            # 如果切换到浏览已下载tab（索引为2）
            if tab_index == 2:  # "浏览已下载"是第3个tab，索引为2
                logger.info("触发浏览已下载tab的刷新")
                # 调用browse_frame的tab选中方法
                if hasattr(self.browse_frame, "on_tab_selected"):
                    self.browse_frame.on_tab_selected()

        except Exception as e:
            logger.error(f"处理tab切换事件时出错: {e}")

    def setup_logging(self):
        """设置日志 - 每次启动创建新的日志文件"""
        try:
            # 确保日志目录存在
            LOG_DIR.mkdir(parents=True, exist_ok=True)

            # 清理旧的日志文件
            self.cleanup_old_logs()

            # 生成带时间戳的日志文件名
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            log_file = LOG_DIR / f"app_{timestamp}.log"

            # 获取日志级别配置
            log_level = self.config.get("log_level", "INFO").upper()
            if log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
                log_level = "INFO"

            # 清除可能存在的旧的日志配置
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)

            # 设置新的日志配置
            logging.basicConfig(
                level=getattr(logging, log_level),
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                handlers=[
                    logging.FileHandler(log_file, encoding="utf-8"),
                    logging.StreamHandler(),
                ],
                force=True,  # 强制重新配置
            )

            # 记录日志文件信息
            print(f"日志文件: {log_file}")
            logger = logging.getLogger(__name__)
            logger.info(f"日志系统初始化完成，日志文件: {log_file}")

        except Exception as e:
            # 如果日志设置失败，至少要能在控制台看到错误
            print(f"设置日志系统失败: {e}")
            # 使用基本的日志配置作为备用
            logging.basicConfig(
                level=logging.INFO,
                format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                handlers=[logging.StreamHandler()],
                force=True,
            )

    def cleanup_old_logs(self):
        """清理旧的日志文件，保留最新的指定数量"""
        try:
            # 从配置获取保留的日志文件数量，默认保留10个
            max_log_files = self.config.get("max_log_files", 10)

            # 获取所有日志文件
            log_pattern = str(LOG_DIR / "app_*.log")
            log_files = glob.glob(log_pattern)

            if len(log_files) <= max_log_files:
                return

            # 按修改时间排序，最新的在前面
            log_files.sort(key=lambda x: os.path.getmtime(x), reverse=True)

            # 删除多余的日志文件
            files_to_delete = log_files[max_log_files:]
            deleted_count = 0

            for file_path in files_to_delete:
                try:
                    os.remove(file_path)
                    deleted_count += 1
                    print(f"已删除旧日志文件: {Path(file_path).name}")
                except Exception as e:
                    print(f"删除日志文件失败 {file_path}: {e}")

            if deleted_count > 0:
                print(
                    f"清理完成，删除了 {deleted_count} 个旧日志文件，保留最新的 {max_log_files} 个"
                )

        except Exception as e:
            print(f"清理旧日志文件时出错: {e}")

    def update_status(self, message):
        """更新状态栏"""
        current_time = datetime.datetime.now().strftime("%H:%M:%S")

        # 格式化状态消息
        formatted_message = f"[{current_time}] {message}"

        self.status_bar.config(text=formatted_message)
        self.root.update_idletasks()

    def on_close(self):
        """关闭应用"""
        if messagebox.askokcancel("退出", "确定要退出吗？"):
            try:
                # 记录应用关闭
                logger.info("=" * 60)
                logger.info("用户请求关闭应用")

                # 停止所有运行中的服务器
                if hasattr(self, "browse_frame") and self.browse_frame.servers:
                    logger.info("关闭应用时停止所有运行中的服务器")
                    self.browse_frame.stop_all_servers()

                # 记录会话结束
                end_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                logger.info(f"应用结束时间: {end_time}")
                logger.info("哔哩哔哩评论观察者正常退出")
                logger.info("=" * 60)

            except Exception as e:
                print(f"关闭应用时记录日志失败: {e}")
            finally:
                self.root.destroy()
