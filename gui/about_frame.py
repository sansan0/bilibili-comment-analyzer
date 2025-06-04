import tkinter as tk
from tkinter import ttk, scrolledtext
import logging
import webbrowser
from PIL import Image, ImageTk

import version

logger = logging.getLogger(__name__)


class AboutFrame(ttk.Frame):
    """关于界面"""

    def __init__(self, parent):
        """初始化界面"""
        super().__init__(parent)
        self.image_scale_factor = 0.4
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        # 主容器，使用垂直布局
        main_container = ttk.Frame(self)
        main_container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        # 标题
        title_label = ttk.Label(
            main_container,
            text=version.get_app_name_en(),
            font=("Microsoft YaHei", 14, "bold"),
        )
        title_label.pack(pady=(0, 5))

        # 版本
        version_label = ttk.Label(
            main_container,
            text=f"版本: {version.get_version_display()}",
            font=("Microsoft YaHei", 8),
        )
        version_label.pack(pady=(0, 5))

        # 分隔线
        separator = ttk.Separator(main_container, orient="horizontal")
        separator.pack(fill=tk.X, pady=10)

        # 详细信息
        info_frame = ttk.Frame(main_container)
        info_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        description_text = (
            "本工具是B站评论数据分析下载器，提供完整的评论采集与可视化分析功能。\n\n"
            "🎯 核心功能:\n"
            "• 单视频评论下载、UP主批量视频下载\n"
            "• 评论地区分布地图、评论词云分析\n"
            "• 可视化展示按地区、性别、等级的多维度筛选分析、实时统计评论数、用户数、点赞数等关键指标\n\n"
            "📊 基本使用示例:\n"
            "• 点击【设置】 -> 扫码登录 -> 点击【视频评论下载】-> 找到视频链接 -> 获得 BV 号(EP号) -> 点击【获取评论】 -> 点击【生成词云】 -> 选中视频文件夹下的 csv 文件 -> 点击【浏览已下载】\n\n"
            "声明:\n"
            "• 本工具仅供学习和研究使用，请勿用于任何商业用途\n"
            "• 使用本工具时请遵守B站用户协议和相关法律法规\n"
            "• 请尊重创作者的劳动成果和知识产权，不得利用本工具侵犯他人权益\n"
            "• 请合理使用本工具，避免频繁下载评论为自身账号造成风险\n"
            "• 使用本工具所产生的一切后果由用户自行承担"
        )

        description_text_widget = scrolledtext.ScrolledText(
            info_frame,
            wrap=tk.WORD,  # 按单词换行，避免单词被截断
            font=("Microsoft YaHei", 10),
            height=10,  # 设置高度（行数）
            width=80,  # 设置宽度（字符数）
            padx=10,
            pady=10,
            background="#f8f9fa",  # 浅灰色背景
            relief=tk.FLAT,  # 平面边框
            borderwidth=0,  # 无边框
            state=tk.DISABLED,  # 设为只读状态
            cursor="arrow",  # 鼠标样式
        )
        description_text_widget.pack(fill=tk.BOTH, expand=True, pady=10)
        description_text_widget.config(state=tk.NORMAL)
        description_text_widget.insert(tk.END, description_text)
        description_text_widget.config(state=tk.DISABLED)

        # GitHub链接 - 使用函数调用
        link_frame = ttk.Frame(info_frame)
        link_frame.pack(fill=tk.X, pady=10)

        link_label = ttk.Label(
            link_frame, text="作者项目主页:", font=("Microsoft YaHei", 9)
        )
        link_label.pack(side=tk.LEFT, padx=(0, 5))

        github_link = ttk.Label(
            link_frame,
            text=version.get_author_url(),
            font=("Microsoft YaHei", 9, "underline"),
            foreground="blue",
            cursor="hand2",
        )
        github_link.pack(side=tk.LEFT)
        github_link.bind(
            "<Button-1>",
            lambda e: webbrowser.open(version.get_author_url()),
        )

        self.add_wechat_image(main_container)

    def add_wechat_image(self, parent):
        """添加微信图片显示"""
        try:
            # 使用新的路径获取方式
            from utils.assets_helper import get_weixin_image_path

            image_path = get_weixin_image_path()

            if not image_path.exists():
                logger.warning(f"微信图片不存在: {image_path}")
                return

            pil_image = Image.open(image_path)

            # 计算缩放后的尺寸
            original_width, original_height = pil_image.size
            new_width = int(original_width * self.image_scale_factor)
            new_height = int(original_height * self.image_scale_factor)

            resized_image = pil_image.resize((new_width, new_height), Image.LANCZOS)

            # 转换为tkinter可用的格式
            self.wechat_image = ImageTk.PhotoImage(resized_image)

            # 创建图片容器框架
            image_frame = ttk.Frame(parent)
            image_frame.pack(pady=(20, 10))

            # 创建并显示图片标签
            image_label = ttk.Label(image_frame, image=self.wechat_image)
            image_label.pack()

            caption_label = ttk.Label(
                image_frame,
                text="扫码关注作者微信公众号，支持作者更新",
                font=("Microsoft YaHei", 9),
                foreground="#666666",
            )
            caption_label.pack(pady=(5, 0))

        except Exception as e:
            logger.error(f"加载微信图片失败: {e}")
