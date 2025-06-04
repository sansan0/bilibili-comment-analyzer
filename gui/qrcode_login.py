import tkinter as tk
from tkinter import ttk, messagebox
import threading
import time
import logging
import requests
import qrcode
from PIL import Image, ImageTk

logger = logging.getLogger(__name__)


class QRCodeLoginDialog:
    """B站二维码登录对话框"""

    def __init__(self, parent):
        """初始化对话框"""
        self.parent = parent
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("B站扫码登录")
        self.dialog.resizable(False, False)
        self.dialog.transient(parent)
        self.dialog.grab_set()

        # 设置变量
        self.cookie = None
        self.qrcode_key = None
        self.polling = False
        self.polling_thread = None

        # 初始化UI
        self.init_ui()

        # 设置大小并居中显示
        self.setup_window_position()

        # 生成二维码
        self.generate_qrcode()

    def setup_window_position(self):
        """设置窗口大小和位置"""
        # 设定窗口大小
        width = 300
        height = 450

        # 计算居中位置
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        x = (screen_width - width) // 2
        y = (screen_height - height) // 2

        # 一次性设置大小和位置
        self.dialog.geometry(f"{width}x{height}+{x}+{y}")

    def init_ui(self):
        """初始化UI"""
        # 标题标签
        ttk.Label(
            self.dialog,
            text="请使用B站手机客户端扫描二维码登录",
            font=("Microsoft YaHei", 10),
        ).pack(pady=10)

        # 图片容器
        self.image_label = ttk.Label(self.dialog)
        self.image_label.pack(pady=10)

        # 状态标签
        self.status_label = ttk.Label(
            self.dialog, text="正在加载二维码...", font=("Microsoft YaHei", 9)
        )
        self.status_label.pack(pady=5)

        # 提示信息
        ttk.Label(
            self.dialog,
            text="提示: 扫码后请在手机上确认登录",
            font=("Microsoft YaHei", 8),
        ).pack(pady=10)

        # 操作按钮
        btn_frame = ttk.Frame(self.dialog)
        btn_frame.pack(pady=20, fill=tk.X)

        # 刷新按钮
        refresh_btn = ttk.Button(
            btn_frame, text="🔄 刷新二维码", command=self.generate_qrcode, width=15
        )
        refresh_btn.pack(side=tk.LEFT, padx=20, ipady=8)

        # 取消按钮
        cancel_btn = ttk.Button(
            btn_frame, text="❌ 取消", command=self.cancel, width=12
        )
        cancel_btn.pack(side=tk.RIGHT, padx=20, ipady=8)

    def update_status_safe(self, message):
        """线程安全地更新状态标签"""
        try:
            if hasattr(self, "dialog") and self.dialog.winfo_exists():
                self.dialog.after(0, lambda: self._update_status_label(message))
        except Exception as e:
            logger.debug(f"更新状态时出错: {e}")

    def _update_status_label(self, message):
        """在主线程中更新状态标签"""
        try:
            if hasattr(self, "status_label") and self.status_label.winfo_exists():
                self.status_label.config(text=message)
        except Exception as e:
            logger.debug(f"更新标签时出错: {e}")

    def schedule_gui_update(self, callback):
        """线程安全地调度GUI更新"""
        try:
            if hasattr(self, "dialog") and self.dialog.winfo_exists():
                self.dialog.after(0, callback)
        except Exception as e:
            logger.debug(f"调度GUI更新时出错: {e}")

    def generate_qrcode(self):
        """生成二维码"""
        self.status_label.config(text="正在获取二维码...")

        try:
            # 构建请求头
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Referer": "https://www.bilibili.com/",
                "Origin": "https://www.bilibili.com",
                "Accept": "application/json, text/plain, */*",
                "Connection": "keep-alive",
            }

            # 使用更完善的请求方式
            response = requests.get(
                "https://passport.bilibili.com/x/passport-login/web/qrcode/generate",
                headers=headers,
                timeout=10,
            )

            # 记录详细的响应信息用于调试
            status_code = response.status_code
            response_text = response.text

            logger.info(f"获取二维码响应状态码: {status_code}")
            logger.info(
                f"获取二维码响应内容: {response_text[:200]}..."
            )  # 只记录前200个字符

            # 检查HTTP状态码
            if status_code != 200:
                self.status_label.config(text=f"获取二维码失败: HTTP {status_code}")
                logger.error(f"获取二维码HTTP错误: {status_code}")
                return

            # 尝试解析JSON
            try:
                data = response.json()
            except ValueError as e:
                # JSON解析失败，可能是无效响应或网络问题
                self.status_label.config(text="获取二维码失败: 服务器响应无效")
                logger.error(f"JSON解析错误: {e}, 原始响应: {response_text[:50]}...")
                return

            if data.get("code") != 0:
                error_msg = data.get("message", "未知错误")
                self.status_label.config(text=f"获取二维码失败: {error_msg}")
                logger.error(f"API错误: {error_msg}")
                return

            # 获取二维码URL和密钥
            if (
                "data" not in data
                or "url" not in data["data"]
                or "qrcode_key" not in data["data"]
            ):
                self.status_label.config(text="获取二维码失败: 响应格式错误")
                logger.error(f"API响应格式错误: {data}")
                return

            self.qrcode_url = data["data"]["url"]
            self.qrcode_key = data["data"]["qrcode_key"]

            logger.info(f"成功获取二维码URL: {self.qrcode_url[:30]}...")
            logger.info(f"二维码密钥: {self.qrcode_key}")

            # 使用qrcode库生成二维码
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(self.qrcode_url)
            qr.make(fit=True)

            # 创建PIL图像
            img = qr.make_image(fill_color="black", back_color="white")
            img = img.resize((200, 200), Image.LANCZOS)

            # 将PIL图像转换为Tkinter图像
            self.photoimage = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.photoimage)

            # 设置状态
            self.status_label.config(text="等待扫描...")

            # 开始轮询检查登录状态
            self.start_polling()

        except requests.exceptions.RequestException as e:
            # 处理网络请求异常
            self.status_label.config(text="网络连接失败，请检查网络")
            logger.error(f"网络请求错误: {e}")
        except Exception as e:
            self.status_label.config(text="生成二维码失败，请重试")
            logger.error(f"生成二维码失败: {e}")

    def start_polling(self):
        """开始轮询检查登录状态"""
        if self.polling:
            return

        self.polling = True
        self.polling_thread = threading.Thread(target=self.poll_login_status)
        self.polling_thread.daemon = True
        self.polling_thread.start()

    def poll_login_status(self):
        """轮询检查登录状态"""
        try:
            # 构建请求头
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
                "Referer": "https://www.bilibili.com/",
                "Origin": "https://www.bilibili.com",
                "Accept": "application/json, text/plain, */*",
                "Connection": "keep-alive",
            }

            while self.polling and self.qrcode_key:
                try:
                    # 检查对话框是否仍然存在
                    if not hasattr(self, "dialog") or not self.dialog.winfo_exists():
                        logger.info("对话框已关闭，停止轮询")
                        self.polling = False
                        break

                    # 请求检查登录状态
                    response = requests.get(
                        "https://passport.bilibili.com/x/passport-login/web/qrcode/poll",
                        params={"qrcode_key": self.qrcode_key},
                        headers=headers,
                        timeout=10,
                    )

                    status_code = response.status_code

                    if status_code != 200:
                        self.update_status_safe(f"检查登录状态失败: HTTP {status_code}")
                        logger.error(f"检查登录状态HTTP错误: {status_code}")
                        time.sleep(2)
                        continue

                    try:
                        data = response.json()
                    except ValueError as e:
                        logger.error(
                            f"JSON解析错误: {e}, 原始响应: {response.text[:50]}..."
                        )
                        time.sleep(2)
                        continue

                    if data.get("code") != 0:
                        error_msg = data.get("message", "未知错误")
                        self.update_status_safe(f"检查登录状态失败: {error_msg}")
                        logger.error(f"API错误: {error_msg}")
                        time.sleep(2)
                        continue

                    # 获取扫码状态
                    if "data" not in data or "code" not in data["data"]:
                        logger.error(f"API响应格式错误: {data}")
                        time.sleep(2)
                        continue

                    code = data["data"]["code"]
                    message = data["data"].get("message", "")

                    logger.info(f"扫码状态: code={code}, message={message}")

                    if code == 0:
                        # 从响应的set-cookie头部提取cookie
                        cookies = response.cookies
                        cookie_str = "; ".join([f"{k}={v}" for k, v in cookies.items()])

                        # 为确保获取所有cookie(有时服务端会分多次设置cookie)，尝试从接口返回提取更多信息
                        if (
                            not cookie_str
                            and "data" in data
                            and "url" in data["data"]
                            and data["data"]["url"]
                        ):
                            try:
                                # 尝试从url参数中提取cookie信息
                                url = data["data"]["url"]
                                logger.info(f"获取到URL: {url[:50]}...")

                                if (
                                    "DedeUserID=" in url
                                    and "SESSDATA=" in url
                                    and "bili_jct=" in url
                                ):
                                    # 使用非常简化的方式来解析url参数中的cookie
                                    parts = url.split("?")[1].split("&")
                                    extracted_cookies = {}
                                    for part in parts:
                                        if "=" in part and not part.startswith(
                                            "gourl="
                                        ):
                                            k, v = part.split("=", 1)
                                            extracted_cookies[k] = v

                                    # 构建cookie字符串
                                    if (
                                        "DedeUserID" in extracted_cookies
                                        and "SESSDATA" in extracted_cookies
                                        and "bili_jct" in extracted_cookies
                                    ):
                                        cookie_str = "; ".join(
                                            [
                                                f"{k}={v}"
                                                for k, v in extracted_cookies.items()
                                            ]
                                        )
                                        logger.info(
                                            f"从URL提取到cookie: {cookie_str[:20]}..."
                                        )
                            except Exception as e:
                                logger.error(f"从URL提取cookie失败: {e}")

                        if cookie_str:
                            self.cookie = cookie_str
                            self.schedule_gui_update(self.on_login_success)
                        else:
                            self.update_status_safe("登录成功，但获取cookie失败")
                            logger.error("登录成功但未能获取cookie")
                        self.polling = False
                        return

                    elif code == 86038:  # 二维码已失效
                        self.update_status_safe("二维码已失效，请刷新")
                        self.polling = False
                        return

                    elif code == 86090:  # 二维码已扫码未确认
                        self.update_status_safe("扫描成功，请在手机上确认登录")

                    elif code == 86101:  # 未扫码
                        self.update_status_safe("等待扫描...")

                    # 等待1秒后继续轮询
                    time.sleep(1)

                except requests.exceptions.RequestException as e:
                    # 处理请求异常，但继续轮询
                    logger.error(f"轮询请求异常: {e}")
                    self.update_status_safe("网络连接异常，重试中...")
                    time.sleep(2)

        except Exception as e:
            logger.error(f"轮询登录状态失败: {e}")
            self.update_status_safe("检查登录状态出错，请重试")
            self.polling = False

    def on_login_success(self):
        """登录成功回调"""
        try:
            if hasattr(self, "status_label") and self.status_label.winfo_exists():
                self.status_label.config(text="登录成功！")
            messagebox.showinfo("登录成功", "B站账号登录成功！")
            self.dialog.destroy()
        except Exception as e:
            logger.debug(f"登录成功回调时出错: {e}")

    def cancel(self):
        """取消登录"""
        self.polling = False
        if self.polling_thread and self.polling_thread.is_alive():
            # 线程会自动结束，无需强制终止
            pass
        try:
            self.dialog.destroy()
        except Exception as e:
            logger.debug(f"关闭对话框时出错: {e}")

    def wait_for_result(self):
        """等待结果"""
        self.parent.wait_window(self.dialog)
        return self.cookie
