import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox
import logging

from config import Config, DEFAULT_CONFIG
from gui.tooltip import create_tooltip
from gui.qrcode_login import QRCodeLoginDialog

logger = logging.getLogger(__name__)


class SettingsFrame(ttk.Frame):
    """设置界面"""

    def __init__(self, parent):
        """初始化界面"""
        super().__init__(parent)
        self.config = Config()
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        # 基础设置区域
        settings_frame = ttk.LabelFrame(self, text="基础设置")
        settings_frame.pack(fill=tk.X, padx=10, pady=5)

        # Cookie设置
        ttk.Label(settings_frame, text="Cookie:").grid(
            row=0, column=0, padx=5, pady=5, sticky=tk.W
        )

        cookie_frame = ttk.Frame(settings_frame)
        cookie_frame.grid(row=0, column=1, padx=5, pady=5, sticky=tk.W + tk.E)

        self.cookie_text = scrolledtext.ScrolledText(
            cookie_frame, wrap=tk.WORD, height=2
        )
        self.cookie_text.pack(fill=tk.X, expand=True)
        self.cookie_text.insert(tk.END, self.config.get("cookie", ""))

        # 添加扫码登录按钮
        login_frame = ttk.Frame(settings_frame)
        login_frame.grid(row=1, column=1, padx=5, pady=0, sticky=tk.W)
        ttk.Button(login_frame, text="📱 扫码登录", command=self.show_qrcode_login).pack(
            side=tk.LEFT
        )

        # 提示信息
        ttk.Label(
            settings_frame,
            text="提示: Cookie需要登录B站后获取，用于获取评论信息。点击扫码登录，打开b站app扫码即可，请你妥善保管Cookie，别提供给任何人",
        ).grid(row=2, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)

        # 输出目录设置
        ttk.Label(settings_frame, text="默认输出目录:").grid(
            row=3, column=0, padx=5, pady=5, sticky=tk.W
        )

        output_frame = ttk.Frame(settings_frame)
        output_frame.grid(row=3, column=1, padx=5, pady=5, sticky=tk.W + tk.E)

        self.output_var = tk.StringVar(value=self.config.get("output", ""))
        ttk.Entry(output_frame, textvariable=self.output_var).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )
        ttk.Button(output_frame, text="📁 浏览", command=self.select_output_dir).pack(
            side=tk.RIGHT, padx=5
        )

        # 默认评论排序
        ttk.Label(settings_frame, text="默认评论排序:").grid(
            row=5, column=0, padx=5, pady=5, sticky=tk.W
        )

        corder_frame = ttk.Frame(settings_frame)
        corder_frame.grid(row=5, column=1, padx=5, pady=5, sticky=tk.W)

        self.corder_var = tk.IntVar(value=self.config.get("corder", 1))
        ttk.Radiobutton(
            corder_frame, text="按时间", variable=self.corder_var, value=0
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            corder_frame, text="按点赞数", variable=self.corder_var, value=1
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            corder_frame, text="按回复数", variable=self.corder_var, value=2
        ).pack(side=tk.LEFT, padx=5)

        # 默认视频排序
        ttk.Label(settings_frame, text="默认视频排序:").grid(
            row=6, column=0, padx=5, pady=5, sticky=tk.W
        )

        vorder_frame = ttk.Frame(settings_frame)
        vorder_frame.grid(row=6, column=1, padx=5, pady=5, sticky=tk.W)

        self.vorder_var = tk.StringVar(value=self.config.get("vorder", "pubdate"))
        ttk.Radiobutton(
            vorder_frame, text="最新发布", variable=self.vorder_var, value="pubdate"
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            vorder_frame, text="最多播放", variable=self.vorder_var, value="click"
        ).pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(
            vorder_frame, text="最多收藏", variable=self.vorder_var, value="stow"
        ).pack(side=tk.LEFT, padx=5)

        # 默认生成地图选项
        self.mapping_var = tk.BooleanVar(value=self.config.get("mapping", True))
        ttk.Checkbutton(
            settings_frame, text="默认生成评论地区分布地图", variable=self.mapping_var
        ).grid(row=7, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)
    
        # 添加图片下载选项
        self.download_images_var = tk.BooleanVar(value=self.config.get("download_images", False))
        download_images_checkbox = ttk.Checkbutton(
            settings_frame, text="下载评论时自动获取图片", variable=self.download_images_var
        )
        download_images_checkbox.grid(row=8, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)

        # 添加图片下载的提示
        create_tooltip(
            download_images_checkbox,
            "勾选后下载评论时会同时下载评论中的图片\n"
            "不勾选可大幅提升下载速度\n"
            "即使不勾选，评论完成后也可以点击【获取图片】按钮单独下载图片\n"
            "图片链接始终会保存在CSV文件中"
        )

        # 添加请求延迟设置区域
        delay_frame = ttk.LabelFrame(self, text="请求延迟和重试设置")
        delay_frame.pack(fill=tk.X, padx=10, pady=5)

        # 第一行：最小和最大请求延迟
        ttk.Label(delay_frame, text="最小请求延迟(秒):").grid(
            row=0, column=0, padx=5, pady=5, sticky=tk.W
        )
        self.min_delay_var = tk.DoubleVar(
            value=self.config.get("request_delay_min", 1.0)
        )
        ttk.Spinbox(
            delay_frame,
            from_=0.1,
            to=5.0,
            increment=0.1,
            textvariable=self.min_delay_var,
            width=8,
        ).grid(row=0, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(delay_frame, text="最大请求延迟(秒):").grid(
            row=0, column=2, padx=(20, 5), pady=5, sticky=tk.W
        )
        self.max_delay_var = tk.DoubleVar(
            value=self.config.get("request_delay_max", 2.0)
        )
        ttk.Spinbox(
            delay_frame,
            from_=0.5,
            to=10.0,
            increment=0.1,
            textvariable=self.max_delay_var,
            width=8,
        ).grid(row=0, column=3, padx=5, pady=5, sticky=tk.W)

        # 第二行：重试等待时间和最大重试次数
        ttk.Label(delay_frame, text="重试等待时间(秒):").grid(
            row=1, column=0, padx=5, pady=5, sticky=tk.W
        )
        self.retry_delay_var = tk.DoubleVar(
            value=self.config.get("request_retry_delay", 5.0)
        )
        ttk.Spinbox(
            delay_frame,
            from_=1.0,
            to=30.0,
            increment=1.0,
            textvariable=self.retry_delay_var,
            width=8,
        ).grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(delay_frame, text="最大重试次数:").grid(
            row=1, column=2, padx=(20, 5), pady=5, sticky=tk.W
        )
        self.max_retries_var = tk.IntVar(value=self.config.get("max_retries", 3))
        ttk.Spinbox(
            delay_frame,
            from_=0,
            to=10,
            increment=1,
            textvariable=self.max_retries_var,
            width=8,
        ).grid(row=1, column=3, padx=5, pady=5, sticky=tk.W)

        # 第三行：连续空页面限制
        ttk.Label(delay_frame, text="连续空页面限制:").grid(
            row=2, column=0, padx=5, pady=5, sticky=tk.W
        )
        self.consecutive_empty_limit_var = tk.IntVar(
            value=self.config.get("consecutive_empty_limit", 2)
        )
        ttk.Spinbox(
            delay_frame,
            from_=1,
            to=5,
            increment=1,
            textvariable=self.consecutive_empty_limit_var,
            width=8,
        ).grid(row=2, column=1, padx=5, pady=5, sticky=tk.W)

        # 说明文字
        ttk.Label(
            delay_frame, text="说明: 请求延迟越大对账号风险越低，但会下载更慢，批量下载谨慎使用"
        ).grid(row=3, column=0, columnspan=4, padx=5, pady=5, sticky=tk.W)
        ttk.Label(
            delay_frame,
            text="最大重试次数适用于所有类型的请求失败（网络错误、空结果等），连续空页面限制一般不要动",
        ).grid(row=4, column=0, columnspan=4, padx=5, pady=0, sticky=tk.W)

        # 操作按钮
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=20)
        button_frame.pack_propagate(False)  # 防止内容影响frame大小
        button_frame.configure(height=120)  # 设置固定高度

        # 创建按钮容器，居中显示
        buttons_container = ttk.Frame(button_frame)
        buttons_container.pack(expand=True)

        # 保存设置按钮
        save_btn = ttk.Button(
            buttons_container, 
            text="💾 保存设置", 
            command=self.save_settings,
            width=20
        )
        save_btn.pack(side=tk.LEFT, padx=15, pady=10, ipady=10)
        save_btn.configure(style="Large.TButton")

        # 恢复默认按钮
        reset_btn = ttk.Button(
            buttons_container, 
            text="🔄 恢复默认", 
            command=self.restore_defaults,
            width=20
        )
        reset_btn.pack(side=tk.LEFT, padx=15, pady=10, ipady=10)
        reset_btn.configure(style="Large.TButton")

        # 添加简单的提示文字
        tip_label = ttk.Label(
            button_frame,
            text="💡 记得点击「保存设置」按钮使修改生效！",
            font=("Microsoft YaHei", 10, "bold"),
            foreground="#d35400"
        )
        tip_label.pack(pady=(10, 0))

        # 配置按钮样式
        style = ttk.Style()
        style.configure("Large.TButton", 
                       font=("Microsoft YaHei", 12, "bold"))

    def show_qrcode_login(self):
        """显示二维码登录对话框"""
        dialog = QRCodeLoginDialog(self)
        cookie = dialog.wait_for_result()

        # 如果获取到cookie，则更新cookie输入框
        if cookie:
            logger.info("二维码登录成功，已获取cookie")
            self.cookie_text.delete(1.0, tk.END)
            self.cookie_text.insert(tk.END, cookie)
            # 立即保存设置
            self.config.set("cookie", cookie)
            messagebox.showinfo("设置已保存", "登录cookie已自动保存")

    def select_output_dir(self):
        """选择输出目录"""
        directory = filedialog.askdirectory(initialdir=self.output_var.get())
        if directory:
            self.output_var.set(directory)

    def save_settings(self):
        """保存设置"""
        # 验证请求延迟设置
        min_delay = self.min_delay_var.get()
        max_delay = self.max_delay_var.get()

        if min_delay > max_delay:
            messagebox.showerror("错误", "最小请求延迟不能大于最大请求延迟")
            return

        if min_delay < 0.1:
            if not messagebox.askyesno(
                "警告", "请求延迟过小可能导致被B站限流，确定要设置这么小的延迟吗？"
            ):
                return

        self.config.set("cookie", self.cookie_text.get(1.0, tk.END).strip())
        self.config.set("output", self.output_var.get())
        self.config.set("corder", self.corder_var.get())
        self.config.set("vorder", self.vorder_var.get())
        self.config.set("mapping", self.mapping_var.get())
        self.config.set("download_images", self.download_images_var.get())

        # 保存请求延迟设置
        self.config.set("request_delay_min", min_delay)
        self.config.set("request_delay_max", max_delay)
        self.config.set("request_retry_delay", self.retry_delay_var.get())
        self.config.set("max_retries", self.max_retries_var.get())
        self.config.set(
            "consecutive_empty_limit", self.consecutive_empty_limit_var.get()
        )

        messagebox.showinfo("成功", "设置已保存")
        logger.info("配置已保存")

    def restore_defaults(self):
        """恢复默认设置"""
        if messagebox.askyesno("确认", "确定要恢复默认设置吗？"):
            # 使用导入的默认配置

            # 更新配置
            for key, value in DEFAULT_CONFIG.items():
                self.config.set(key, value)

            # 更新界面
            self.cookie_text.delete(1.0, tk.END)
            self.output_var.set(DEFAULT_CONFIG["output"])
            self.corder_var.set(DEFAULT_CONFIG["corder"])
            self.vorder_var.set(DEFAULT_CONFIG["vorder"])
            self.mapping_var.set(DEFAULT_CONFIG["mapping"])
            self.download_images_var.set(DEFAULT_CONFIG["download_images"]) 
            self.min_delay_var.set(DEFAULT_CONFIG["request_delay_min"])
            self.max_delay_var.set(DEFAULT_CONFIG["request_delay_max"])
            self.retry_delay_var.set(DEFAULT_CONFIG["request_retry_delay"])
            self.max_retries_var.set(DEFAULT_CONFIG["max_retries"])
            self.consecutive_empty_limit_var.set(
                DEFAULT_CONFIG["consecutive_empty_limit"]
            )

            messagebox.showinfo("成功", "设置已恢复默认")
            logger.info("配置已恢复默认")
