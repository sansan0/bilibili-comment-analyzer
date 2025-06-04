import csv
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Any
from collections import defaultdict
from pathlib import Path


from utils.assets_helper import (
    get_stopwords_path,
    get_pkuseg_model_path,
    get_wordcloud_template_path,
)
from store.csv_analyzer import normalize_location

logger = logging.getLogger(__name__)

# 全局分词器变量
_segmenter = None
_segmenter_available = False


def init_segmenter():
    """初始化分词器"""
    global _segmenter, _segmenter_available

    if _segmenter is not None:
        return _segmenter_available

    try:
        import spacy_pkuseg as pkuseg

        logger.info("成功导入spacy_pkuseg模块")
    except ImportError as e:
        logger.error(f"无法导入spacy_pkuseg模块: {e}")
        logger.error("请确保已安装spacy-pkuseg包")
        _segmenter_available = False
        return False

    try:
        # 使用新的路径获取方法
        model_path = get_pkuseg_model_path()
        logger.info(f"pkuseg模型路径: {model_path}")
        logger.info(f"模型路径是否存在: {model_path.exists()}")

        if not model_path.exists():
            logger.warning(f"pkuseg本地模型不存在: {model_path}")
            logger.info("尝试使用pkuseg默认模型")
            try:
                _segmenter = pkuseg.pkuseg()
                _segmenter_available = True
                logger.info("成功使用pkuseg默认模型初始化分词器")
            except Exception as e:
                logger.error(f"使用默认模型初始化分词器失败: {e}")
                _segmenter_available = False
                return False
        else:
            # 使用本地模型初始化分词器
            try:
                _segmenter = pkuseg.pkuseg(model_name=str(model_path))
                _segmenter_available = True
                logger.info(f"pkuseg分词器初始化成功，使用本地模型: {model_path}")
            except Exception as e:
                logger.error(f"使用本地模型初始化失败: {e}")
                logger.info("回退到默认模型")
                try:
                    _segmenter = pkuseg.pkuseg()
                    _segmenter_available = True
                    logger.info("成功使用pkuseg默认模型初始化分词器")
                except Exception as e2:
                    logger.error(f"使用默认模型也失败: {e2}")
                    _segmenter_available = False
                    return False

        # 测试分词器
        try:
            test_result = _segmenter.cut("测试分词器")
            logger.info(f"分词器测试结果: {test_result}")
        except Exception as e:
            logger.error(f"分词器测试失败: {e}")
            _segmenter_available = False
            return False

        return True

    except Exception as e:
        logger.error(f"初始化pkuseg分词器时发生未预期错误: {e}")
        import traceback

        logger.error(f"详细错误堆栈: {traceback.format_exc()}")
        _segmenter_available = False
        return False


def extract_emojis(text: str) -> List[str]:
    """提取评论中的表情符号，包括[表情名]和Unicode emoji

    Args:
        text: 原始评论文本

    Returns:
        去重后的表情符号列表
    """
    if not text:
        return []

    emojis = set()

    # 1. 匹配 [表情名] 格式的表情
    bracket_emoji_pattern = r"\[([^\]]+)\]"
    bracket_matches = re.findall(bracket_emoji_pattern, text)
    for match in bracket_matches:
        emojis.add(f"[{match}]")

    # 2. 匹配 Unicode emoji
    # 常见的emoji Unicode范围
    unicode_emoji_pattern = (
        r"[\U0001F600-\U0001F64F]|"  # 表情符号
        r"[\U0001F300-\U0001F5FF]|"  # 杂项符号和象形文字
        r"[\U0001F680-\U0001F6FF]|"  # 交通和地图符号
        r"[\U0001F1E0-\U0001F1FF]|"  # 区域指示符号
        r"[\U00002600-\U000026FF]|"  # 杂项符号
        r"[\U00002700-\U000027BF]|"  # 装饰符号
        r"[\U0001F900-\U0001F9FF]|"  # 补充符号和象形文字
        r"[\U0001FA70-\U0001FAFF]|"  # 符号和象形文字扩展A
        r"[\U00002500-\U00002BEF]|"  # 各种技术符号
        r"[\U0001F018-\U0001F270]"  # 其他符号
    )

    unicode_matches = re.findall(unicode_emoji_pattern, text)
    for match in unicode_matches:
        emojis.add(match)

    result = sorted(list(emojis))

    if result:
        logger.debug(f"从文本 '{text[:50]}...' 中提取到表情: {result}")

    return result


