import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import threading
import logging
from pathlib import Path
import re
import json
import time

from config import Config
from api.crypto import bvid_to_avid
from models.comment import Comment, Stat
from store.csv_analyzer import normalize_location, generate_map_from_csv
from store.csv_exporter import save_to_csv
from store.geo_exporter import write_geojson
from api.bilibili_api import (
    BilibiliAPI,
    extract_title_from_dirname,
    get_dir_name,
    parse_bilibili_url,
)
from gui.tooltip import create_tooltip

logger = logging.getLogger(__name__)


class VideoFrame(ttk.Frame):
    """视频评论下载界面"""

    # 内容类型显示名称映射
    CONTENT_TYPE_NAMES = {"video": "视频", "bangumi": "番剧剧集", "season": "番剧季度"}

    def __init__(self, parent):
        """初始化界面"""
        super().__init__(parent)
        self.config = Config()
        self.api = BilibiliAPI(self.config.get("cookie", ""))
        self.init_ui()

    def get_content_type_name(self, content_type: str = None) -> str:
        """获取内容类型的显示名称"""
        if content_type is None:
            content_type = getattr(self, "content_type", "unknown")
        return self.CONTENT_TYPE_NAMES.get(content_type, "内容")

    def init_ui(self):
        """初始化UI"""
        # 输入区域
        input_frame = ttk.LabelFrame(self, text="输入")
        input_frame.pack(fill=tk.X, padx=10, pady=3)

        # BV号/EP号/SS号输入
        ttk.Label(input_frame, text="视频BV号/番剧EP号/番剧SS号:").grid(
            row=0, column=0, padx=5, pady=3, sticky=tk.W
        )
        self.bvid_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.bvid_var, width=30).grid(
            row=0, column=1, padx=5, pady=3, sticky=tk.W
        )

        # 更新提示文本
        bv_hint_frame = ttk.Frame(input_frame)
        bv_hint_frame.grid(row=0, column=2, padx=5, pady=3, sticky=tk.W)

        # 视频示例
        ttk.Label(bv_hint_frame, text="视频：https://www.bilibili.com/video/").pack(
            side=tk.LEFT
        )
        bold_font = ("Microsoft YaHei", 9, "bold")
        ttk.Label(bv_hint_frame, text="BVxxxxx", font=bold_font).pack(side=tk.LEFT)

        # 番剧剧集示例
        ep_hint_frame = ttk.Frame(input_frame)
        ep_hint_frame.grid(row=1, column=2, padx=5, pady=0, sticky=tk.W)
        ttk.Label(
            ep_hint_frame, text="番剧剧集：https://www.bilibili.com/bangumi/play/"
        ).pack(side=tk.LEFT)
        ttk.Label(ep_hint_frame, text="epxxxxxx", font=bold_font).pack(side=tk.LEFT)

        # 番剧季度示例
        ss_hint_frame = ttk.Frame(input_frame)
        ss_hint_frame.grid(row=2, column=2, padx=5, pady=0, sticky=tk.W)
        ttk.Label(
            ss_hint_frame, text="番剧季度：https://www.bilibili.com/bangumi/play/"
        ).pack(side=tk.LEFT)
        ttk.Label(ss_hint_frame, text="ssxxxxx", font=bold_font).pack(side=tk.LEFT)

        # 评论排序方式
        ttk.Label(input_frame, text="评论排序:").grid(
            row=2, column=0, padx=5, pady=3, sticky=tk.W
        )
        self.corder_var = tk.IntVar(value=self.config.get("corder", 1))
        corder_frame = ttk.Frame(input_frame)
        corder_frame.grid(row=2, column=1, padx=5, pady=3, sticky=tk.W)

        ttk.Radiobutton(
            corder_frame, text="按时间", variable=self.corder_var, value=0
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            corder_frame, text="按点赞数", variable=self.corder_var, value=1
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            corder_frame, text="按回复数", variable=self.corder_var, value=2
        ).pack(side=tk.LEFT, padx=5)

        # 是否生成地图
        self.mapping_var = tk.BooleanVar(value=self.config.get("mapping", True))
        ttk.Checkbutton(
            input_frame, text="生成评论地区分布地图", variable=self.mapping_var
        ).grid(row=3, column=0, columnspan=2, padx=5, pady=3, sticky=tk.W)

        # 操作按钮
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=3)

        download_btn = ttk.Button(
            button_frame, text="📥 获取评论", command=self.start_download
        )
        download_btn.pack(side=tk.LEFT, padx=3, pady=3)

        create_tooltip(
            download_btn,
            "下载好评论后\n" "可在【浏览已下载】中点击【浏览地图】",
        )

        stop_btn = ttk.Button(button_frame, text="⏹️ 停止", command=self.stop_download)
        stop_btn.pack(side=tk.LEFT, padx=3, pady=3)

        clear_btn = ttk.Button(button_frame, text="🧹 清空日志", command=self.clear_log)
        clear_btn.pack(side=tk.LEFT, padx=3, pady=3)

        csv_map_btn = ttk.Button(
            button_frame, text="🌐生成地图", command=self.generate_map_from_csv
        )
        csv_map_btn.pack(side=tk.LEFT, padx=3, pady=3)
        create_tooltip(
            csv_map_btn,
            "从现有的CSV文件中生成【地图】\n"
            "可在【浏览已下载】中点击【浏览地图】\n"
            "CSV文件包含所有评论数据，是生成地图的唯一来源\n"
            "注：该按钮主要用于数据迁移和作者自己开发测试效果啦~",
        )

        csv_wordcloud_btn = ttk.Button(
            button_frame, text="☁️ 生成词云", command=self.generate_wordcloud_from_csv
        )
        csv_wordcloud_btn.pack(side=tk.LEFT, padx=3, pady=3)
        create_tooltip(
            csv_wordcloud_btn,
            "从现有的CSV中生成词云\n"
            "可在【浏览已下载】中点击【浏览词云】\n"
            "支持按地区、性别、等级筛选不同情况下的词云数据\n"
            "实时查看筛选后的统计信息",
        )
        download_images_btn = ttk.Button(
            button_frame, text="📥 获取图片", command=self.download_images_from_csv
        )
        download_images_btn.pack(side=tk.LEFT, padx=3, pady=3)
        create_tooltip(
            download_images_btn,
            "从现有的CSV文件中提取图片链接并下载\n"
            "即使在下载评论时未开启图片下载\n"
            "也可以通过此功能补充下载图片\n"
            "已存在的图片会自动跳过，不会重复下载",
        )
        # 进度条
        self.progress_var = tk.DoubleVar()
        ttk.Label(button_frame, text="进度:").pack(side=tk.LEFT, padx=3, pady=3)
        ttk.Progressbar(
            button_frame, variable=self.progress_var, length=300, mode="determinate"
        ).pack(side=tk.LEFT, padx=3, pady=3, fill=tk.X, expand=True)

        # 日志区域
        log_frame = ttk.LabelFrame(self, text="日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=3)

        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Microsoft YaHei", 9),
            padx=5,
            pady=5,
            background="#fafafa",
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=3)

        self.log_text.tag_configure("info", foreground="#000000")
        self.log_text.tag_configure("success", foreground="#008800")
        self.log_text.tag_configure("warning", foreground="#FF8C00")
        self.log_text.tag_configure("error", foreground="#CC0000")
        self.log_text.tag_configure(
            "header", foreground="#0066CC", font=("Microsoft YaHei", 9, "bold")
        )

        # 状态变量
        self.stop_flag = False
        self.download_thread = None

    def generate_map_from_csv(self):
        """从现有CSV文件生成地图"""

        # 获取输出目录
        output_base_dir = self.config.get("output", "")
        if not output_base_dir:
            messagebox.showerror("错误", "请先在设置中配置输出目录")
            return

        output_path = Path(output_base_dir)
        if not output_path.exists():
            messagebox.showerror("错误", f"输出目录不存在: {output_base_dir}")
            return

        # 选择CSV文件
        file_path = filedialog.askopenfilename(
            title="选择CSV文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")],
            initialdir=output_base_dir,  # 确保从输出目录开始
        )

        if not file_path:
            return

        csv_path = Path(file_path)

        # 验证选择的CSV文件是否在输出目录下
        try:
            # 检查CSV文件是否在输出目录的子目录中
            csv_path.relative_to(output_path)
            self.log(f"选择的CSV文件: {csv_path}")
        except ValueError:
            # 文件不在输出目录下，给出警告但仍允许继续
            self.log(f"警告: 选择的CSV文件不在输出目录下: {csv_path}", "warning")

        # 选择输出目录
        # 也从输出目录开始，而不是CSV文件的父目录
        # 默认建议使用CSV文件所在的目录，但初始目录仍是输出目录的根
        suggested_output_dir = (
            csv_path.parent
            if csv_path.parent.is_relative_to(output_path)
            else output_base_dir
        )

        output_dir = filedialog.askdirectory(
            title="选择地图输出目录",
            initialdir=str(
                suggested_output_dir
            ),  # 使用建议的目录，但确保在输出目录范围内
        )

        if not output_dir:
            return

        output_dir_path = Path(output_dir)

        # 验证选择的输出目录是否合理
        try:
            # 检查输出目录是否在输出目录的子目录中
            output_dir_path.relative_to(output_path)
            self.log(f"地图将输出到: {output_dir_path}")
        except ValueError:
            # 输出目录不在输出目录下，给出警告但仍允许继续
            self.log(
                f"警告: 选择的输出目录不在配置的输出目录下: {output_dir_path}",
                "warning",
            )

        # 生成地图前的确认信息
        self.log(f"开始从CSV文件生成地图")
        self.log(f"  CSV文件: {csv_path.name}")
        self.log(f"  输出目录: {output_dir_path}")

        try:
            # 生成地图
            result = generate_map_from_csv(str(csv_path), str(output_dir_path))

            if result:
                self.log("地图生成成功", "success")

                # 检查生成的文件
                bv_name = csv_path.stem  # CSV文件名（不含扩展名）
                html_file = output_dir_path / f"{bv_name}.html"
                geojson_file = output_dir_path / f"{bv_name}.geojson"

                if html_file.exists():
                    self.log(f"HTML地图文件: {html_file}")
                if geojson_file.exists():
                    self.log(f"GeoJSON数据文件: {geojson_file}")

                # 询问是否打开输出目录
                if messagebox.askyesno(
                    "生成完成",
                    f"地图生成成功！\n\n生成位置: {output_dir_path}\n\n是否打开输出目录？",
                ):
                    self.open_directory(str(output_dir_path))

            else:
                self.log("地图生成失败", "error")
                messagebox.showerror("错误", "地图生成失败，请查看日志了解详细信息")

        except Exception as e:
            self.log(f"地图生成过程中出错: {e}", "error")
            messagebox.showerror("错误", f"地图生成失败: {str(e)}")

    def open_directory(self, directory_path: str):
        """打开指定目录"""
        try:
            import subprocess
            import platform

            system = platform.system()
            if system == "Windows":
                subprocess.run(["explorer", directory_path])
            elif system == "Darwin":  # macOS
                subprocess.run(["open", directory_path])
            else:  # Linux and others
                subprocess.run(["xdg-open", directory_path])

        except Exception as e:
            self.log(f"打开目录失败: {e}", "error")

    def validate_input(self):
        """验证输入 - 支持BV号、EP号和SS号"""
        input_text = self.bvid_var.get().strip()
        if not input_text:
            messagebox.showerror("错误", "请输入视频BV号、番剧EP号或番剧SS号")
            return False

        try:
            # 尝试解析输入
            if input_text.startswith("http"):
                # 如果是完整URL，解析URL
                content_type, identifier = parse_bilibili_url(input_text)
                self.content_type = content_type
                self.identifier = identifier
                self.log(f"解析URL: {input_text} -> {content_type}: {identifier}")
            else:
                # 直接输入标识符
                if input_text.startswith("BV"):
                    # 验证BV号格式
                    if not re.match(r"^BV[a-zA-Z0-9]{10}$", input_text):
                        messagebox.showerror(
                            "错误", "BV号格式不正确，应为'BV'+10位字母数字组合"
                        )
                        return False
                    self.content_type = "video"
                    self.identifier = input_text
                elif input_text.startswith("EP") or input_text.startswith("ep"):
                    # EP号格式
                    ep_id = (
                        input_text[2:]
                        if input_text.lower().startswith("ep")
                        else input_text
                    )
                    if not ep_id.isdigit():
                        messagebox.showerror("错误", "EP号格式不正确，应为'EP'+数字")
                        return False
                    self.content_type = "bangumi"
                    self.identifier = f"EP{ep_id}"
                elif input_text.startswith("SS") or input_text.startswith("ss"):
                    # SS号格式
                    season_id = (
                        input_text[2:]
                        if input_text.lower().startswith("ss")
                        else input_text
                    )
                    if not season_id.isdigit():
                        messagebox.showerror("错误", "SS号格式不正确，应为'SS'+数字")
                        return False
                    self.content_type = "season"
                    self.identifier = f"SS{season_id}"
                else:
                    messagebox.showerror(
                        "错误",
                        "输入格式不正确。请输入：\n• BV号（如：BV1xx411c7mD）\n• EP号（如：EP123456）\n• SS号（如：SS12345）\n• 完整链接",
                    )
                    return False

                self.log(
                    f"解析输入: {input_text} -> {self.content_type}: {self.identifier}"
                )

        except ValueError as e:
            messagebox.showerror("错误", str(e))
            return False
        except Exception as e:
            messagebox.showerror("错误", f"解析输入时出错: {str(e)}")
            return False

        # 检查输出目录是否设置
        output_dir = self.config.get("output", "")
        if not output_dir:
            messagebox.showerror("错误", "请先在设置中配置输出目录")
            return False

        return True

    def start_download(self):
        """开始下载 - 更新以支持不同内容类型"""
        if not self.validate_input():
            return

        if self.download_thread and self.download_thread.is_alive():
            messagebox.showinfo("提示", "已有下载任务正在进行中")
            return

        # 检查是否已存在相同标识符的数据
        identifier = self.identifier
        base_output_dir = Path(self.config.get("output", ""))

        # 查找以该标识符开头的目录
        search_pattern = f"{identifier}_*"
        existing_dirs = list(base_output_dir.glob(search_pattern))

        # 检查是否存在数据
        data_exists = False
        existing_files = []

        if existing_dirs:
            for dir_path in existing_dirs:
                csv_file = dir_path / f"{identifier}.csv"
                if csv_file.exists():
                    data_exists = True
                    existing_files.append(str(csv_file))

        # 如果数据已存在，询问用户是否覆盖
        if data_exists:
            try:
                result = self.show_overwrite_dialog(identifier, existing_files)
                if result == "cancel":
                    self.log("用户取消了下载操作")
                    return
                elif result == "overwrite":
                    # 用户选择覆盖，设置覆盖标志
                    self.overwrite_mode = True
                    self.log("用户选择覆盖现有数据，将清空重新下载")
                else:
                    return
            except Exception as e:
                logger.error(f"显示确认对话框时出错: {e}")
                messagebox.showerror("错误", "无法显示确认对话框")
                return
        else:
            self.overwrite_mode = False

        self.stop_flag = False
        self.progress_var.set(0)

        # 保存配置
        self.config.set("corder", self.corder_var.get())
        self.config.set("mapping", self.mapping_var.get())

        # 更新API的cookie
        self.api = BilibiliAPI(self.config.get("cookie", ""))

        # 创建并启动下载线程
        self.download_thread = threading.Thread(target=self.download_comments)
        self.download_thread.daemon = True
        self.download_thread.start()

    def show_overwrite_dialog(self, identifier: str, existing_files: list) -> str:
        """显示覆盖确认对话框 - 更新以支持不同类型内容"""

        dialog = tk.Toplevel(self)
        dialog.title("数据已存在")
        dialog.geometry("520x350")
        dialog.resizable(False, False)
        dialog.transient(self)
        dialog.grab_set()

        result = {"value": "cancel"}

        # 主容器
        main_frame = ttk.Frame(dialog)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)

        # 确定内容类型显示文本
        content_type_text = self.get_content_type_name()

        # 标题
        title_label = ttk.Label(
            main_frame,
            text=f"发现已存在 {identifier} 的 {content_type_text} 数据",
            font=("Microsoft YaHei", 12, "bold"),
            foreground="#d63031",
        )
        title_label.pack(pady=(0, 10))

        # 说明文字
        info_text = f"检测到以下位置已存在该 {content_type_text} 的评论数据：\n\n"

        # 显示文件路径，但限制显示长度
        for i, file_path in enumerate(existing_files[:2]):  # 最多显示2个路径
            # 截取路径的最后部分以便显示
            short_path = (
                str(Path(file_path).parent.name) + "/" + str(Path(file_path).name)
            )
            info_text += f"• {short_path}\n"

        if len(existing_files) > 2:
            info_text += f"... 等共 {len(existing_files)} 个文件"

        info_label = ttk.Label(
            main_frame,
            text=info_text,
            wraplength=480,
            justify="left",
            font=("Microsoft YaHei", 9),
        )
        info_label.pack(pady=(0, 15))

        # 操作说明框
        warning_frame = ttk.LabelFrame(main_frame, text="操作说明", padding=10)
        warning_frame.pack(fill=tk.X, pady=(0, 20))

        warning_text = (
            "• 覆盖数据：清空现有CSV文件中的所有评论数据，重新下载\n"
            "• 取消操作：保持现有数据不变，不进行下载\n\n"
            "⚠️ 覆盖操作不可恢复，请谨慎选择！"
        )

        warning_label = ttk.Label(
            warning_frame,
            text=warning_text,
            wraplength=450,
            justify="left",
            font=("Microsoft YaHei", 9),
            foreground="#e17055",
        )
        warning_label.pack()

        # 按钮区域
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(side=tk.BOTTOM, fill=tk.X, pady=(10, 0))

        def on_overwrite():
            result["value"] = "overwrite"
            dialog.destroy()

        def on_cancel():
            result["value"] = "cancel"
            dialog.destroy()

        style = ttk.Style()

        # 重置并设置取消按钮样式
        style.configure(
            "Cancel.TButton", foreground="black", font=("Microsoft YaHei", 9)
        )

        # 重置并设置覆盖按钮样式
        style.configure(
            "Overwrite.TButton", foreground="black", font=("Microsoft YaHei", 9, "bold")
        )

        # 按钮
        cancel_btn = ttk.Button(
            button_frame,
            text="取消操作",
            command=on_cancel,
            width=12,
            style="Cancel.TButton",
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(10, 0))

        overwrite_btn = ttk.Button(
            button_frame,
            text="覆盖数据",
            command=on_overwrite,
            width=12,
            style="Overwrite.TButton",
        )
        overwrite_btn.pack(side=tk.RIGHT)

        # 确保窗口完全创建后再居中显示
        def center_dialog():
            # 更新窗口以确保所有组件都已渲染
            dialog.update_idletasks()

            # 获取父窗口的位置和大小
            parent_x = self.winfo_rootx()
            parent_y = self.winfo_rooty()
            parent_width = self.winfo_width()
            parent_height = self.winfo_height()

            # 获取对话框的大小
            dialog_width = dialog.winfo_reqwidth()
            dialog_height = dialog.winfo_reqheight()

            # 计算居中位置（相对于父窗口）
            x = parent_x + (parent_width - dialog_width) // 2
            y = parent_y + (parent_height - dialog_height) // 2

            # 确保对话框不会超出屏幕边界
            screen_width = dialog.winfo_screenwidth()
            screen_height = dialog.winfo_screenheight()

            if x < 0:
                x = 0
            elif x + dialog_width > screen_width:
                x = screen_width - dialog_width

            if y < 0:
                y = 0
            elif y + dialog_height > screen_height:
                y = screen_height - dialog_height

            # 设置对话框位置
            dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # 使用after方法延迟执行居中，确保窗口完全创建
        dialog.after(10, center_dialog)

        # 默认焦点在取消按钮上
        cancel_btn.focus_set()

        # 键盘绑定
        dialog.bind("<Escape>", lambda e: on_cancel())
        dialog.bind("<Return>", lambda e: on_overwrite())

        # 确保对话框可见
        dialog.lift()
        dialog.attributes("-topmost", True)
        dialog.after(100, lambda: dialog.attributes("-topmost", False))

        # 等待用户选择
        dialog.wait_window()

        return result["value"]

    def stop_download(self):
        """停止下载"""
        if self.download_thread and self.download_thread.is_alive():
            self.stop_flag = True
            self.log("正在停止下载...")
        else:
            messagebox.showinfo("提示", "没有正在进行的下载任务")

    def clear_log(self):
        """清空日志"""
        self.log_text.delete(1.0, tk.END)

    def log(self, message, level="info"):
        """添加日志，改进显示格式

        Args:
            message: 日志消息
            level: 日志级别，可选值 "info", "success", "warning", "error", "header"
        """
        # 获取当前时间
        import datetime

        current_time = datetime.datetime.now().strftime("%H:%M:%S")

        # 根据消息内容选择标记类型
        tag = level
        if (
            message.startswith("开始获取")
            or message.startswith("视频")
            and "的评论获取完成" in message
        ):
            tag = "header"
        elif "成功" in message or "完成" in message:
            tag = "success"
        elif "错误" in message or "失败" in message:
            tag = "error"
        elif "警告" in message or "未能" in message:
            tag = "warning"

        # 格式化日志消息
        formatted_message = f"[{current_time}] {message}\n"

        # 如果是统计信息，添加额外的缩进和空行
        if message.strip().startswith("  ") and ":" in message:
            formatted_message = f"\n{message}\n"

        # 添加消息到日志文本框
        self.log_text.insert(tk.END, formatted_message, tag)

        # 特殊处理：主要任务开始或结束时添加分隔线
        if tag == "header":
            self.log_text.insert(tk.END, f"{'-'*50}\n", "info")

        # 如果是新部分开始，添加空行
        if "正在" in message and ("获取" in message or "生成" in message):
            self.log_text.insert(tk.END, "\n")

        # 自动滚动到底部
        self.log_text.see(tk.END)

        # 写入到日志文件
        logger.info(message)

    def download_comments(self):
        """下载评论的线程函数 - 重写以支持不同内容类型"""
        try:
            identifier = self.identifier
            content_type = self.content_type

            self.log(
                f"开始获取{('视频' if content_type == 'video' else '番剧')} {identifier} 的评论"
            )

            # 获取内容信息
            content_info = self.api.fetch_content_info(identifier, content_type)

            if content_info.get("code") != 0:
                error_msg = content_info.get("message", "未知错误")
                self.log(
                    f"获取{self.get_content_type_name()}信息失败: {error_msg}",
                    "error",
                )
                return

            # 提取关键信息
            data = content_info.get("data", {})
            aid = data.get("aid")
            content_title = data.get("title", "未知内容")

            if not aid:
                self.log("无法获取有效的AID", "error")
                return

            oid = str(aid)

            self.log(
                f"获取到{('视频' if content_type == 'video' else '番剧')}信息: {content_title}"
            )
            self.log(f"AID: {aid}")

            # 检查是否已经存在包含标题的目录
            base_output_dir = Path(self.config.get("output", ""))
            video_title = content_title
            existing_dir = None

            # 查找以标识符开头的目录
            for item in base_output_dir.glob(f"{identifier}_*"):
                if item.is_dir():
                    existing_dir = item
                    extracted_title = extract_title_from_dirname(item.name)
                    if extracted_title:
                        video_title = extracted_title
                        self.log(f"找到已有目录，使用现有标题: {video_title}")
                        break

            # 如果没有找到现有标题，使用从API获取的标题
            if not existing_dir or video_title == content_title:
                video_title = content_title
                self.log(f"使用API获取的标题: {video_title}")

            # 创建输出目录 - 使用标识符+标题的格式
            dir_name = get_dir_name(identifier, video_title)
            output_dir = base_output_dir / dir_name
            output_dir.mkdir(parents=True, exist_ok=True)

            # 保存内容信息到JSON文件
            content_info_path = output_dir / "content_info.json"
            if not content_info_path.exists() or self.overwrite_mode:
                try:
                    with open(content_info_path, "w", encoding="utf-8") as f:
                        json.dump(content_info, f, ensure_ascii=False, indent=2)
                    self.log(f"已保存内容信息到: {content_info_path}")
                except Exception as e:
                    self.log(f"保存内容信息失败: {e}")

            self.log(
                f"开始获取{('视频' if content_type == 'video' else '番剧')} {identifier} ({video_title}) 的评论"
            )

            # 获取评论总数
            total = self.api.fetch_comment_count(oid)
            if total == 0:
                self.log("未找到评论或获取评论数失败")
                return

            self.log(
                f"该{self.get_content_type_name()}共有 {total} 条评论"
            )

            downloaded_count = 0
            round_num = 0
            recorded_map = {}
            stat_map = {}
            offset_str = ""

            # 从配置获取重试相关参数
            max_retries = self.config.get("max_retries", 3)
            consecutive_empty_limit = self.config.get("consecutive_empty_limit", 2)

            # 用于跟踪连续获取到的空页面数量
            consecutive_empty_pages = 0

            while not self.stop_flag:
                reply_collection = []

                self.log(f"正在获取第 {round_num + 1} 页评论")

                # 如果已下载的评论数大于等于总评论数，且连续空页面数达到限制，则停止获取
                if (
                    downloaded_count >= total
                    and consecutive_empty_pages >= consecutive_empty_limit
                ):
                    self.log(
                        f"{self.get_content_type_name()} {identifier} ({video_title}) 的评论获取完成"
                    )
                    break

                round_num += 1
                retry_count = 0
                success = False

                # 请求评论并处理重试
                while retry_count < max_retries and not success and not self.stop_flag:
                    cmt_info = self.api.fetch_comments(
                        oid, round_num, self.corder_var.get(), offset_str
                    )

                    # 检查API请求是否成功
                    if cmt_info.get("code") != 0:
                        error_msg = cmt_info.get("message", "未知错误")
                        retry_count += 1
                        if retry_count < max_retries:
                            retry_delay = self.config.get("request_retry_delay", 5.0)
                            self.log(
                                f"请求评论失败: {error_msg}，将在 {retry_delay} 秒后重试 ({retry_count}/{max_retries})...",
                                "warning",
                            )
                            time.sleep(retry_delay)
                            continue
                        else:
                            self.log(
                                f"请求评论失败: {error_msg}，已达到最大重试次数 {max_retries}，跳过此页",
                                "error",
                            )
                            break

                    replies = cmt_info.get("data", {}).get("replies", [])

                    # 处理空页面情况
                    if not replies:
                        consecutive_empty_pages += 1
                        retry_count += 1

                        if retry_count < max_retries:
                            retry_delay = self.config.get("request_retry_delay", 5.0)
                            self.log(
                                f"第 {round_num} 页未获取到评论，连续空页面数: {consecutive_empty_pages}，将在 {retry_delay} 秒后重试 ({retry_count}/{max_retries})...",
                                "warning",
                            )
                            time.sleep(retry_delay)
                            continue
                        else:
                            self.log(
                                f"第 {round_num} 页连续 {consecutive_empty_pages} 次未获取到评论，已达到最大重试次数",
                                "warning",
                            )
                            # 不设置success为True，让外层循环继续处理
                            break
                    else:
                        # 获取到了评论，重置连续空页面计数
                        consecutive_empty_pages = 0
                        success = True

                        offset_str = (
                            cmt_info.get("data", {})
                            .get("cursor", {})
                            .get("pagination_reply", {})
                            .get("next_offset", "")
                        )
                        reply_collection.extend(replies)

                # 如果用户停止了下载或达到了连续空页面的限制，则跳出主循环
                if self.stop_flag or (
                    consecutive_empty_pages >= consecutive_empty_limit and not success
                ):
                    if self.stop_flag:
                        self.log("用户停止了下载")
                    else:
                        self.log(
                            f"连续 {consecutive_empty_pages} 页未获取到评论，停止获取"
                        )
                    break

                # 如果请求失败且已重试达到上限，继续下一轮循环（尝试下一页）
                if not success:
                    continue

                # 获取子评论
                for reply in replies:
                    rcount = reply.get("rcount", 0)
                    if rcount == 0:
                        continue

                    reply_replies = reply.get("replies", [])
                    if reply_replies and len(reply_replies) == rcount:
                        reply_collection.extend(reply_replies)
                    else:
                        # 需要额外获取子评论
                        sub_replies = self.fetch_sub_comments(
                            oid, reply.get("rpid"), identifier
                        )
                        reply_collection.extend(sub_replies)

                # 处理置顶评论
                top_replies = cmt_info.get("data", {}).get("top_replies", [])
                if top_replies:
                    reply_collection.extend(top_replies)
                    for reply in top_replies:
                        reply_replies = reply.get("replies", [])
                        if reply_replies:
                            reply_collection.extend(reply_replies)

                # 转换为Comment对象
                comments = []
                for reply in reply_collection:
                    rpid = reply.get("rpid")
                    if rpid not in recorded_map:
                        comment = Comment.from_api_response(reply)
                        comment.bvid = identifier  # 使用统一的标识符

                        recorded_map[rpid] = True
                        comments.append(comment)

                        # 统计地区信息
                        if self.mapping_var.get():
                            location = comment.location
                            if not location or location == "":
                                location = "未知"

                            # 规范化地区名称，与CSV分析保持一致
                            normalized_location = normalize_location(location)

                            # 确保用户ID是字符串类型
                            user_id = str(comment.mid)

                            if normalized_location in stat_map:
                                stat = stat_map[normalized_location]
                                stat.location += 1  # 评论数增加
                                stat.like += comment.like
                                stat.level[comment.current_level] += 1
                                stat.users.add(user_id)  # 添加用户ID到集合
                                stat.update_user_sex(
                                    user_id, comment.sex
                                )  # 更新用户性别统计
                            else:
                                stat = Stat(
                                    name=normalized_location,
                                    location=1,
                                    like=comment.like,
                                )
                                stat.level[comment.current_level] += 1
                                stat.users.add(user_id)  # 添加用户ID到集合
                                stat.update_user_sex(
                                    user_id, comment.sex
                                )  # 更新用户性别统计
                                stat_map[normalized_location] = stat

                # 保存到CSV
                if comments:
                    overwrite_mode = getattr(self, "overwrite_mode", False)
                    save_to_csv(
                        identifier,
                        comments,
                        str(output_dir),
                        video_title,
                        overwrite_mode,
                    )
                    # 如果是覆盖模式，只在第一次调用时覆盖，后续调用应该追加
                    if overwrite_mode:
                        self.overwrite_mode = False  # 重置覆盖标志，后续为追加模式

                downloaded_count += len(comments)
                self.log(f"已获取 {downloaded_count}/{total} 条评论")

                # 更新进度条
                self.progress_var.set(min(100, downloaded_count / total * 100))

            # 生成地图
            if self.mapping_var.get() and stat_map:
                self.log(f"统计到 {len(stat_map)} 个地区的数据")
                for location, stat in stat_map.items():
                    self.log(f"  {location}: {stat.location} 条评论")

                self.log("正在生成评论地区分布地图...")
                unmatched_regions = write_geojson(
                    stat_map, identifier, str(output_dir), video_title
                )
                self.log("地图生成完成")

                # 显示未匹配地区
                if unmatched_regions:
                    unmatched_names = ", ".join(unmatched_regions.keys())
                    self.log(
                        f"有 {len(unmatched_regions)} 个地区未能匹配到地图: {unmatched_names}"
                    )

                    # 单独打印每个未匹配地区的信息
                    for region, count in unmatched_regions.items():
                        self.log(
                            f"  未匹配地区: {region} - {count['comments']}条评论, {count['users']}位用户"
                        )

            self.log("任务完成")
            self.progress_var.set(100)

        except Exception as e:
            self.log(f"下载过程中出错: {e}")
            logger.exception("下载评论出错")

    def fetch_sub_comments(self, oid, rpid, identifier):
        """获取子评论 - 更新以使用统一标识符"""
        page = 1
        all_replies = []

        try:
            while not self.stop_flag:
                self.log(f"获取评论 {rpid} 的子评论，第 {page} 页")

                # 构建请求参数
                params = {
                    "oid": oid,
                    "type": "1",
                    "root": str(rpid),
                    "ps": "20",
                    "pn": str(page),
                }

                # 使用类似主评论的请求方式
                try:
                    # 尝试使用requests库
                    import requests

                    headers = {
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0",
                        "Referer": f"https://www.bilibili.com/{'video' if self.content_type == 'video' else 'bangumi/play'}/{identifier}",
                        "Origin": "https://www.bilibili.com",
                        "Accept": "application/json, text/plain, */*",
                    }

                    if self.api.cookie:
                        headers["Cookie"] = self.api.cookie

                    # 请求前添加延迟
                    self.api.sleep_between_requests()

                    url = "https://api.bilibili.com/x/v2/reply/reply?" + "&".join(
                        [f"{k}={v}" for k, v in params.items()]
                    )
                    response = requests.get(url, headers=headers)

                    if response.status_code == 200:
                        data = response.json()

                        if data.get("code") != 0:
                            self.log(
                                f"获取子评论失败: {data.get('message', '未知错误')}"
                            )
                            break

                        replies = data.get("data", {}).get("replies", [])

                        if not replies:
                            break

                        all_replies.extend(replies)
                        page += 1
                    else:
                        self.log(f"获取子评论请求失败，状态码: {response.status_code}")
                        break

                except Exception as e:
                    self.log(f"获取子评论出错: {e}")
                    # 请求失败添加重试延迟
                    self.api.sleep_between_requests("retry")
                    break

        except Exception as e:
            self.log(f"子评论处理过程中出错: {e}")

        return all_replies

    def generate_wordcloud_from_csv(self):
        """从现有CSV文件生成词云"""

        # 获取输出目录
        output_base_dir = self.config.get("output", "")
        if not output_base_dir:
            messagebox.showerror("错误", "请先在设置中配置输出目录")
            return

        output_path = Path(output_base_dir)
        if not output_path.exists():
            messagebox.showerror("错误", f"输出目录不存在: {output_base_dir}")
            return

        # 选择CSV文件
        file_path = filedialog.askopenfilename(
            title="选择CSV文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")],
            initialdir=output_base_dir,
        )

        if not file_path:
            return

        csv_path = Path(file_path)

        # 验证选择的CSV文件是否在输出目录下
        try:
            csv_path.relative_to(output_path)
            self.log(f"选择的CSV文件: {csv_path}")
        except ValueError:
            self.log(f"警告: 选择的CSV文件不在输出目录下: {csv_path}", "warning")

        # 选择输出目录
        suggested_output_dir = (
            csv_path.parent
            if csv_path.parent.is_relative_to(output_path)
            else output_base_dir
        )

        output_dir = filedialog.askdirectory(
            title="选择词云输出目录",
            initialdir=str(suggested_output_dir),
        )

        if not output_dir:
            return

        output_dir_path = Path(output_dir)

        # 生成词云前的确认信息
        self.log(f"开始从CSV文件生成词云")
        self.log(f"  CSV文件: {csv_path.name}")
        self.log(f"  输出目录: {output_dir_path}")

        try:
            # 导入词云生成模块
            from store.wordcloud_exporter import generate_wordcloud_from_csv

            # 生成词云
            result = generate_wordcloud_from_csv(str(csv_path), str(output_dir_path))

            if result:
                self.log("词云生成成功", "success")

                # 检查生成的文件
                bv_name = csv_path.stem
                wordcloud_file = output_dir_path / f"{bv_name}_wordcloud.html"

                if wordcloud_file.exists():
                    self.log(f"词云HTML文件: {wordcloud_file}")

                # 询问是否打开输出目录
                if messagebox.askyesno(
                    "生成完成",
                    f"词云生成成功！\n\n生成位置: {output_dir_path}\n\n是否打开输出目录？",
                ):
                    self.open_directory(str(output_dir_path))

            else:
                self.log("词云生成失败", "error")
                messagebox.showerror("错误", "词云生成失败，请查看日志了解详细信息")

        except Exception as e:
            self.log(f"词云生成过程中出错: {e}", "error")
            messagebox.showerror("错误", f"词云生成失败: {str(e)}")

    def download_images_from_csv(self):
        """从CSV文件下载图片"""
        # 获取输出目录
        output_base_dir = self.config.get("output", "")
        if not output_base_dir:
            messagebox.showerror("错误", "请先在设置中配置输出目录")
            return

        output_path = Path(output_base_dir)
        if not output_path.exists():
            messagebox.showerror("错误", f"输出目录不存在: {output_base_dir}")
            return

        # 选择CSV文件
        file_path = filedialog.askopenfilename(
            title="选择包含图片链接的CSV文件",
            filetypes=[("CSV文件", "*.csv"), ("所有文件", "*.*")],
            initialdir=output_base_dir,
        )

        if not file_path:
            return

        csv_path = Path(file_path)

        # 验证CSV文件
        try:
            csv_path.relative_to(output_path)
            self.log(f"选择的CSV文件: {csv_path.name}")
        except ValueError:
            self.log(f"警告: 选择的CSV文件不在输出目录下: {csv_path}", "warning")

        # 确认下载
        if not messagebox.askyesno(
            "确认下载",
            f"将从以下CSV文件中提取并下载图片：\n\n{csv_path.name}\n\n"
            "图片将保存到同目录下的 images 文件夹中。\n"
            "已存在的图片会自动跳过。\n\n"
            "确定要开始下载吗？",
        ):
            return

        # 在新线程中执行下载
        def download_thread():
            try:
                self.log("开始从CSV文件提取并下载图片...")

                # 导入下载函数
                from store.image_downloader import download_images_from_csv

                # 执行下载
                download_images_from_csv(str(csv_path))

                self.log("图片下载任务完成", "success")

                # 询问是否打开图片目录
                images_dir = csv_path.parent / "images"
                if images_dir.exists():
                    self.after(
                        100, lambda: self.ask_open_images_directory(str(images_dir))
                    )

            except Exception as e:
                self.log(f"下载图片时出错: {e}", "error")
                logger.exception("下载图片出错")

        # 启动下载线程
        import threading

        thread = threading.Thread(target=download_thread, daemon=True)
        thread.start()

    def ask_open_images_directory(self, images_dir: str):
        """询问是否打开图片目录"""
        if messagebox.askyesno(
            "下载完成",
            f"图片下载完成！\n\n图片保存位置: {images_dir}\n\n是否打开图片目录？",
        ):
            self.open_directory(images_dir)
