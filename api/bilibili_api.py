import json
import time
import logging
import random
import re
from typing import Dict, Any, Tuple, Optional
import requests

from .crypto import sign_and_generate_url, bvid_to_avid, avid_to_bvid

# 基础请求头
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36 Edg/125.0.0.0"
ORIGIN = "https://www.bilibili.com"
HOST = "https://www.bilibili.com"

logger = logging.getLogger(__name__)


def sanitize_filename(filename: str) -> str:
    """清理文件名"""
    # 替换文件名中不允许的字符
    invalid_chars = r'<>:"/\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, "_")

    # 截断文件名长度，防止过长
    if len(filename) > 100:
        filename = filename[:97] + "..."

    return filename


def extract_title_from_dirname(dirname: str) -> str:
    """从目录名称中提取视频标题

    格式: BV号_标题 或 EP号_标题

    Args:
        dirname: 目录名称

    Returns:
        提取出的标题，如果无法提取则返回空字符串
    """
    parts = dirname.split("_", 1)
    if len(parts) > 1 and (parts[0].startswith("BV") or parts[0].startswith("EP")):
        return parts[1]
    return ""


def get_dir_name(identifier: str, title: str) -> str:
    """根据标识符和标题生成目录名

    Args:
        identifier: 视频标识符（BV号或EP号）
        title: 视频标题

    Returns:
        格式化后的目录名
    """
    safe_title = sanitize_filename(title)
    return f"{identifier}_{safe_title}"


def parse_bilibili_url(url: str) -> Tuple[str, str]:
    """解析B站URL，返回类型和标识符

    Args:
        url: B站URL

    Returns:
        tuple: (content_type, identifier)
            content_type: 'video', 'bangumi', 或 'season'
            identifier: BV号、EP号或SS号
    """
    # 视频链接模式
    video_patterns = [
        r"bilibili\.com/video/([A-Za-z0-9]+)",
        r"b23\.tv/([A-Za-z0-9]+)",
    ]

    # 番剧剧集链接模式
    bangumi_patterns = [
        r"bilibili\.com/bangumi/play/ep(\d+)",
        r"bilibili\.com/bangumi/play/ss\d+.*ep(\d+)",
    ]

    # 番剧季度链接模式
    season_patterns = [
        r"bilibili\.com/bangumi/play/ss(\d+)",
    ]

    # 检查视频链接
    for pattern in video_patterns:
        match = re.search(pattern, url)
        if match:
            identifier = match.group(1)
            if identifier.startswith("BV"):
                return "video", identifier

    # 检查番剧剧集链接
    for pattern in bangumi_patterns:
        match = re.search(pattern, url)
        if match:
            ep_id = match.group(1)
            return "bangumi", f"EP{ep_id}"

    # 检查番剧季度链接
    for pattern in season_patterns:
        match = re.search(pattern, url)
        if match:
            season_id = match.group(1)
            return "season", f"SS{season_id}"

    # 如果都不匹配，尝试直接判断输入格式
    if url.startswith("BV"):
        return "video", url
    elif url.startswith("EP") or url.startswith("ep"):
        ep_id = url.replace("EP", "").replace("ep", "")
        return "bangumi", f"EP{ep_id}"
    elif url.startswith("SS") or url.startswith("ss"):
        season_id = url.replace("SS", "").replace("ss", "")
        return "season", f"SS{season_id}"

    raise ValueError(
        f"无法识别的B站链接格式: {url}\n支持格式：\n• BV号\n• EP号（如：EP123456）\n• SS号（如：SS12345）\n• 完整链接"
    )


def extract_season_id(identifier: str) -> str:
    """从SS标识符中提取数字ID"""
    if identifier.startswith("SS"):
        return identifier[2:]
    return identifier


def extract_ep_id(identifier: str) -> str:
    """从EP标识符中提取数字ID"""
    if identifier.startswith("EP"):
        return identifier[2:]
    return identifier