def remove_emojis_from_text(text: str) -> str:
    """从文本中移除表情符号，用于分词处理

    Args:
        text: 原始文本

    Returns:
        去除表情后的文本
    """
    if not text:
        return ""

    # 移除 [表情名] 格式的表情
    text = re.sub(r"\[([^\]]+)\]", "", text)

    # 移除 Unicode emoji
    unicode_emoji_pattern = (
        r"[\U0001F600-\U0001F64F]|"  # 表情符号
        r"[\U0001F300-\U0001F5FF]|"  # 杂项符号和象形文字
        r"[\U0001F680-\U0001F6FF]|"  # 交通和地图符号
        r"[\U0001F1E0-\U0001F1FF]|"  # 区域指示符号
        r"[\U00002600-\U000026FF]|"  # 杂项符号
        r"[\U00002700-\U000027BF]|"  # 装饰符号
        r"[\U0001F900-\U0001F9FF]|"  # 补充符号和象形文字
        r"[\U0001FA70-\U0001FAFF]|"  # 符号和象形文字扩展A
        r"[\U00002500-\U00002BEF]|"  # 各种技术符号
        r"[\U0001F018-\U0001F270]"  # 其他符号
    )

    text = re.sub(unicode_emoji_pattern, "", text)

    # 清理多余的空格
    text = re.sub(r"\s+", " ", text).strip()

    return text


def clean_comment_content(content: str) -> str:
    """清洗评论内容，移除@用户名等

    Args:
        content: 原始评论内容

    Returns:
        清洗后的内容，如果清洗后为空则返回空字符串
    """
    if not content:
        return ""

    original_content = content

    # 更全面的@用户名匹配模式
    # 支持中文、英文、数字、下划线、连字符等常见用户名字符
    username_pattern = r"[\w\u4e00-\u9fa5℃\-_]+"

    # 1. 处理开头的各种回复格式
    # "回复 @用户名:" 或 "回复 @用户名 " 或 "回复@用户名:"
    content = re.sub(rf"^回复\s*@{username_pattern}\s*:?\s*", "", content)

    # 2. 处理开头的直接@格式
    # "@用户名:" 或 "@用户名 " 或 "@-用户名-" 等
    content = re.sub(rf"^@-?{username_pattern}-?\s*:?\s*", "", content)

    # 3. 处理结尾的@用户名
    content = re.sub(rf"@-?{username_pattern}-?\s*$", "", content)

    # 4. 处理中间的@用户名（保守处理，只移除明显的@标记）
    # 避免移除正常文本中包含@的内容
    content = re.sub(rf"\s@-?{username_pattern}-?\s", " ", content)

    # 清理多余的空格和标点
    content = re.sub(r"\s+", " ", content).strip()
    content = re.sub(r"^[:：\s]+|[:：\s]+$", "", content).strip()

    # 如果内容只剩下@用户名相关的内容，返回空字符串
    if re.fullmatch(rf"@-?{username_pattern}-?", content):
        logger.debug(f"评论内容 '{original_content}' 清洗后仅剩@用户名，返回空内容")
        return ""

    # 如果清洗后内容为空或只剩标点符号，返回空字符串
    if not content or re.fullmatch(r"[^\w\u4e00-\u9fa5]+", content):
        logger.debug(f"评论内容 '{original_content}' 清洗后为空或仅含标点，返回空内容")
        return ""

    logger.debug(f"评论清洗: '{original_content}' -> '{content}'")
    return content


