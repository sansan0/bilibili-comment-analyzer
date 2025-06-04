"""
哔哩哔哩 API 模块
提供与哔哩哔哩平台交互的核心功能
"""

from .bilibili_api import (
    BilibiliAPI, 
    sanitize_filename, 
    extract_title_from_dirname, 
    get_dir_name,
    parse_bilibili_url,
    extract_ep_id
)
from .crypto import sign_and_generate_url, bvid_to_avid, avid_to_bvid

__all__ = [
    'BilibiliAPI', 
    'sanitize_filename', 
    'extract_title_from_dirname', 
    'get_dir_name',
    'parse_bilibili_url',
    'extract_ep_id',
    'sign_and_generate_url', 
    'bvid_to_avid', 
    'avid_to_bvid'
]