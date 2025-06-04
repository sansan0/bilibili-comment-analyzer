import time
import hashlib
import urllib.parse
from typing import Dict, Tuple
import requests  
import logging

logger = logging.getLogger(__name__)

# 加密表
mixin_key_enc_tab = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]

# 缓存
_cache = {}
_last_update_time = 0

# BV转AV常量
XOR_CODE = 23442827791579
MAX_CODE = 2251799813685247
CHARTS = "FcwAPNKTMug3GV5Lj7EJnHpWsx4tb8haYeviqBz6rkCy12mUSDQX9RdoZf"

def sign_and_generate_url(url_str: str, cookie: str) -> str:
    """签名并生成新的URL"""
    parsed_url = urllib.parse.urlparse(url_str)
    query_params = urllib.parse.parse_qs(parsed_url.query)
    
    # 转换为字典
    params = {k: v[0] for k, v in query_params.items()}
    
    # 获取加密密钥
    img_key, sub_key = get_wbi_keys_cached(cookie)
    
    # 加密参数
    new_params = enc_wbi(params, img_key, sub_key)
    
    # 构建新的查询字符串
    new_query = urllib.parse.urlencode(new_params)
    
    # 构建新的URL
    new_url = urllib.parse.urlunparse((
        parsed_url.scheme,
        parsed_url.netloc,
        parsed_url.path,
        parsed_url.params,
        new_query,
        parsed_url.fragment
    ))
    
    return new_url

def enc_wbi(params: Dict[str, str], img_key: str, sub_key: str) -> Dict[str, str]:
    """WBI加密"""
    # 获取混合密钥
    mixin_key = get_mixin_key(img_key + sub_key)
    
    # 添加时间戳
    curr_time = str(int(time.time()))
    params["wts"] = curr_time
    
    # 排序
    sorted_params = sorted(params.items(), key=lambda x: x[0])
    
    # 净化字符串
    params = {k: sanitize_string(v) for k, v in sorted_params}
    
    # 构建查询字符串
    query_str = urllib.parse.urlencode(params)
    
    # 计算w_rid
    w_rid = hashlib.md5((query_str + mixin_key).encode()).hexdigest()
    params["w_rid"] = w_rid
    
    return params

def get_mixin_key(orig: str) -> str:
    """获取混合密钥"""
    result = []
    for index in mixin_key_enc_tab:
        if index < len(orig):
            result.append(orig[index])
    
    return ''.join(result)[:32]

def sanitize_string(s: str) -> str:
    """净化字符串"""
    unwanted_chars = ["!", "'", "(", ")", "*"]
    for char in unwanted_chars:
        s = s.replace(char, "")
    return s

def update_cache(cookie: str) -> None:
    """更新缓存"""
    global _last_update_time
    if time.time() - _last_update_time < 600:  # 10分钟
        return
    
    img_key, sub_key = get_wbi_keys(cookie)
    _cache["img_key"] = img_key
    _cache["sub_key"] = sub_key
    _last_update_time = time.time()

def get_wbi_keys_cached(cookie: str) -> Tuple[str, str]:
    """从缓存获取WBI密钥"""
    update_cache(cookie)
    return _cache.get("img_key", ""), _cache.get("sub_key", "")

def get_wbi_keys(cookie: str) -> Tuple[str, str]:
    """获取WBI密钥"""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://www.bilibili.com/",
        "Cookie": cookie
    }
    
    try:
        response = requests.get("https://api.bilibili.com/x/web-interface/nav", headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        img_url = data.get("data", {}).get("wbi_img", {}).get("img_url", "")
        sub_url = data.get("data", {}).get("wbi_img", {}).get("sub_url", "")
        
        img_key = img_url.split("/")[-1].split(".")[0]
        sub_key = sub_url.split("/")[-1].split(".")[0]
        
        return img_key, sub_key
    except Exception as e:
        logger.error(f"获取WBI密钥失败: {e}")
        return "", ""

def swap_string(s: str, x: int, y: int) -> str:
    """交换字符串中的两个字符"""
    s_list = list(s)
    s_list[x], s_list[y] = s_list[y], s_list[x]
    return ''.join(s_list)

def bvid_to_avid(bvid: str) -> int:
    """BV号转AV号"""
    try:
        s = swap_string(swap_string(bvid, 3, 9), 4, 7)
        bv1 = s[3:]
        temp = 0
        
        for c in bv1:
            idx = CHARTS.find(c)
            if idx == -1:  # 如果找不到字符
                logger.error(f"BV号转AV号失败: 无效字符 {c}")
                return 0
            temp = temp * 58 + idx
        
        avid = (temp & MAX_CODE) ^ XOR_CODE
        logger.info(f"BV号 {bvid} 转换为AV号 {avid}")
        return avid
    except Exception as e:
        logger.error(f"BV号转AV号失败: {e}")
        # 如果转换失败，可以尝试将BV号部分作为ID使用
        return 0

def avid_to_bvid(avid: int) -> str:
    """AV号转BV号"""
    arr = ["B", "V", "1"] + [""] * 9
    bv_idx = len(arr) - 1
    temp = (avid | (MAX_CODE + 1)) ^ XOR_CODE
    
    while temp > 0:
        idx = temp % 58
        arr[bv_idx] = CHARTS[idx]
        temp //= 58
        bv_idx -= 1
    
    raw = ''.join(arr)
    bvid = swap_string(swap_string(raw, 3, 9), 4, 7)
    return bvid