def remove_all_punctuation(text: str) -> str:
    """彻底移除文本中的所有标点符号

    Args:
        text: 输入文本

    Returns:
        移除所有标点符号后的文本
    """
    if not text:
        return ""

    # 定义要移除的所有标点符号（包含中英文标点）
    punctuation_to_remove = [
        # 英文标点
        "!",
        "@",
        "#",
        "$",
        "%",
        "^",
        "&",
        "*",
        "(",
        ")",
        "_",
        "+",
        "-",
        "=",
        "[",
        "]",
        "{",
        "}",
        ";",
        "'",
        '"',
        "\\",
        "|",
        ",",
        ".",
        "<",
        ">",
        "/",
        "?",
        "~",
        # 中文标点
        "，",
        "。",
        "；",
        "：",
        "？",
        "！",
        '"',
        '"',
        """, """,
        "（",
        "）",
        "【",
        "】",
        "《",
        "》",
        "、",
        "～",
        "·",
        "｜",
        # 各种省略号和破折号
        "…",
        "...",
        "......",
        "。。。",
        "···",
        "••",
        "‥",
        "‧",
        "——",
        "—",
        "–",
        "―",
        "‖",
        "¦",
        "‾",
        "＿",
        # 其他符号
        "°",
        "※",
        "★",
        "☆",
        "♪",
        "♫",
        "♬",
        "♭",
        "♮",
        "♯",
        "→",
        "←",
        "↑",
        "↓",
        "↖",
        "↗",
        "↘",
        "↙",
        "↔",
        "↕",
        "∞",
        "±",
        "×",
        "÷",
        "≠",
        "≤",
        "≥",
        "≈",
        "∑",
        "∏",
        "§",
        "¶",
        "†",
        "‡",
        "•",
        "‰",
        "′",
        "″",
        "‴",
        "※",
    ]

    # 移除所有标点符号
    cleaned_text = text
    for punct in punctuation_to_remove:
        cleaned_text = cleaned_text.replace(punct, " ")

    # 使用正则表达式移除其他可能的标点符号
    # 保留中文、英文字母、数字和空格，其他都移除
    cleaned_text = re.sub(r"[^\u4e00-\u9fa5a-zA-Z0-9\s]", " ", cleaned_text)

    # 清理多余的空格
    cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

    logger.debug(f"标点符号清理: '{text[:50]}...' -> '{cleaned_text[:50]}...'")
    return cleaned_text


def segment_text(text: str, stopwords: List[str]) -> List[str]:
    """对文本进行分词并过滤停用词

    处理流程：
    1. 清洗评论内容（移除@用户名等）
    2. 移除表情符号
    3. 彻底移除所有标点符号
    4. 进行分词
    5. 过滤停用词和短词

    Args:
        text: 要分词的文本
        stopwords: 停用词列表

    Returns:
        分词并过滤停用词后的去重词汇列表
    """
    if not text or not text.strip():
        return []

    # 步骤1: 清洗评论内容（移除@用户名等）
    cleaned_text = clean_comment_content(text)
    if not cleaned_text or not cleaned_text.strip():
        logger.debug(f"评论内容清洗后为空: '{text[:50]}...'")
        return []

    # 步骤2: 移除表情符号
    text_without_emojis = remove_emojis_from_text(cleaned_text)
    if not text_without_emojis or not text_without_emojis.strip():
        logger.debug(f"移除表情后为空: '{text[:50]}...'")
        return []

    # 步骤3: 彻底移除所有标点符号
    text_without_punctuation = remove_all_punctuation(text_without_emojis)
    if not text_without_punctuation or not text_without_punctuation.strip():
        logger.debug(f"移除标点后为空: '{text[:50]}...'")
        return []

    logger.debug(
        f"文本处理完成: '{text[:30]}...' -> '{text_without_punctuation[:30]}...'"
    )

    # 步骤4: 进行分词
    # 使用pkuseg进行分词
    tokens = _segmenter.cut(text_without_punctuation)

    # 步骤5: 过滤停用词和无效词汇，同时去重
    seen_tokens = set()
    filtered_tokens = []

    for token in tokens:
        # 清理token（去除首尾空格）
        token = token.strip()

        # 记录所有token用于调试
        if token:
            logger.debug(f"处理token: '{token}' (长度: {len(token)})")

        # 过滤条件
        if (
            not token  # 空token
            or len(token) < 2  # 长度过短
            or re.match(r"^\d+$", token)  # 纯数字
            or re.match(r"^[a-zA-Z]$", token)  # 单个英文字母
            or token in stopwords  # 停用词
            or token in seen_tokens
        ):  # 已出现过的词（去重）

            logger.debug(
                f"过滤掉token: '{token}' (原因: 长度不足/纯数字/单字母/停用词/重复)"
            )
            continue

        # 额外检查：确保没有遗漏的标点符号
        if re.match(r"^[^\u4e00-\u9fa5a-zA-Z0-9]+$", token):
            logger.warning(
                f"发现遗漏的标点符号token: '{token}' (Unicode: {[ord(c) for c in token]})"
            )
            continue

        seen_tokens.add(token)
        filtered_tokens.append(token)

    logger.debug(
        f"最终分词结果: {len(filtered_tokens)} 个词汇 -> {filtered_tokens[:10]}{'...' if len(filtered_tokens) > 10 else ''}"
    )
    return filtered_tokens