class BilibiliAPI:
    """B站API接口封装"""

    def __init__(self, cookie: str = ""):
        """初始化B站API"""
        self.cookie = cookie
        # 统一的请求会话
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Origin": ORIGIN,
                "Referer": ORIGIN,
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
                "Sec-Fetch-Site": "same-site",
                "Sec-Fetch-Mode": "cors",
                "Sec-Fetch-Dest": "empty",
            }
        )
        if cookie:
            self.session.headers["Cookie"] = cookie

    def sleep_between_requests(self, request_type="normal"):
        """
        在请求之间添加延迟，减轻API负担，避免频繁请求导致的封禁

        Args:
            request_type: 请求类型：
                - "normal": 普通请求
                - "retry": 重试请求

        Returns:
            实际延迟的时间（秒）
        """
        from config import Config

        config = Config()

        if request_type == "normal":
            min_delay = config.get("request_delay_min", 1.0)
            max_delay = config.get("request_delay_max", 2.0)
            delay = min_delay + random.random() * (max_delay - min_delay)
        else:  # retry
            delay = config.get("request_retry_delay", 5.0)

        logger.debug(f"请求延迟: {delay:.2f}秒 ({request_type})")
        time.sleep(delay)
        return delay

    def fetch_bangumi_episode_info(self, ep_id: str) -> Dict[str, Any]:
        """获取番剧剧集信息

        Args:
            ep_id: 剧集ID（数字）

        Returns:
            包含剧集信息的字典，包括aid等
        """
        self.sleep_between_requests()

        url = f"https://api.bilibili.com/pgc/view/web/season"
        params = {"ep_id": ep_id}

        try:
            headers = {
                "Referer": f"https://www.bilibili.com/bangumi/play/ep{ep_id}",
            }

            response = self.session.get(url, params=params, headers=headers, timeout=10)
            logger.info(f"获取番剧剧集信息的状态码: {response.status_code}")

            response.raise_for_status()
            data = response.json()

            if data.get("code") != 0:
                logger.error(f"获取番剧剧集信息失败: {data}")
                return {
                    "code": -1,
                    "message": data.get("message", "未知错误"),
                    "data": {},
                }

            # 从返回的episodes中找到对应的episode
            episodes = data.get("result", {}).get("episodes", [])
            current_episode = None

            for ep in episodes:
                if str(ep.get("id")) == str(ep_id):
                    current_episode = ep
                    break

            if not current_episode:
                logger.error(f"未找到EP{ep_id}的信息")
                return {"code": -1, "message": "未找到对应剧集", "data": {}}

            # 构造类似视频信息的返回格式
            result = {
                "code": 0,
                "data": {
                    "aid": current_episode.get("aid"),
                    "bvid": current_episode.get("bvid", ""),
                    "title": current_episode.get("long_title")
                    or current_episode.get("share_copy", ""),
                    "desc": current_episode.get("desc", ""),
                    "owner": {
                        "mid": data.get("result", {}).get("up_info", {}).get("mid", 0),
                        "name": data.get("result", {})
                        .get("up_info", {})
                        .get("uname", ""),
                    },
                    "stat": current_episode.get("stat", {}),
                    "ep_id": ep_id,
                    "season_id": data.get("result", {}).get("season_id"),
                    "series_title": data.get("result", {}).get("title", ""),
                },
            }

            logger.info(f"成功获取番剧EP{ep_id}信息: {result['data']['title']}")
            return result

        except Exception as e:
            logger.error(f"获取番剧剧集信息出错: {e}")
            return {"code": -1, "message": str(e), "data": {}}

    def fetch_bangumi_season_info(self, season_id: str) -> Dict[str, Any]:
        """获取番剧季度信息

        Args:
            season_id: 季度ID（数字）

        Returns:
            包含季度信息的字典，包括第一集的aid等
        """
        self.sleep_between_requests()

        url = f"https://api.bilibili.com/pgc/view/web/season"
        params = {"season_id": season_id}

        try:
            headers = {
                "Referer": f"https://www.bilibili.com/bangumi/play/ss{season_id}",
            }

            response = self.session.get(url, params=params, headers=headers, timeout=10)
            logger.info(f"获取番剧季度信息的状态码: {response.status_code}")

            response.raise_for_status()
            data = response.json()

            if data.get("code") != 0:
                logger.error(f"获取番剧季度信息失败: {data}")
                return {
                    "code": -1,
                    "message": data.get("message", "未知错误"),
                    "data": {},
                }

            # 从返回的episodes中获取第一集作为代表
            episodes = data.get("result", {}).get("episodes", [])
            if not episodes:
                logger.error(f"SS{season_id}没有找到剧集信息")
                return {"code": -1, "message": "未找到剧集", "data": {}}

            # 使用第一集的信息
            first_episode = episodes[0]

            # 构造类似视频信息的返回格式
            result = {
                "code": 0,
                "data": {
                    "aid": first_episode.get("aid"),
                    "bvid": first_episode.get("bvid", ""),
                    "title": data.get("result", {}).get("title", ""),  # 使用季度标题
                    "desc": data.get("result", {}).get("evaluate", ""),
                    "owner": {
                        "mid": data.get("result", {}).get("up_info", {}).get("mid", 0),
                        "name": data.get("result", {})
                        .get("up_info", {})
                        .get("uname", ""),
                    },
                    "stat": first_episode.get("stat", {}),
                    "season_id": season_id,
                    "ep_id": first_episode.get("id"),
                    "series_title": data.get("result", {}).get("title", ""),
                    "total_episodes": len(episodes),
                },
            }

            logger.info(
                f"成功获取番剧SS{season_id}信息: {result['data']['title']} (共{len(episodes)}集)"
            )
            return result

        except Exception as e:
            logger.error(f"获取番剧季度信息出错: {e}")
            return {"code": -1, "message": str(e), "data": {}}

    def fetch_content_info(self, identifier: str, content_type: str = None) -> Dict[str, Any]:
        """统一的内容信息获取接口
    
        Args:
            identifier: 内容标识符（BV号、EP号或SS号）
            content_type: 内容类型（'video'、'bangumi'或'season'），如果不提供会自动判断
        
        Returns:
            内容信息字典
        """
        if content_type is None:
            if identifier.startswith('BV'):
                content_type = 'video'
            elif identifier.startswith('EP'):
                content_type = 'bangumi'
            elif identifier.startswith('SS'):
                content_type = 'season'
            else:
                return {"code": -1, "message": "无法识别的标识符格式", "data": {}}
            
        if content_type == 'video':
            return self.fetch_video_info(identifier)
        elif content_type == 'bangumi':
            ep_id = extract_ep_id(identifier)
            return self.fetch_bangumi_episode_info(ep_id)
        elif content_type == 'season':
            season_id = extract_season_id(identifier)
            return self.fetch_bangumi_season_info(season_id)
        else:
            return {"code": -1, "message": "不支持的内容类型", "data": {}}

    def fetch_comment_count(self, oid: str) -> int:
        """获取评论总数"""
        url = f"https://api.bilibili.com/x/v2/reply/count?type=1&oid={oid}"

        try:
            # 请求前添加延迟
            self.sleep_between_requests()

            logger.info(f"请求评论总数 URL: {url}")
            logger.info(f"当前Cookie长度: {len(self.cookie) if self.cookie else 0}")

            # 检查内容是否已经被自动解压缩
            response = self.session.get(url, timeout=10)

            logger.info(f"API请求响应状态码: {response.status_code}")
            content_encoding = response.headers.get("Content-Encoding", "none").lower()
            logger.info(f"响应头Content-Encoding: {content_encoding}")

            response.raise_for_status()

            # 检查内容是否已经是有效JSON
            raw_content = response.content
            try:
                # 先尝试直接解析，可能requests已经自动解压缩了
                text_content = raw_content.decode("utf-8")
                if text_content.strip().startswith(
                    "{"
                ) or text_content.strip().startswith("["):
                    logger.info("内容已经是有效的JSON格式，无需手动解压缩")
                else:
                    raise ValueError("不是有效JSON，需要手动解压缩")
            except (UnicodeDecodeError, ValueError):
                # 如果不是有效JSON，则进行手动解压缩
                logger.info(f"需要手动解压缩，编码格式: {content_encoding}")
                if content_encoding == "gzip":
                    import gzip

                    text_content = gzip.decompress(raw_content).decode("utf-8")
                elif content_encoding == "deflate":
                    import zlib

                    text_content = zlib.decompress(raw_content).decode("utf-8")
                elif content_encoding == "br":
                    import brotli

                    text_content = brotli.decompress(raw_content).decode("utf-8")
                else:
                    text_content = response.text

            logger.info(f"最终内容预览: {text_content[:200]}...")

            # 解析JSON
            import json

            data = json.loads(text_content)

            logger.info(f"API响应解析成功，code: {data.get('code', 'unknown')}")

            if data.get("code") != 0:
                logger.error(f"获取评论总数失败，API返回: {data}")
                return 0

            count = data.get("data", {}).get("count", 0)
            logger.info(f"成功获取评论总数: {count}")
            return count

        except Exception as e:
            logger.error(f"获取评论总数出错: {e}")
            import traceback

            logger.error(f"详细堆栈: {traceback.format_exc()}")
            return 0

    def fetch_video_info(self, bvid: str) -> Dict[str, Any]:
        """获取单个视频的详细信息，包括标题"""
        # 请求前添加延迟
        self.sleep_between_requests()

        # 构建URL
        url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"

        try:
            # 设置特定的请求头
            headers = {
                "Referer": f"https://www.bilibili.com/video/{bvid}",
            }

            # 发送请求
            response = self.session.get(url, headers=headers, timeout=10)
            logger.info(f"获取视频信息的状态码: {response.status_code}")

            response.raise_for_status()
            data = response.json()

            if data.get("code") != 0:
                logger.error(f"获取视频信息失败: {data}")
                return {
                    "code": -1,
                    "message": data.get("message", "未知错误"),
                    "data": {},
                }

            return data

        except Exception as e:
            logger.error(f"获取视频信息出错: {e}")
            return {"code": -1, "message": str(e), "data": {}}

    def fetch_comments(
        self, oid: str, next_page: int, order: int, offset_str: str = ""
    ) -> Dict[str, Any]:
        """获取评论列表"""
        # 请求前添加延迟
        self.sleep_between_requests()

        # 构建请求参数
        if offset_str == "":
            fmt_offset_str = '{"offset":""}'
        else:
            fmt_offset_str = f'{{"offset":{json.dumps(offset_str)}}}'

        # 构建URL - 优先使用旧接口
        params = {"oid": oid, "type": "1", "pn": str(next_page), "sort": str(order)}
        url = "https://api.bilibili.com/x/v2/reply?" + "&".join(
            [f"{k}={v}" for k, v in params.items()]
        )

        logger.info(f"获取评论列表: {url}")

        try:
            response = self.session.get(url, timeout=10)
            logger.info(f"获取评论列表的状态码: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                logger.debug(f"评论接口请求成功: {data.get('code')}")
                return data
            else:
                logger.error(
                    f"评论接口请求失败: {response.status_code} - {response.text[:200]}"
                )

        except Exception as e:
            logger.error(f"获取评论列表出错: {e}")

        # 如果旧接口失败，尝试新接口
        try:
            # 请求前添加延迟
            self.sleep_between_requests("retry")

            # 构建新接口URL
            wbi_params = {
                "oid": oid,
                "type": "1",
                "mode": "3",
                "plat": "1",
                "web_location": "1315875",
                "pagination_str": fmt_offset_str,
            }
            wbi_url = "https://api.bilibili.com/x/v2/reply/wbi/main?" + "&".join(
                [f"{k}={v}" for k, v in wbi_params.items()]
            )

            logger.info(f"尝试使用WBI接口获取评论: {wbi_url}")

            signed_url = sign_and_generate_url(wbi_url, self.cookie)
            response = self.session.get(signed_url, timeout=10)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"WBI接口获取评论列表出错: {e}")
            return {"code": -1, "message": str(e), "data": {"replies": []}}

    def fetch_sub_comments(self, oid: str, rpid: int, next_page: int) -> Dict[str, Any]:
        """获取子评论"""
        # 请求前添加延迟
        self.sleep_between_requests()

        # 构建URL
        params = {
            "oid": oid,
            "type": "1",
            "root": str(rpid),
            "ps": "20",
            "pn": str(next_page),
        }
        url = "https://api.bilibili.com/x/v2/reply/reply?" + "&".join(
            [f"{k}={v}" for k, v in params.items()]
        )

        try:
            signed_url = sign_and_generate_url(url, self.cookie)
            response = self.session.get(signed_url, timeout=10)
            response.raise_for_status()
            return response.json()

        except Exception as e:
            logger.error(f"获取子评论出错: {e}")

            # 失败重试前添加延迟
            self.sleep_between_requests("retry")

            return {"code": -1, "message": str(e), "data": {"replies": []}}

    def fetch_video_list(self, mid: int, page: int, order: str) -> Dict[str, Any]:
        """获取UP主视频列表"""
        # 请求前添加延迟
        self.sleep_between_requests()

        # 构建URL
        params = {
            "mid": str(mid),
            "order": order,
            "platform": "web",
            "pn": str(page),
            "ps": "30",
            "tid": "0",
        }
        url = "https://api.bilibili.com/x/space/wbi/arc/search?" + "&".join(
            [f"{k}={v}" for k, v in params.items()]
        )

        try:
            # 添加完整的请求头
            headers = {
                "Referer": f"https://space.bilibili.com/{mid}/video",
            }

            logger.info(f"获取UP主 {mid} 的视频列表: 页码={page}, 排序={order}")
            signed_url = sign_and_generate_url(url, self.cookie)
            response = self.session.get(signed_url, headers=headers, timeout=10)

            logger.info(f"获取视频列表的状态码: {response.status_code}")
            response.raise_for_status()

            data = response.json()
            if data.get("code") != 0:
                logger.error(f"获取UP主视频列表失败: {data.get('message', '未知错误')}")

            return data

        except Exception as e:
            logger.error(f"获取UP主视频列表出错: {e}")
            return {"code": -1, "message": str(e), "data": {"list": {"vlist": []}}}
