import tkinter as tk
from tkinter import ttk, messagebox
import logging
import threading
import socket
import webbrowser
from pathlib import Path
import time
import os
import http.server
import socketserver
from typing import Optional
import queue
import tempfile
import shutil

from config import Config

logger = logging.getLogger(__name__)

# 线程安全的消息队列
ui_update_queue = queue.Queue()


class StoppableHTTPServer(socketserver.TCPServer):
    """可停止的HTTP服务器"""

    allow_reuse_address = True

    def run(self):
        try:
            self.serve_forever()
        finally:
            self.server_close()


class BrowseFrame(ttk.Frame):
    """浏览已下载评论的界面"""

    def __init__(self, parent):
        """初始化界面"""
        super().__init__(parent)
        self.config = Config()
        self.servers = {}  # 跟踪正在运行的服务器 {port: server_info}
        self.temp_dirs = {}  # 跟踪临时目录 {port: temp_dir_path}
        self.init_ui()

        # 启动UI更新检查器
        self.check_ui_updates()

    def init_ui(self):
        """初始化UI"""
        # 当前目录显示区域
        directory_frame = ttk.LabelFrame(self, text="当前输出目录")
        directory_frame.pack(fill=tk.X, padx=10, pady=5)

        # 目录路径显示
        dir_display_frame = ttk.Frame(directory_frame)
        dir_display_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(dir_display_frame, text="路径:", font=("Microsoft YaHei", 9)).pack(
            side=tk.LEFT, padx=(0, 5)
        )

        self.current_dir_var = tk.StringVar()
        self.dir_label = ttk.Label(
            dir_display_frame,
            textvariable=self.current_dir_var,
            font=("Microsoft YaHei", 9),
            foreground="#2c3e50",
            relief=tk.SUNKEN,
            padding=5,
        )
        self.dir_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 5))

        # 打开目录按钮
        open_dir_btn = ttk.Button(
            dir_display_frame,
            text="📁 打开目录",
            command=self.open_current_directory,
            width=12,
        )
        open_dir_btn.pack(side=tk.RIGHT, padx=5)

        # 目录状态显示
        self.dir_status_var = tk.StringVar()
        self.dir_status_label = ttk.Label(
            directory_frame,
            textvariable=self.dir_status_var,
            font=("Microsoft YaHei", 8),
            foreground="#7f8c8d",
        )
        self.dir_status_label.pack(padx=5, pady=(0, 5))

        # 头部工具栏
        toolbar_frame = ttk.Frame(self)
        toolbar_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Button(toolbar_frame, text="🔄 刷新列表", command=self.refresh_items).pack(
            side=tk.LEFT, padx=5
        )
        self.stop_all_btn = ttk.Button(
            toolbar_frame,
            text="🛑 停止所有服务器",
            command=self.stop_all_servers,
            state="disabled",
        )
        self.stop_all_btn.pack(side=tk.LEFT, padx=5)

        # 状态信息
        self.status_var = tk.StringVar(value="就绪")
        ttk.Label(toolbar_frame, textvariable=self.status_var).pack(
            side=tk.RIGHT, padx=5
        )

        # 项目列表区域
        list_frame = ttk.LabelFrame(self, text="已下载项目列表")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 创建带滚动条的容器
        container = ttk.Frame(list_frame)
        container.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # 创建Canvas和滚动条
        self.canvas = tk.Canvas(container)
        scrollbar = ttk.Scrollbar(
            container, orient="vertical", command=self.canvas.yview
        )
        self.scrollable_frame = ttk.Frame(self.canvas)

        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")),
        )

        self.canvas.create_window((0, 0), window=self.scrollable_frame, anchor="nw")
        self.canvas.configure(yscrollcommand=scrollbar.set)

        # 放置Canvas和滚动条
        self.canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        # 活动服务器列表
        server_frame = ttk.LabelFrame(self, text="活动服务器")
        server_frame.pack(fill=tk.X, padx=10, pady=5)

        # 创建表格视图
        self.server_tree = ttk.Treeview(
            server_frame, columns=("title", "port", "status"), show="headings"
        )
        self.server_tree.heading("title", text="视频标题")
        self.server_tree.heading("port", text="端口")
        self.server_tree.heading("status", text="状态")

        self.server_tree.column("title", width=300, anchor="w")
        self.server_tree.column("port", width=70, anchor="center")
        self.server_tree.column("status", width=100, anchor="center")

        # 添加右键菜单
        self.context_menu = tk.Menu(self.server_tree, tearoff=0)
        self.context_menu.add_command(
            label="停止服务器", command=self.stop_selected_server
        )

        self.server_tree.bind("<Button-3>", self.show_context_menu)

        self.server_tree.pack(fill=tk.X, padx=5, pady=5)

        # 初始加载项目
        self.refresh_items()

    def update_current_directory(self):
        """更新当前目录显示"""
        try:
            # 获取当前设置的输出目录
            current_dir = self.config.get("output", "")

            if not current_dir:
                self.current_dir_var.set("未设置输出目录")
                self.dir_status_var.set("⚠️ 请在设置中配置输出目录")
                self.dir_status_label.config(foreground="#e74c3c")
                return

            # 显示目录路径
            self.current_dir_var.set(current_dir)

            # 检查目录状态
            output_path = Path(current_dir)
            if not output_path.exists():
                self.dir_status_var.set("⚠️ 目录不存在，将会自动创建")
                self.dir_status_label.config(foreground="#f39c12")
                # 尝试创建目录
                try:
                    output_path.mkdir(parents=True, exist_ok=True)
                    self.dir_status_var.set("✅ 目录已创建")
                    self.dir_status_label.config(foreground="#27ae60")
                except Exception as e:
                    self.dir_status_var.set(f"❌ 无法创建目录: {str(e)}")
                    self.dir_status_label.config(foreground="#e74c3c")
            else:
                # 统计目录内容
                bv_folders = list(output_path.glob("BV*_*"))
                valid_folders = [f for f in bv_folders if f.is_dir()]

                if valid_folders:
                    self.dir_status_var.set(
                        f"✅ 目录正常，包含 {len(valid_folders)} 个项目"
                    )
                    self.dir_status_label.config(foreground="#27ae60")
                else:
                    self.dir_status_var.set("📂 目录为空，尚无下载项目")
                    self.dir_status_label.config(foreground="#7f8c8d")

        except Exception as e:
            logger.error(f"更新目录显示时出错: {e}")
            self.current_dir_var.set("目录信息获取失败")
            self.dir_status_var.set(f"❌ 错误: {str(e)}")
            self.dir_status_label.config(foreground="#e74c3c")

    def open_current_directory(self):
        """打开当前目录"""
        try:
            current_dir = self.config.get("output", "")
            if not current_dir:
                messagebox.showwarning("提示", "未设置输出目录，请先在设置中配置")
                return

            output_path = Path(current_dir)
            if not output_path.exists():
                # 尝试创建目录
                try:
                    output_path.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    messagebox.showerror("错误", f"无法创建目录: {str(e)}")
                    return

            # 打开目录
            import subprocess
            import platform

            system = platform.system()
            if system == "Windows":
                subprocess.run(["explorer", str(output_path)])
            elif system == "Darwin":  # macOS
                subprocess.run(["open", str(output_path)])
            else:  # Linux and others
                subprocess.run(["xdg-open", str(output_path)])

        except Exception as e:
            logger.error(f"打开目录失败: {e}")
            messagebox.showerror("错误", f"打开目录失败: {str(e)}")

    def on_tab_selected(self):
        """当tab被选中时调用"""
        logger.info("浏览已下载tab被选中，更新目录信息")
        self.update_current_directory()
        # 稍微延迟一下再刷新列表，确保目录信息已更新
        self.after(100, self.refresh_items)

    def update_stop_all_button(self):
        """更新停止所有服务器按钮的状态"""
        if self.servers:
            self.stop_all_btn.config(state="normal")
        else:
            self.stop_all_btn.config(state="disabled")

    def check_ui_updates(self):
        """检查UI更新队列，处理来自线程的UI更新请求"""
        try:
            updated_servers = False
            while not ui_update_queue.empty():
                # 获取一个更新请求
                update_request = ui_update_queue.get_nowait()

                # 处理不同类型的更新请求
                if update_request["type"] == "server_status":
                    port = update_request["port"]
                    status = update_request["status"]
                    if port in self.servers:
                        self.servers[port]["status"] = status
                        updated_servers = True
                elif update_request["type"] == "status_message":
                    self.status_var.set(update_request["message"])
                elif update_request["type"] == "remove_server":
                    port = update_request["port"]
                    if port in self.servers:
                        del self.servers[port]
                        updated_servers = True

            # 如果服务器状态有变化，更新UI
            if updated_servers:
                self.update_server_list()
                self.update_stop_all_button()

        except Exception as e:
            logger.error(f"处理UI更新请求时出错: {e}")

        # 每500毫秒检查一次更新队列
        self.after(500, self.check_ui_updates)

    def refresh_items(self):
        """刷新项目列表"""
        self.update_current_directory()

        # 清除现有项目
        for widget in self.scrollable_frame.winfo_children():
            widget.destroy()

        # 获取输出目录
        output_dir = Path(self.config.get("output", ""))
        if not output_dir.exists():
            self.status_var.set(f"输出目录不存在: {output_dir}")
            return

        # 查找所有以BV或EP开头的文件夹
        content_folders = []

        # 查找BV开头的视频文件夹
        for item in output_dir.glob("BV*_*"):
            if item.is_dir():
                content_folders.append(item)

        # 查找EP开头的番剧文件夹
        for item in output_dir.glob("EP*_*"):
            if item.is_dir():
                content_folders.append(item)

        if not content_folders:
            ttk.Label(self.scrollable_frame, text="未找到已下载的项目").pack(
                padx=20, pady=20
            )
            self.status_var.set("未找到项目")
            return

        # 按修改时间排序（最新的在前面）
        content_folders.sort(key=lambda x: x.stat().st_mtime, reverse=True)

        # 为每个文件夹创建条目
        for folder in content_folders:
            # 提取标识符和标题
            folder_name = folder.name
            parts = folder_name.split("_", 1)

            if len(parts) != 2:
                continue

            identifier = parts[0]  # 可能是BV号或EP号
            title = parts[1]

            # 确定内容类型
            if identifier.startswith("BV"):
                content_type = "视频"
                content_type_icon = "🎬"
            elif identifier.startswith("EP"):
                content_type = "番剧"
                content_type_icon = "📺"
            else:
                continue  # 跳过不识别的格式

            # 检查是否有对应的geojson和html文件 - 修改文件名检查
            has_geojson = (folder / f"{identifier}.geojson").exists()
            has_html = (folder / f"{identifier}.html").exists()

            has_wordcloud_json = (folder / f"{identifier}_wordcloud_data.json").exists()
            has_wordcloud_html = (folder / f"{identifier}_wordcloud.html").exists()

            # 创建项目行
            item_frame = ttk.Frame(self.scrollable_frame)
            item_frame.pack(fill=tk.X, padx=5, pady=2)

            # 添加内容类型标识
            ttk.Label(
                item_frame,
                text=f"{content_type_icon} {content_type}",
                width=8,
                anchor=tk.W,
            ).pack(side=tk.LEFT, padx=5, pady=5)

            # 添加标题
            ttk.Label(item_frame, text=title, width=42, anchor=tk.W).pack(
                side=tk.LEFT, padx=5, pady=5
            )

            # 添加标识符
            ttk.Label(item_frame, text=identifier, width=15, anchor=tk.W).pack(
                side=tk.LEFT, padx=5, pady=5
            )

            # 地图按钮
            if has_geojson and has_html:
                browse_btn = ttk.Button(
                    item_frame,
                    text="✅ 浏览地图",
                    command=lambda f=folder, i=identifier, t=title: self.start_server(
                        f, i, t, f"{i}.html"
                    ),
                )
                browse_btn.pack(side=tk.LEFT, padx=5, pady=2)

            # 词云按钮
            if has_wordcloud_json and has_wordcloud_html:
                wordcloud_btn = ttk.Button(
                    item_frame,
                    text="✅ 浏览词云",
                    command=lambda f=folder, i=identifier, t=title: self.start_server(
                        f, i, t, f"{i}_wordcloud.html"
                    ),
                )
                wordcloud_btn.pack(side=tk.RIGHT, padx=5, pady=2)

            item_frame.configure(style="TFrame")

        self.status_var.set(f"找到 {len(content_folders)} 个项目")

        # 创建样式
        style = ttk.Style()
        style.configure("TFrame", background="#f0f0f0")

    def find_free_port(self) -> int:
        """获取可用端口"""
        max_attempts = 10
        for attempt in range(max_attempts):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
                    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                    sock.bind(("127.0.0.1", 0))
                    port = sock.getsockname()[1]
                    logger.info(f"找到可用端口: {port}")
                    return port
            except Exception as e:
                logger.warning(f"端口分配失败: {e}")
                if attempt == max_attempts - 1:
                    logger.error("无法找到可用端口")
                    raise Exception("无法找到可用端口")
                time.sleep(0.1)

        return 8000 + (os.getpid() % 1000)

    def copy_files_to_temp(self, source_folder: Path, target_filename: str = None) -> Optional[Path]:
        """将文件复制到临时目录，避免路径访问问题 - 增强版本"""
        try:
            # 创建临时目录
            temp_dir = Path(tempfile.mkdtemp(prefix="bilibili_server_"))
            logger.info(f"创建临时目录: {temp_dir}")

            # 确定需要复制的文件类型
            required_extensions = [".html", ".geojson", ".json"]
        
            # 如果指定了目标文件，确保相关文件都被复制
            if target_filename:
                if "wordcloud" in target_filename:
                    # 词云相关文件
                    identifier = target_filename.replace("_wordcloud.html", "")
                    required_files = [
                        f"{identifier}_wordcloud.html",
                        f"{identifier}_wordcloud_data.json"
                    ]
                else:
                    # 地图相关文件
                    identifier = target_filename.replace(".html", "")
                    required_files = [
                        f"{identifier}.html", 
                        f"{identifier}.geojson"
                    ]
            
                # 复制指定的必需文件
                for required_file in required_files:
                    source_file = source_folder / required_file
                    if source_file.exists():
                        dest_path = temp_dir / required_file
                        shutil.copy2(source_file, dest_path)
                        logger.debug(f"复制必需文件: {source_file} -> {dest_path}")
                    else:
                        logger.warning(f"必需文件不存在: {source_file}")

            # 复制所有相关文件到临时目录（作为备份）
            for file_path in source_folder.glob("*"):
                if file_path.is_file() and file_path.suffix in required_extensions:
                    dest_path = temp_dir / file_path.name
                    if not dest_path.exists():  # 避免重复复制
                        shutil.copy2(file_path, dest_path)
                        logger.debug(f"复制额外文件: {file_path} -> {dest_path}")

            logger.info(f"文件复制完成，临时目录: {temp_dir}")
        
            # 验证目标文件是否存在
            if target_filename:
                target_path = temp_dir / target_filename
                if not target_path.exists():
                    logger.error(f"目标文件未成功复制到临时目录: {target_path}")
                    return None
                
            return temp_dir

        except Exception as e:
            logger.error(f"复制文件到临时目录失败: {e}")
            return None

    def start_server(self, folder_path: Path, identifier: str, title: str, filename: str):
        """启动本地HTTP服务器 - 修复文件复用问题"""
        try:
            # 检查是否已经有服务器为该目录提供服务
            for port, info in self.servers.items():
                if info["folder"] == folder_path:
                    # 检查目标文件是否存在于现有服务器的临时目录中
                    temp_dir = info.get("temp_dir")
                    if temp_dir and (temp_dir / filename).exists():
                        # 文件存在，可以复用服务器
                        url = f"http://127.0.0.1:{port}/{filename}"
                        try:
                            webbrowser.open(url)
                            self.status_var.set(f"已打开页面: {url}")
                            logger.info(f"复用现有服务器: {url}")
                            return
                        except Exception as e:
                            logger.error(f"打开浏览器失败: {e}")
                            self.status_var.set(f"服务器运行中，但无法打开浏览器: {url}")
                            return
                    else:
                        # 目标文件不存在于临时目录中，需要重新创建临时目录
                        logger.info(f"目标文件{filename}不存在于现有服务器临时目录中，重新创建")
                        # 停止现有服务器
                        self.stop_server(port)
                        break

            # 检查目标文件是否存在
            target_file = folder_path / filename
            if not target_file.exists():
                logger.error(f"目标文件不存在: {target_file}")
                messagebox.showerror("错误", f"文件不存在: {filename}")
                return

            logger.info(f"准备启动服务器，文件夹: {folder_path}, 目标文件: {filename}")

            # 获取一个可用端口
            try:
                port = self.find_free_port()
            except Exception as e:
                logger.error(f"无法获取可用端口: {e}")
                messagebox.showerror("错误", "无法找到可用端口，请检查系统权限")
                return

            # 复制文件到临时目录 - 传递目标文件名以确保包含所需文件
            temp_dir = self.copy_files_to_temp(folder_path, filename)
            if not temp_dir:
                logger.error("复制文件到临时目录失败")
                messagebox.showerror("错误", "无法准备服务器文件")
                return

            # 保存服务器信息
            self.servers[port] = {
                "folder": folder_path,
                "temp_dir": temp_dir,
                "identifier": identifier,
                "title": title,
                "status": "启动中",
                "server": None,
                "thread": None,
            }

            # 记录临时目录用于清理
            self.temp_dirs[port] = temp_dir

            # 更新服务器列表
            self.update_server_list()
            self.update_stop_all_button()

            # 创建并启动服务器线程
            server_thread = threading.Thread(
                target=self.run_server, args=(temp_dir, port, identifier, title), daemon=True
            )
            self.servers[port]["thread"] = server_thread
            server_thread.start()

            # 给服务器一点时间启动
            time.sleep(1.0)

            # 打开浏览器
            url = f"http://127.0.0.1:{port}/{filename}"
            try:
                webbrowser.open(url)
                self.status_var.set(f"服务器已启动: {url}")
                logger.info(f"服务器启动成功，URL: {url}")
            except Exception as e:
                logger.error(f"打开浏览器出错: {e}")
                self.status_var.set(f"服务器已启动在端口 {port}，但打开浏览器失败")
                messagebox.showinfo(
                    "提示", f"服务器已启动，请手动打开浏览器访问：\n{url}"
                )

        except Exception as e:
            logger.error(f"启动服务器失败: {e}")
            import traceback

            logger.error(f"详细错误: {traceback.format_exc()}")
            messagebox.showerror("错误", f"启动服务器失败: {str(e)}")

    def run_server(self, serve_dir: Path, port: int, identifier: str, title: str):
        """运行HTTP服务器的线程函数 - 更新参数名"""
        # 保存当前目录
        original_dir = os.getcwd()
        server = None

        try:
            # 切换到服务目录
            logger.info(f"切换到服务目录: {serve_dir}")
            os.chdir(str(serve_dir))

            # 更新状态
            ui_update_queue.put(
                {"type": "server_status", "port": port, "status": "运行中"}
            )

            # 创建自定义HTTP处理器，增强错误处理
            class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
                def end_headers(self):
                    self.send_header("Content-Type", "text/html; charset=utf-8")
                    self.send_header("Cache-Control", "no-cache")
                    super().end_headers()

                def do_GET(self):
                    if self.path == "/favicon.ico":
                        self.send_response(204)
                        self.end_headers()
                        return

                    try:
                        super().do_GET()
                    except Exception as e:
                        logger.error(f"HTTP请求处理错误: {e}")
                        self.send_error(500, f"Internal Server Error: {e}")

                def log_message(self, format, *args):
                    if "favicon.ico" not in (args[0] if args else ""):
                        logger.info(f"HTTP请求: {format % args}")

                def log_error(self, format, *args):
                    logger.error(f"HTTP错误: {format % args}")

            # 尝试创建HTTP服务器，增加重试机制
            max_server_attempts = 3
            for attempt in range(max_server_attempts):
                try:
                    server = http.server.HTTPServer(
                        ("127.0.0.1", port), CustomHTTPRequestHandler
                    )
                    server.timeout = None  # 禁用超时
                    break
                except OSError as e:
                    if (
                        "Address already in use" in str(e)
                        and attempt < max_server_attempts - 1
                    ):
                        logger.warning(f"端口 {port} 被占用，等待后重试...")
                        time.sleep(1)
                        continue
                    else:
                        raise

            if server is None:
                raise Exception(f"无法在端口 {port} 创建HTTP服务器")

            # 保存服务器引用
            if port in self.servers:
                self.servers[port]["server"] = server

            # 运行服务器
            logger.info(f"HTTP服务器已启动在端口 {port}, 服务目录: {serve_dir}")
            server.serve_forever()

        except Exception as e:
            logger.error(f"服务器运行出错: {e}")
            import traceback

            logger.error(f"详细错误: {traceback.format_exc()}")

            # 通过队列安全地更新UI
            ui_update_queue.put(
                {
                    "type": "server_status",
                    "port": port,
                    "status": f"错误: {str(e)[:20]}",
                }
            )
        finally:
            # 清理服务器
            if server:
                try:
                    server.server_close()
                except Exception as e:
                    logger.error(f"关闭服务器时出错: {e}")

            # 恢复原始目录
            try:
                os.chdir(original_dir)
            except Exception as e:
                logger.error(f"恢复工作目录失败: {e}")

            # 通过队列安全地更新UI
            ui_update_queue.put(
                {"type": "server_status", "port": port, "status": "已停止"}
            )

    def update_server_list(self):
        """更新服务器列表视图 - 只能在主线程中调用"""
        # 清除现有项
        for item in self.server_tree.get_children():
            self.server_tree.delete(item)

        # 添加服务器信息
        for port, info in self.servers.items():
            self.server_tree.insert(
                "", "end", values=(info["title"], port, info["status"])
            )

    def cleanup_temp_dir(self, port: int):
        """清理临时目录"""
        if port in self.temp_dirs:
            temp_dir = self.temp_dirs[port]
            try:
                if temp_dir.exists():
                    shutil.rmtree(temp_dir)
                    logger.info(f"已清理临时目录: {temp_dir}")
                del self.temp_dirs[port]
            except Exception as e:
                logger.error(f"清理临时目录失败: {e}")

    def stop_server(self, port: int):
        """停止指定端口的服务器"""
        if port in self.servers:
            server_info = self.servers[port]

            # 停止服务器
            if server_info["server"]:
                try:
                    # 创建一个线程安全地关闭服务器
                    def shutdown_server():
                        try:
                            server_info["server"].shutdown()
                        except Exception as e:
                            logger.error(f"关闭服务器出错: {e}")

                    shutdown_thread = threading.Thread(target=shutdown_server)
                    shutdown_thread.daemon = True
                    shutdown_thread.start()
                    shutdown_thread.join(2.0)  # 最多等待2秒
                except Exception as e:
                    logger.error(f"停止服务器出错: {e}")

            # 清理临时目录
            self.cleanup_temp_dir(port)

            # 从列表中移除
            del self.servers[port]

            # 更新服务器列表
            self.update_server_list()
            self.update_stop_all_button()

            self.status_var.set(f"已停止端口 {port} 的服务器")

    def stop_all_servers(self):
        """停止所有运行的服务器"""
        if not self.servers:
            self.status_var.set("没有运行中的服务器")
            return

        if not messagebox.askokcancel("确认", "确定要停止所有运行中的服务器吗？"):
            return

        ports = list(self.servers.keys())
        for port in ports:
            self.stop_server(port)

        # 清理所有临时目录
        for port in list(self.temp_dirs.keys()):
            self.cleanup_temp_dir(port)

        self.status_var.set("已停止所有服务器")
        self.update_stop_all_button()

    def show_context_menu(self, event):
        """显示右键菜单"""
        selected_item = self.server_tree.identify_row(event.y)
        if selected_item:
            self.server_tree.selection_set(selected_item)
            self.context_menu.post(event.x_root, event.y_root)

    def get_selected_server_port(self) -> Optional[int]:
        """获取选中的服务器端口"""
        selected_items = self.server_tree.selection()
        if not selected_items:
            return None

        selected_item = selected_items[0]
        values = self.server_tree.item(selected_item, "values")

        try:
            return int(values[1])  # 端口在第二列
        except (IndexError, ValueError):
            return None

    def stop_selected_server(self):
        """停止选中的服务器"""
        port = self.get_selected_server_port()
        if not port:
            return

        self.stop_server(port)

    def __del__(self):
        """析构函数，清理资源"""
        try:
            # 清理所有临时目录
            for port in list(self.temp_dirs.keys()):
                self.cleanup_temp_dir(port)
        except Exception as e:
            logger.error(f"析构时清理资源失败: {e}")