def calculate_reply_counts(comments_data: List[Dict[str, Any]]) -> Dict[int, int]:
    """计算每个评论的被回复次数

    Args:
        comments_data: 评论数据列表

    Returns:
        rpid -> 被回复次数的映射字典
    """
    reply_counts = defaultdict(int)

    # 统计每个parent_id出现的次数
    for comment in comments_data:
        parent_id = comment.get("parent_id", 0)
        if parent_id != 0:  # 只统计回复
            reply_counts[parent_id] += 1

    logger.info(f"统计被回复次数完成，共有 {len(reply_counts)} 个评论被回复")

    # 输出一些统计信息
    if reply_counts:
        max_replies = max(reply_counts.values())
        total_replies = sum(reply_counts.values())
        logger.info(f"最多被回复次数: {max_replies}, 总回复数: {total_replies}")

    return dict(reply_counts)


def analyze_csv_for_wordcloud(csv_file_path: str) -> Dict[str, Any]:
    """从CSV文件分析评论数据，生成词云所需的数据结构"""
    logger.info(f"分析CSV文件用于词云生成: {csv_file_path}")

    csv_path = Path(csv_file_path)
    if not csv_path.exists():
        logger.error(f"CSV文件不存在: {csv_path}")
        return {}

    # 从assets获取GeoJSON数据，建立名称映射表
    from utils.assets_helper import get_geojson_template_path

    geo_template_path = get_geojson_template_path()
    province_map = {}

    if geo_template_path.exists():
        try:
            with open(geo_template_path, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)

            # 构建地区名称映射表
            for feature in geojson_data["features"]:
                province = feature["properties"]["name"]
                province_map[province] = province

            logger.info(f"已建立地区映射表，包含 {len(province_map)} 个地区")
        except Exception as e:
            logger.error(f"读取GeoJSON模板失败: {e}")
    else:
        logger.warning(f"GeoJSON模板文件不存在: {geo_template_path}")

    # 加载停用词
    stopwords = load_stopwords()
    logger.info(f"已加载 {len(stopwords)} 个停用词")

    # 初始化分词器
    init_segmenter()
    logger.info("使用pkuseg分词引擎")

    # 初始化数据结构
    regions_set = set()
    genders_set = set()
    levels_set = set()
    users_set = set()
    all_emojis = set()  # 存储所有出现的表情
    region_stats = defaultdict(
        lambda: {
            "comments": 0,
            "users": set(),
            "by_gender": {"男": 0, "女": 0, "保密": 0},
            "by_level": [0] * 7,
            "likes": 0,
        }
    )

    comments_data = []
    processed_rows = 0
    error_rows = 0
    segmentation_errors = 0
    emoji_extraction_errors = 0
    empty_after_cleaning = 0

    try:
        # 尝试不同的编码格式
        encodings = ["utf-8", "gbk", "gb2312", "utf-8-sig"]
        csv_content = None

        for encoding in encodings:
            try:
                with open(csv_path, "r", encoding=encoding) as f:
                    csv_content = f.read()
                    logger.info(f"成功使用 {encoding} 编码读取CSV文件")
                    break
            except UnicodeDecodeError:
                logger.debug(f"使用 {encoding} 编码读取失败，尝试下一个")
                continue

        if csv_content is None:
            logger.error("无法使用任何编码格式读取CSV文件")
            return {}

        # 分析CSV结构
        lines = csv_content.strip().split("\n")
        if len(lines) < 2:
            logger.error("CSV文件内容不足，至少需要表头和一行数据")
            return {}

        # 检查表头
        header_line = lines[0]
        logger.info(f"CSV表头: {header_line}")

        from io import StringIO

        csv_file = StringIO(csv_content)
        reader = csv.DictReader(csv_file)

        # 检查必要字段
        fieldnames = reader.fieldnames
        logger.info(f"CSV字段名: {fieldnames}")

        required_fields = [
            "content",
            "location",
            "mid",
            "sex",
            "level",
            "like",
            "rpid",
            "parent",
        ]
        missing_fields = [field for field in required_fields if field not in fieldnames]
        if missing_fields:
            logger.warning(f"CSV文件缺少字段: {missing_fields}")

        # 第一遍：读取所有数据，准备计算被回复次数
        temp_comments_data = []

        # 处理每一行数据
        for row_num, row in enumerate(reader, start=2):  # 从第2行开始计数
            try:
                # 安全获取字段值的函数
                def safe_get(field_name, default=""):
                    value = row.get(field_name, default)
                    if value is None:
                        return default
                    return str(value).strip()

                # 处理评论内容
                content = safe_get("content", "")
                if not content:
                    logger.debug(f"第{row_num}行: 评论内容为空，跳过")
                    continue

                # 提取表情符号
                try:
                    emojis = extract_emojis(content)
                    all_emojis.update(emojis)  # 收集所有表情
                except Exception as e:
                    logger.warning(f"第{row_num}行表情提取失败: {e}")
                    emojis = []
                    emoji_extraction_errors += 1

                # 对内容进行分词处理（会自动排除表情）
                try:
                    tokens = segment_text(content, stopwords)
                    if not tokens and content.strip():
                        # 如果原内容不为空但分词结果为空，记录统计
                        empty_after_cleaning += 1
                        logger.debug(
                            f"第{row_num}行: 评论内容清洗后为空，原内容: '{content[:50]}...'"
                        )
                except Exception as e:
                    logger.warning(f"第{row_num}行分词失败: {e}")
                    tokens = []
                    segmentation_errors += 1

                # 处理位置信息
                location = safe_get("location", "未知")
                if not location:
                    location = "未知"

                # 规范化地区名称
                normalized_location = normalize_location(location)

                # 处理用户ID
                user_id = safe_get("mid", "0")
                if not user_id or user_id == "":
                    user_id = "0"
                user_id = str(user_id)  # 确保是字符串

                # 处理性别
                sex = safe_get("sex", "保密")
                if sex not in ["男", "女", "保密"]:
                    sex = "保密"

                # 处理等级
                level_str = safe_get("level", "0")
                try:
                    level = int(float(level_str))  # 先转float再转int，处理"1.0"这种情况
                    if level < 0 or level > 6:
                        level = 0
                except (ValueError, TypeError):
                    logger.debug(
                        f"第{row_num}行: 等级值'{level_str}'无法转换为整数，使用默认值0"
                    )
                    level = 0

                # 处理点赞数
                like_str = safe_get("like", "0")
                try:
                    like = int(float(like_str))
                    if like < 0:
                        like = 0
                except (ValueError, TypeError):
                    logger.debug(
                        f"第{row_num}行: 点赞数'{like_str}'无法转换为整数，使用默认值0"
                    )
                    like = 0

                # 处理rpid - 评论ID（仅用于内部计算）
                rpid_str = safe_get("rpid", "0")
                try:
                    rpid = int(float(rpid_str))
                except (ValueError, TypeError):
                    logger.debug(
                        f"第{row_num}行: rpid值'{rpid_str}'无法转换为整数，使用默认值0"
                    )
                    rpid = 0

                # 处理parent - 父评论ID（仅用于内部计算）
                parent_str = safe_get("parent", "0")
                try:
                    parent_id = int(float(parent_str))
                except (ValueError, TypeError):
                    logger.debug(
                        f"第{row_num}行: parent值'{parent_str}'无法转换为整数，使用默认值0"
                    )
                    parent_id = 0

                # 判断是否为回复
                is_reply = parent_id != 0

                # 收集实际存在的数据 - 确保等级是整数
                regions_set.add(normalized_location)
                genders_set.add(sex)
                levels_set.add(level)  # 添加整数等级
                users_set.add(user_id)

                # 创建临时评论数据（包含rpid和parent_id用于计算）
                temp_comment_data = {
                    "content": content,  # 保留原始内容
                    "tokens": tokens,  # 分词结果
                    "emojis": emojis,  # 表情列表
                    "is_reply": is_reply,  # 是否为回复
                    "parent_id": parent_id,  # 父评论ID（临时用于计算）
                    "rpid": rpid,  # 评论ID（临时用于计算）
                    "location": normalized_location,
                    "sex": sex,
                    "level": level,
                    "like": like,
                    "mid": user_id,
                    "row_num": row_num,  # 临时保存行号用于调试
                }
                temp_comments_data.append(temp_comment_data)

                # 更新统计信息
                region_stats[normalized_location]["comments"] += 1
                region_stats[normalized_location]["likes"] += like
                region_stats[normalized_location]["users"].add(user_id)
                region_stats[normalized_location]["by_gender"][sex] += 1

                if 0 <= level <= 6:
                    region_stats[normalized_location]["by_level"][level] += 1

                processed_rows += 1

                # 每处理1000行输出一次进度
                if processed_rows % 1000 == 0:
                    logger.info(
                        f"已处理 {processed_rows} 行数据，"
                        f"分词错误 {segmentation_errors} 行，"
                        f"表情提取错误 {emoji_extraction_errors} 行，"
                        f"清洗后为空 {empty_after_cleaning} 行"
                    )

            except Exception as e:
                error_rows += 1
                logger.warning(f"第{row_num}行处理出错: {str(e)[:100]}...")
                logger.debug(f"第{row_num}行详细错误: {e}")
                logger.debug(f"第{row_num}行数据: {dict(row)}")

                # 如果错误行数过多，停止处理
                if error_rows > 100:
                    logger.error(f"错误行数过多({error_rows}行)，停止处理")
                    break

                continue

        logger.info(
            f"第一遍CSV处理完成: 成功处理 {processed_rows} 行，错误 {error_rows} 行"
        )
        logger.info(
            f"分词错误 {segmentation_errors} 行，表情提取错误 {emoji_extraction_errors} 行，清洗后为空 {empty_after_cleaning} 行"
        )

        # 检查是否有有效数据
        if not temp_comments_data:
            logger.error("没有有效的评论数据")
            return {}

        # 计算被回复次数
        logger.info("开始计算被回复次数...")
        reply_counts = calculate_reply_counts(temp_comments_data)

        # 第二遍：添加被回复次数并生成最终数据（移除敏感字段）
        comments_data = []
        for temp_comment in temp_comments_data:
            rpid = temp_comment["rpid"]
            reply_count = reply_counts.get(rpid, 0)

            # 生成最终评论数据，移除rpid和parent_id字段
            final_comment = {
                "content": temp_comment["content"],
                "tokens": temp_comment["tokens"],
                "emojis": temp_comment["emojis"],
                "is_reply": temp_comment["is_reply"],
                "reply_count": reply_count,
                "location": temp_comment["location"],
                "sex": temp_comment["sex"],
                "level": temp_comment["level"],
                "like": temp_comment["like"],
                "mid": temp_comment["mid"],
            }

            comments_data.append(final_comment)

        # 统计回复相关信息
        total_replies = sum(1 for comment in comments_data if comment["is_reply"])
        total_root_comments = len(comments_data) - total_replies

        logger.info(
            f"评论统计: 总评论 {len(comments_data)} 条，直接评论 {total_root_comments} 条，回复 {total_replies} 条"
        )

        # 构建最终数据结构
        data = {
            "regions": sorted(list(regions_set)),
            "genders": sorted(list(genders_set)),
            "levels": sorted(list(levels_set)),  # 确保等级列表是整数
            "emojis": sorted(list(all_emojis)),  # 所有出现的表情
            "comments": comments_data,
            "stopwords": stopwords,  # 添加停用词
            "statistics": {
                "total_comments": len(comments_data),
                "total_users": len(users_set),
                "total_emojis": len(all_emojis),
                "direct_comments": total_root_comments,
                "reply_comments": total_replies,
                "by_region": {},
                "by_gender": {gender: 0 for gender in genders_set},
                "by_level": {level: 0 for level in levels_set},
                "reply_statistics": {
                    "comments_with_replies": len(reply_counts),
                    "max_reply_count": (
                        max(reply_counts.values()) if reply_counts else 0
                    ),
                    "total_reply_relationships": (
                        sum(reply_counts.values()) if reply_counts else 0
                    ),
                },
            },
        }

        # 计算全局统计
        for comment in comments_data:
            data["statistics"]["by_gender"][comment["sex"]] += 1
            data["statistics"]["by_level"][comment["level"]] += 1

        # 处理地区统计
        for region, stats in region_stats.items():
            data["statistics"]["by_region"][region] = {
                "comments": stats["comments"],
                "users": len(stats["users"]),
                "by_gender": stats["by_gender"],
                "by_level": stats["by_level"],
                "likes": stats["likes"],
            }

        logger.info(f"数据分析完成:")
        logger.info(f"  - 总评论数: {len(data['comments'])}")
        logger.info(f"  - 总用户数: {len(users_set)}")
        logger.info(f"  - 涉及地区: {len(data['regions'])} 个")
        logger.info(f"  - 实际性别: {data['genders']}")
        logger.info(f"  - 实际等级: {data['levels']}")
        logger.info(f"  - 停用词数量: {len(stopwords)}")
        logger.info(f"  - 表情种类: {len(all_emojis)} 个")
        logger.info(f"  - 直接评论: {total_root_comments} 条")
        logger.info(f"  - 回复评论: {total_replies} 条")

        return data

    except Exception as e:
        logger.error(f"分析CSV文件时发生致命错误: {e}")
        import traceback

        logger.error(f"详细错误信息: {traceback.format_exc()}")
        return {}


