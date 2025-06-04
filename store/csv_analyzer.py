import csv
import logging
from pathlib import Path
from typing import Dict
from models.comment import Stat

from store.geo_exporter import write_geojson
from api.bilibili_api import extract_title_from_dirname

logger = logging.getLogger(__name__)


def normalize_location(location: str) -> str:
    """
    此函数被保留只是为了兼容现有代码
    """
    return location


def print_location_mapping_debug(csv_file_path: str):
    """打印CSV中的地区名称与规范化后的映射关系，帮助调试"""
    try:
        locations = set()
        with open(csv_file_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                location = row.get("location", "")
                if location and location != "未知":
                    locations.add(location)

        logger.info("地区名称映射关系:")
        for location in sorted(locations):
            normalized = normalize_location(location)
            logger.info(f"  {location} -> {normalized}")

    except Exception as e:
        logger.error(f"打印地区映射关系出错: {e}")


def analyze_csv_for_map(csv_file_path: str) -> Dict[str, Stat]:
    """分析CSV生成地图数据"""
    logger.info(f"分析CSV文件: {csv_file_path}")

    csv_path = Path(csv_file_path)
    if not csv_path.exists():
        logger.error(f"CSV文件不存在: {csv_path}")
        return {}

    # 从assets获取GeoJSON数据，建立名称映射表
    from utils.assets_helper import get_geojson_template_path
    import json

    geo_template_path = get_geojson_template_path()
    province_map = {}

    if geo_template_path.exists():
        try:
            with open(geo_template_path, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)

            # 构建地区名称映射表
            # 用于检查是否存在于GeoJSON中
            for feature in geojson_data["features"]:
                province = feature["properties"]["name"]
                province_map[province] = province  # 原名

            logger.info(f"已建立地区映射表，包含 {len(province_map)} 个地区")
        except Exception as e:
            logger.error(f"读取GeoJSON模板失败: {e}")
    else:
        logger.warning(f"GeoJSON模板文件不存在: {geo_template_path}")

    stat_map = {}
    user_maps = {}  # 存储每个地区的用户ID映射，用于调试

    try:
        # 首先检查CSV文件的列名
        with open(csv_path, "r", encoding="utf-8") as f:
            first_line = f.readline().strip()
            header_fields = [field.strip() for field in first_line.split(",")]
            logger.info(f"CSV文件包含以下列: {header_fields}")

            # 检查是否包含必要的列
            required_fields = ["location", "mid", "sex", "like", "level"]
            missing_fields = [
                field for field in required_fields if field not in header_fields
            ]
            if missing_fields:
                logger.warning(f"CSV文件缺少以下列: {missing_fields}")

        # 读取和处理CSV数据
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # 从CSV行创建评论对象
                try:
                    # 处理位置信息
                    location = row.get("location", "").strip()
                    if not location or location == "":
                        location = "未知"  # 确保未知地区也被统计

                    # 获取用户ID
                    user_id = row.get("mid", "0").strip()
                    if not user_id:
                        user_id = "0"
                    user_id = str(user_id)  # 确保ID是字符串

                    # 使用规范化函数处理地区名称
                    normalized_location = normalize_location(location)

                    # 提取有用的统计数据
                    # 处理性别信息
                    sex = row.get("sex", "").strip()
                    if not sex or sex not in ["男", "女", "保密"]:
                        sex = "保密"  # 确保性别值有效

                    # 处理点赞数
                    like_str = row.get("like", "0").strip()
                    try:
                        like = int(like_str)
                    except ValueError:
                        like = 0

                    # 处理等级
                    level_str = row.get("level", "0").strip()
                    try:
                        level = int(level_str)
                        if level < 0 or level > 6:
                            level = 0
                    except ValueError:
                        level = 0

                    # 更新统计信息
                    if normalized_location in stat_map:
                        stat = stat_map[normalized_location]
                        stat.location += 1  # 评论数增加
                        stat.like += like
                        if 0 <= level <= 6:
                            stat.level[level] += 1

                        # 添加用户ID到集合
                        stat.users.add(user_id)

                        # 更新用户性别统计
                        stat.update_user_sex(user_id, sex)

                        # 记录用户ID映射，用于调试
                        if normalized_location not in user_maps:
                            user_maps[normalized_location] = set()
                        user_maps[normalized_location].add(user_id)
                    else:
                        # 创建新的统计项
                        stat = Stat(name=normalized_location, location=1, like=like)
                        if 0 <= level <= 6:
                            stat.level[level] += 1

                        # 添加用户ID到集合
                        stat.users.add(user_id)

                        # 更新用户性别统计
                        stat.update_user_sex(user_id, sex)

                        # 记录用户ID映射，用于调试
                        user_maps[normalized_location] = {user_id}

                        stat_map[normalized_location] = stat

                except Exception as e:
                    logger.warning(f"处理CSV行时出错: {e}, 行: {row}")
                    continue

            # 打印用户统计信息，用于调试
            for location, users in user_maps.items():
                user_count = len(users)
                if location in stat_map:
                    stat = stat_map[location]
                    # 重新计算性别统计，确保准确
                    stat.recalculate_sex_stats()
                    logger.info(
                        f"地区 '{location}' 有 {user_count} 位用户, {stat.location} 条评论"
                    )
                    logger.info(
                        f"性别统计: 男 {stat.sex.get('男', 0)}人, 女 {stat.sex.get('女', 0)}人, 保密 {stat.sex.get('保密', 0)}人"
                    )

            logger.info(f"已分析 {len(stat_map)} 个地区的统计信息")
            return stat_map

    except Exception as e:
        logger.error(f"分析CSV文件出错: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return {}


def generate_map_from_csv(csv_file_path: str, output_dir: str) -> bool:
    """从CSV文件生成地图"""

    try:
        # 打印地区名称映射关系，帮助调试
        print_location_mapping_debug(csv_file_path)

        # 分析CSV得到统计数据
        stat_map = analyze_csv_for_map(csv_file_path)

        if not stat_map:
            logger.warning("没有找到足够的地区数据来生成地图")
            return False

        # 提取文件名作为输出文件名
        csv_path = Path(csv_file_path)
        filename = csv_path.stem

        # 尝试获取视频标题
        video_title = None

        # 方法1: 尝试从CSV文件所在的目录名称中提取标题
        parent_dir = csv_path.parent.name
        if parent_dir.startswith("BV"):
            extracted_title = extract_title_from_dirname(parent_dir)
            if extracted_title:
                video_title = extracted_title
                logger.info(f"从目录名'{parent_dir}'中提取到标题: {video_title}")

        # 方法2: 检查是否存在video_info.json文件
        if not video_title:
            video_info_path = csv_path.parent / "video_info.json"
            if video_info_path.exists():
                try:
                    with open(video_info_path, "r", encoding="utf-8") as f:
                        video_info = json.load(f)
                        # 检查是否有title字段
                        if "title" in video_info:
                            video_title = video_info["title"]
                            logger.info(f"从video_info.json中获取到标题: {video_title}")
                        elif "data" in video_info and "title" in video_info["data"]:
                            video_title = video_info["data"]["title"]
                            logger.info(f"从video_info.json中获取到标题: {video_title}")
                except Exception as e:
                    logger.warning(f"读取video_info.json失败: {e}")

        # 检查stat_map的完整性
        for location, stat in list(stat_map.items()):
            # 确保所有必要的属性都存在
            if not hasattr(stat, "users") or stat.users is None:
                logger.warning(f"地区 '{location}' 缺少users属性，将创建空集合")
                stat.users = set()

            if not hasattr(stat, "user_sex_map") or stat.user_sex_map is None:
                logger.warning(f"地区 '{location}' 缺少user_sex_map属性，将创建空字典")
                stat.user_sex_map = {}

            # 重新计算性别统计
            if hasattr(stat, "recalculate_sex_stats"):
                stat.recalculate_sex_stats()

            # 打印详细统计信息
            logger.info(
                f"地区 '{location}': {stat.location}条评论, {len(stat.users)}位用户"
            )
            logger.info(
                f"性别统计: 男 {stat.sex.get('男', 0)}人, 女 {stat.sex.get('女', 0)}人, 保密 {stat.sex.get('保密', 0)}人"
            )

        # 生成地图
        unmatched_regions = write_geojson(stat_map, filename, output_dir, video_title)
        logger.info(f"已成功从CSV文件生成地图: {output_dir}/{filename}.html")

        # 记录使用的标题
        if video_title:
            logger.info(f"使用视频标题'{video_title}'作为HTML标题")
        else:
            logger.info(f"未找到视频标题，使用BV号'{filename}'作为HTML标题")

        # 输出未匹配地区信息
        if unmatched_regions:
            logger.info(f"有 {len(unmatched_regions)} 个地区未能匹配到地图")
            for region, info in unmatched_regions.items():
                logger.info(
                    f"未匹配地区: {region} - {info['comments']}条评论, {info['users']}位用户"
                )

        return True

    except Exception as e:
        logger.error(f"从CSV生成地图失败: {e}")
        import traceback

        logger.error(traceback.format_exc())
        return False
