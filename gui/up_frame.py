import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import logging
import time
from pathlib import Path
import json

from config import Config
from api.bilibili_api import BilibiliAPI, extract_title_from_dirname, get_dir_name
from models.comment import Comment, Stat
from store.csv_analyzer import normalize_location
from models.video import Video
from store.csv_exporter import save_to_csv
from store.geo_exporter import write_geojson
from gui.tooltip import create_tooltip

logger = logging.getLogger(__name__)


class UpFrame(ttk.Frame):
    """UP主视频批量下载界面"""

    def __init__(self, parent):
        """初始化界面"""
        super().__init__(parent)
        self.config = Config()
        self.api = BilibiliAPI(self.config.get("cookie", ""))
        self.init_ui()

    def init_ui(self):
        """初始化UI"""
        # 输入区域
        input_frame = ttk.LabelFrame(self, text="输入")
        input_frame.pack(fill=tk.X, padx=10, pady=5)

        # UP主ID输入
        ttk.Label(input_frame, text="UP主ID:").grid(
            row=0, column=0, padx=5, pady=5, sticky=tk.W
        )
        self.mid_var = tk.StringVar()
        ttk.Entry(input_frame, textvariable=self.mid_var, width=30).grid(
            row=0, column=1, padx=5, pady=5, sticky=tk.W
        )

        mid_hint_frame = ttk.Frame(input_frame)
        mid_hint_frame.grid(row=0, column=2, padx=5, pady=5, sticky=tk.W)
        # 创建标签指示如何找到UP主ID
        ttk.Label(
            mid_hint_frame, text="例如(只需要加粗部分)：https://space.bilibili.com/"
        ).pack(side=tk.LEFT)
        # 添加加粗的UP主ID部分
        bold_font = ("Microsoft YaHei", 9, "bold")
        ttk.Label(mid_hint_frame, text="123456", font=bold_font).pack(side=tk.LEFT)

        # 页数设置
        ttk.Label(input_frame, text="视频页面范围:").grid(
            row=1, column=0, padx=5, pady=5, sticky=tk.W
        )
        pages_frame = ttk.Frame(input_frame)
        pages_frame.grid(row=1, column=1, padx=5, pady=5, sticky=tk.W)

        ttk.Label(pages_frame, text="从第").pack(side=tk.LEFT)
        self.start_page_var = tk.IntVar(value=1)
        ttk.Spinbox(
            pages_frame, from_=1, to=50, textvariable=self.start_page_var, width=3
        ).pack(side=tk.LEFT, padx=2)

        ttk.Label(pages_frame, text="页到第").pack(side=tk.LEFT)
        self.end_page_var = tk.IntVar(value=3)
        ttk.Spinbox(
            pages_frame, from_=1, to=50, textvariable=self.end_page_var, width=3
        ).pack(side=tk.LEFT, padx=2)

        ttk.Label(pages_frame, text="页").pack(side=tk.LEFT, padx=2)

        # 添加验证按钮和说明
        help_frame = ttk.Frame(input_frame)
        help_frame.grid(row=2, column=1, padx=5, pady=0, sticky=tk.W)

        ttk.Label(
            help_frame,
            text="(注: B站视频列表通常每页30个视频)",
            font=("Microsoft YaHei", 8),
        ).pack(side=tk.LEFT)

        # 视频排序方式
        ttk.Label(input_frame, text="视频排序:").grid(
            row=3, column=0, padx=5, pady=5, sticky=tk.W
        )
        vorder_frame = ttk.Frame(input_frame)
        vorder_frame.grid(row=3, column=1, padx=5, pady=5, sticky=tk.W)

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

        # 评论排序方式
        ttk.Label(input_frame, text="评论排序:").grid(
            row=4, column=0, padx=5, pady=5, sticky=tk.W
        )
        corder_frame = ttk.Frame(input_frame)
        corder_frame.grid(row=4, column=1, padx=5, pady=5, sticky=tk.W)

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

        # 是否生成地图
        self.mapping_var = tk.BooleanVar(value=self.config.get("mapping", True))
        ttk.Checkbutton(
            input_frame, text="生成评论地区分布地图", variable=self.mapping_var
        ).grid(row=5, column=0, columnspan=2, padx=5, pady=5, sticky=tk.W)

        # 操作按钮
        button_frame = ttk.Frame(self)
        button_frame.pack(fill=tk.X, padx=10, pady=5)

        download_btn = ttk.Button(
            button_frame, text="📥 获取评论", command=self.start_download
        )
        download_btn.pack(side=tk.LEFT, padx=5, pady=5)

        create_tooltip(
            download_btn,
            "下载好评论后\n" "可在【浏览已下载】中点击【浏览地图】",
        )

        ttk.Button(button_frame, text="⏹️ 停止", command=self.stop_download).pack(
            side=tk.LEFT, padx=5, pady=5
        )
        ttk.Button(button_frame, text="🧹 清空日志", command=self.clear_log).pack(
            side=tk.LEFT, padx=5, pady=5
        )

        # 进度条
        self.progress_var = tk.DoubleVar()
        ttk.Label(button_frame, text="进度:").pack(side=tk.LEFT, padx=5, pady=5)
        ttk.Progressbar(
            button_frame, variable=self.progress_var, length=300, mode="determinate"
        ).pack(side=tk.LEFT, padx=5, pady=5, fill=tk.X, expand=True)

        # 日志区域
        log_frame = ttk.LabelFrame(self, text="日志")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # 修改日志文本框样式
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            font=("Microsoft YaHei", 9),
            padx=5,
            pady=5,
            background="#fafafa",
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

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

    def validate_input(self):
        """验证输入"""
        mid = self.mid_var.get().strip()
        if not mid:
            messagebox.showerror("错误", "请输入UP主ID")
            return False

        # 验证UP主ID格式
        if not mid.isdigit():
            messagebox.showerror("错误", "UP主ID必须是数字")
            return False

        # 验证页数范围
        start_page = self.start_page_var.get()
        end_page = self.end_page_var.get()

        if start_page > end_page:
            messagebox.showerror("错误", "起始页不能大于结束页")
            return False

        if end_page - start_page > 20:
            if not messagebox.askyesno(
                "警告",
                f"您设置了下载{end_page - start_page + 1}页视频，可能需要较长时间，确定继续吗？",
            ):
                return False

        # 检查输出目录是否设置
        output_dir = self.config.get("output", "")
        if not output_dir:
            messagebox.showerror("错误", "请先在设置中配置输出目录")
            return False

        return True

    def start_download(self):
        """开始下载"""
        if not self.validate_input():
            return

        if self.download_thread and self.download_thread.is_alive():
            messagebox.showinfo("提示", "已有下载任务正在进行中")
            return

        self.stop_flag = False
        self.progress_var.set(0)

        # 保存配置
        self.config.set("corder", self.corder_var.get())
        self.config.set("vorder", self.vorder_var.get())
        self.config.set("mapping", self.mapping_var.get())

        # 更新API的cookie
        self.api = BilibiliAPI(self.config.get("cookie", ""))

        # 创建并启动下载线程
        self.download_thread = threading.Thread(target=self.download_up_videos)
        self.download_thread.daemon = True
        self.download_thread.start()

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
            or message.startswith("共找到")
            or message.endswith("视频评论获取完成")
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

    def download_up_videos(self):
        """下载UP主视频评论的线程函数"""
        try:
            mid = int(self.mid_var.get().strip())
            start_page = self.start_page_var.get()
            end_page = self.end_page_var.get()
            vorder = self.vorder_var.get()

            self.log(f"开始获取UP主 {mid} 的视频列表")
            self.log(f"将下载第 {start_page} 页到第 {end_page} 页的视频")

            video_collection = []
            current_page = start_page - 1  # 调整起始值以匹配原来的逻辑
            retry_count = 0
            max_retries = 3

            # 获取视频列表
            while current_page < end_page and not self.stop_flag:
                current_page += 1
                self.log(f"正在获取第 {current_page} 页视频列表")

                # 添加重试逻辑
                retry_current = 0
                success = False

                while retry_current < max_retries and not success:
                    try:
                        # 获取视频列表
                        video_info = self.api.fetch_video_list(
                            mid, current_page, vorder
                        )

                        if video_info.get("code") != 0:
                            error_msg = video_info.get("message", "未知错误")
                            self.log(f"获取视频列表失败: {error_msg}", "error")

                            # 如果接口提示稍后重试，则等待并重试
                            if "请稍后再试" in error_msg:
                                retry_current += 1
                                if retry_current < max_retries:
                                    retry_wait = 5 * retry_current
                                    self.log(
                                        f"将在 {retry_wait} 秒后重试 ({retry_current}/{max_retries})...",
                                        "warning",
                                    )
                                    time.sleep(retry_wait)
                                    continue
                            break

                        vlist = (
                            video_info.get("data", {}).get("list", {}).get("vlist", [])
                        )

                        if not vlist:
                            self.log(
                                f"第 {current_page} 页未获取到视频，可能已到达最后一页",
                                "warning",
                            )
                            break

                        # 添加到视频集合
                        for video_item in vlist:
                            video = Video.from_api_response(video_item)
                            video_collection.append(video)

                        self.log(
                            f"第 {current_page} 页获取到 {len(vlist)} 个视频", "success"
                        )
                        success = True

                    except Exception as e:
                        retry_current += 1
                        if retry_current < max_retries:
                            retry_wait = 5 * retry_current
                            self.log(f"获取视频列表出错: {e}", "error")
                            self.log(
                                f"将在 {retry_wait} 秒后重试 ({retry_current}/{max_retries})...",
                                "warning",
                            )
                            time.sleep(retry_wait)
                        else:
                            self.log(
                                f"获取视频列表失败，已达最大重试次数: {e}", "error"
                            )
                            break

                if self.stop_flag:
                    self.log("用户停止了下载")
                    break

                # 如果该页获取失败且不是最后一页，询问是否继续
                if not success and current_page < end_page:
                    # 由于在线程中，不能直接使用messagebox，使用自定义状态标记
                    self.log(
                        f"第 {current_page} 页获取失败，跳过此页继续后续页面", "warning"
                    )
                    continue

            if not video_collection:
                self.log(f"未找到UP主 {mid} 的视频", "warning")
                return

            total_videos = len(video_collection)
            self.log(f"共找到 {total_videos} 个视频", "header")

            # 下载每个视频的评论
            for i, video in enumerate(video_collection):
                if self.stop_flag:
                    break

                self.log(
                    f"开始获取视频 [{i+1}/{total_videos}] {video.bvid}: {video.title}",
                    "header",
                )
                self.download_video_comments(video)

                # 更新总进度
                self.progress_var.set(min(100, (i + 1) / total_videos * 100))

            self.log("所有视频评论获取完成", "success")

        except Exception as e:
            self.log(f"下载过程中出错: {e}", "error")
            logger.exception("下载UP主视频评论出错")

    def download_video_comments(self, video):
        """下载单个视频的评论"""
        try:
            bvid = video.bvid
            avid = video.aid
            oid = str(avid)

            # 首先尝试使用video对象中的标题
            video_title = (
                video.title if hasattr(video, "title") and video.title else "未知视频"
            )

            # 检查是否已经存在包含标题的目录
            base_output_dir = Path(self.config.get("output", ""))
            existing_dir = None

            # 查找以BV号开头的目录
            for item in base_output_dir.glob(f"{bvid}_*"):
                if item.is_dir():
                    existing_dir = item
                    extracted_title = extract_title_from_dirname(item.name)
                    if extracted_title:
                        video_title = extracted_title
                        self.log(f"找到已有目录，使用现有标题: {video_title}")
                        break

            # 如果没有找到目录或无法提取标题，且video对象的标题不可用，则请求API
            if (
                not existing_dir or video_title == "未知视频"
            ) and video_title == "未知视频":
                self.log(f"正在获取视频 {bvid} 的信息...")
                video_info = self.api.fetch_video_info(bvid)

                if video_info.get("code") == 0:
                    video_title = video_info.get("data", {}).get("title", "未知视频")
                    self.log(f"从API获取到视频标题: {video_title}")
                else:
                    self.log(f"获取视频标题失败，使用默认标题")

            # 创建输出目录 - 使用BV号+标题的格式
            dir_name = get_dir_name(bvid, video_title)
            output_dir = base_output_dir / dir_name
            output_dir.mkdir(parents=True, exist_ok=True)

            # 保存视频信息到JSON文件（如果是新获取的）
            video_info_path = output_dir / "video_info.json"
            if not video_info_path.exists():
                try:
                    # 如果是通过API获取的，使用完整信息
                    if "video_info" in locals() and video_info.get("code") == 0:
                        with open(video_info_path, "w", encoding="utf-8") as f:
                            json.dump(video_info, f, ensure_ascii=False, indent=2)
                    # 否则使用video对象的信息
                    else:
                        video_info_dict = {
                            "bvid": bvid,
                            "aid": avid,
                            "title": video_title,
                            "author": video.author if hasattr(video, "author") else "",
                            "comment_count": (
                                video.comment if hasattr(video, "comment") else 0
                            ),
                        }
                        with open(video_info_path, "w", encoding="utf-8") as f:
                            json.dump(video_info_dict, f, ensure_ascii=False, indent=2)
                    self.log(f"已保存视频信息到: {video_info_path}")
                except Exception as e:
                    self.log(f"保存视频信息失败: {e}")

            # 获取评论总数
            total = self.api.fetch_comment_count(oid)
            if total == 0:
                self.log(f"视频 {bvid} ({video_title}) 未找到评论或获取评论数失败")
                return

            self.log(f"视频 {bvid} ({video_title}) 共有 {total} 条评论")

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

                self.log(f"正在获取视频 {bvid} 第 {round_num + 1} 页评论")

                # 如果已下载的评论数大于等于总评论数，且连续空页面数达到限制，则停止获取
                if (
                    downloaded_count >= total
                    and consecutive_empty_pages >= consecutive_empty_limit
                ):
                    self.log(f"视频 {bvid} 评论获取完成")
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
                        self.log(f"用户停止了视频 {bvid} 的下载")
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
                            oid, reply.get("rpid"), bvid
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
                        comment.bvid = bvid

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
                    save_to_csv(bvid, comments, str(output_dir), video_title)

                downloaded_count += len(comments)
                self.log(f"视频 {bvid} 已获取 {downloaded_count}/{total} 条评论")

                if self.stop_flag:
                    self.log(f"用户停止了视频 {bvid} 的下载")
                    break

            # 生成地图
            if self.mapping_var.get() and stat_map:
                self.log(f"正在生成视频 {bvid} 的评论地区分布地图...")
                unmatched_regions = write_geojson(
                    stat_map, bvid, str(output_dir), video_title
                )
                self.log(f"视频 {bvid} 地图生成完成")

                # 显示未匹配地区
                if unmatched_regions:
                    unmatched_names = ", ".join(unmatched_regions.keys())
                    self.log(
                        f"视频 {bvid} 有 {len(unmatched_regions)} 个地区未能匹配到地图: {unmatched_names}"
                    )

                    # 单独打印每个未匹配地区的信息
                    for region, info in unmatched_regions.items():
                        self.log(
                            f"  未匹配地区: {region} - {info['comments']}条评论, {info['users']}位用户"
                        )

        except Exception as e:
            self.log(f"下载视频 {video.bvid} 评论过程中出错: {e}", "error")
            logger.exception(f"下载视频 {video.bvid} 评论出错")

    def fetch_sub_comments(self, oid, rpid, bvid):
        """获取子评论"""
        page = 1
        all_replies = []

        while not self.stop_flag:
            self.log(f"获取视频 {bvid} 评论 {rpid} 的子评论，第 {page} 页")

            sub_cmt_info = self.api.fetch_sub_comments(oid, rpid, page)

            if sub_cmt_info.get("code") != 0:
                self.log(f"获取子评论失败: {sub_cmt_info.get('message', '未知错误')}")
                break

            replies = sub_cmt_info.get("data", {}).get("replies", [])

            if not replies:
                break

            all_replies.extend(replies)

            # 获取子评论的回复
            for reply in replies:
                reply_replies = reply.get("replies", [])
                if reply_replies:
                    all_replies.extend(reply_replies)

            # 获取置顶评论
            top_replies = sub_cmt_info.get("data", {}).get("top_replies", [])
            if top_replies:
                all_replies.extend(top_replies)
                for reply in top_replies:
                    reply_replies = reply.get("replies", [])
                    if reply_replies:
                        all_replies.extend(reply_replies)

            page += 1

        return all_replies