def load_stopwords() -> List[str]:
    """加载停用词列表"""
    try:
        stopwords_path = get_stopwords_path()

        if not stopwords_path.exists():
            logger.warning(f"停用词文件不存在: {stopwords_path}")
            return []

        with open(stopwords_path, "r", encoding="utf-8") as f:
            stopwords = [line.strip() for line in f if line.strip()]

        logger.info(f"成功加载 {len(stopwords)} 个停用词")
        return stopwords

    except Exception as e:
        logger.error(f"加载停用词失败: {e}")
        return []


def generate_wordcloud_from_csv(csv_file_path: str, output_dir: str) -> bool:
    """从CSV文件生成词云HTML页面"""
    try:
        logger.info(f"开始生成词云: CSV={csv_file_path}, 输出={output_dir}")

        # 检查CSV文件是否存在
        csv_path = Path(csv_file_path)
        if not csv_path.exists():
            logger.error(f"CSV文件不存在: {csv_path}")
            return False

        # 检查输出目录
        output_dir_path = Path(output_dir)
        logger.info(f"输出目录: {output_dir_path}")
        logger.info(f"输出目录是否存在: {output_dir_path.exists()}")

        # 首先检查分词器是否可用
        logger.info("正在初始化分词器...")
        if not init_segmenter():
            logger.error("分词器初始化失败，无法生成词云")
            logger.error("可能的原因:")
            logger.error("1. spacy-pkuseg包未正确安装")
            logger.error("2. pkuseg模型文件缺失")
            logger.error("3. 打包环境下模块导入失败")
            return False

        logger.info("分词器初始化成功，开始分析CSV数据...")

        # 分析CSV数据
        try:
            data = analyze_csv_for_wordcloud(csv_file_path)
        except Exception as e:
            logger.error(f"分析CSV文件失败: {e}")
            import traceback

            logger.error(f"详细错误: {traceback.format_exc()}")
            return False

        if not data or not data.get("comments"):
            logger.error("没有找到足够的评论数据来生成词云")
            logger.error("可能的原因:")
            logger.error("1. CSV文件为空或格式不正确")
            logger.error("2. CSV文件中没有有效的评论内容")
            logger.error("3. 所有评论在清洗后都变为空")
            return False

        logger.info(f"成功分析到 {len(data.get('comments', []))} 条评论数据")

        # 提取文件名
        filename = csv_path.stem

        # 尝试获取内容标题
        content_title = None

        # 方法1: 从目录名提取标题
        parent_dir = csv_path.parent.name
        if parent_dir.startswith("BV") or parent_dir.startswith("EP"):
            try:
                from api.bilibili_api import extract_title_from_dirname

                extracted_title = extract_title_from_dirname(parent_dir)
                if extracted_title:
                    content_title = extracted_title
                    logger.info(f"从目录名提取到标题: {content_title}")
            except Exception as e:
                logger.debug(f"从目录名提取标题失败: {e}")

        # 方法2: 从content_info.json提取标题
        if not content_title:
            content_info_path = csv_path.parent / "content_info.json"
            if content_info_path.exists():
                try:
                    with open(content_info_path, "r", encoding="utf-8") as f:
                        content_info = json.load(f)

                    # 直接获取data.title字段
                    title = content_info.get("data", {}).get("title", "")
                    if title and title.strip():
                        content_title = title.strip()
                        logger.info(f"从content_info.json获取到标题: {content_title}")
                    else:
                        logger.warning("content_info.json中的data.title字段为空")

                except Exception as e:
                    logger.warning(f"读取content_info.json失败: {e}")

        # 确保输出目录存在
        try:
            output_dir_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"输出目录已确保存在: {output_dir_path}")
        except Exception as e:
            logger.error(f"创建输出目录失败: {e}")
            return False

        # 保存数据到JSON文件
        data_file = output_dir_path / f"{filename}_wordcloud_data.json"
        try:
            logger.info(f"正在保存词云数据到: {data_file}")
            with open(data_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            # 验证文件是否真正写入
            if data_file.exists():
                file_size = data_file.stat().st_size
                if file_size > 0:
                    logger.info(
                        f"词云数据保存成功: {data_file} (大小: {file_size} 字节)"
                    )
                else:
                    logger.error(f"词云数据文件为空: {data_file}")
                    return False
            else:
                logger.error(f"词云数据文件未创建: {data_file}")
                return False

        except PermissionError as e:
            logger.error(f"没有权限写入词云数据文件: {e}")
            return False
        except Exception as e:
            logger.error(f"保存词云数据失败: {e}")
            import traceback

            logger.error(f"详细错误: {traceback.format_exc()}")
            return False

        # 生成HTML文件 - 使用实际标题或标识符
        html_file = output_dir_path / f"{filename}_wordcloud.html"
        try:
            logger.info(f"正在生成词云HTML文件: {html_file}")
            # 如果有实际标题就使用，否则使用标识符
            display_title = content_title if content_title else filename
            render_wordcloud_html(
                display_title,
                f"{filename}_wordcloud_data.json",
                str(html_file),
            )

            # 验证HTML文件是否真正生成
            if html_file.exists():
                file_size = html_file.stat().st_size
                if file_size > 0:
                    logger.info(
                        f"词云HTML生成成功: {html_file} (大小: {file_size} 字节)"
                    )
                    logger.info(f"使用标题: {display_title}")
                    return True
                else:
                    logger.error(f"词云HTML文件为空: {html_file}")
                    return False
            else:
                logger.error(f"词云HTML文件未创建: {html_file}")
                return False

        except Exception as e:
            logger.error(f"生成词云HTML失败: {e}")
            import traceback

            logger.error(f"详细错误: {traceback.format_exc()}")
            return False

    except Exception as e:
        logger.error(f"生成词云过程中发生未预期错误: {e}")
        import traceback

        logger.error(f"详细错误堆栈: {traceback.format_exc()}")
        return False


def render_wordcloud_html(title: str, data_file: str, output_path: str) -> None:
    """渲染词云HTML文件"""
    try:
        # 读取模板文件
        template_path = get_wordcloud_template_path()
        logger.info(f"词云模板路径: {template_path}")
        logger.info(f"模板文件是否存在: {template_path.exists()}")

        if not template_path.exists():
            logger.error(f"词云模板文件不存在: {template_path}")
            raise FileNotFoundError(f"词云模板文件不存在: {template_path}")

        # 读取模板内容
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template_content = f.read()
            logger.info(f"成功读取模板内容，长度: {len(template_content)} 字符")
        except Exception as e:
            logger.error(f"读取词云模板失败: {e}")
            raise

        # 替换模板变量
        html_content = template_content.replace("{{ .Title }}", title)
        html_content = html_content.replace("{{ .DataFile }}", data_file)
        logger.info(f"模板变量替换完成，标题: {title}, 数据文件: {data_file}")

        # 保存HTML文件
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(f"词云HTML模板渲染完成: {output_path}")
        except Exception as e:
            logger.error(f"写入词云HTML文件失败: {e}")
            raise

    except Exception as e:
        logger.error(f"渲染词云HTML失败: {e}")
        import traceback

        logger.error(f"详细错误: {traceback.format_exc()}")
        raise
