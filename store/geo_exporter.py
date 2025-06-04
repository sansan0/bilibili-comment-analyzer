import json
import logging
from pathlib import Path
from typing import Dict
from utils.assets_helper import get_geojson_template_path, get_template_path
from models.comment import Stat

logger = logging.getLogger(__name__)


def write_geojson(
    stat_map: Dict[str, Stat], filename: str, output_dir: str, video_title: str = None
) -> Dict[str, Dict[str, int]]:
    """生成GeoJSON文件和HTML地图，并返回未匹配地区的评论数量和用户数量"""
    unmatched_regions = {}  # 存储未匹配地区的评论数量和用户数量

    try:
        # 确保输出目录存在
        output_path = Path(output_dir)
        logger.info(f"输出目录: {output_path}")
        logger.info(f"输出目录是否存在: {output_path.exists()}")
        
        try:
            output_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"输出目录已确保存在: {output_path}")
        except Exception as e:
            logger.error(f"创建输出目录失败: {e}")
            return unmatched_regions

        # 读取模板GeoJSON文件
        geo_template_path = get_geojson_template_path()
        logger.info(f"GeoJSON模板路径: {geo_template_path}")
        logger.info(f"GeoJSON模板是否存在: {geo_template_path.exists()}")

        if not geo_template_path.exists():
            logger.error(f"GeoJSON模板文件不存在: {geo_template_path}")
            return unmatched_regions

        # 确保每个Stat对象都有必要的属性
        for location, stat in stat_map.items():
            if not hasattr(stat, "user_sex_map") or stat.user_sex_map is None:
                stat.user_sex_map = {}
                if hasattr(stat, "users") and stat.users:
                    for user_id in stat.users:
                        stat.user_sex_map[user_id] = "保密"

            if hasattr(stat, "recalculate_sex_stats"):
                stat.recalculate_sex_stats()

            if not hasattr(stat, "users") or stat.users is None:
                stat.users = set()

        # 打印统计信息
        logger.info(f"地区统计信息: {len(stat_map)} 个地区")
        for location, stat in stat_map.items():
            user_count = len(stat.users) if hasattr(stat, "users") and stat.users else 0
            logger.info(f"  {location}: {stat.location} 条评论, {user_count} 位用户")

        # 加载GeoJSON模板
        try:
            with open(geo_template_path, "r", encoding="utf-8") as f:
                geojson_data = json.load(f)
            logger.info("成功加载GeoJSON模板")
        except Exception as e:
            logger.error(f"加载GeoJSON模板失败: {e}")
            return unmatched_regions

        # 创建地区名称映射
        location_to_feature = {}  # 记录每个location匹配到的feature name
        merged_stats = {}  # 记录合并后的统计数据

        # 处理每个location进行匹配
        for location, stat in list(stat_map.items()):
            matched = False

            # 遍历所有feature寻找匹配
            for feature in geojson_data["features"]:
                feature_name = feature["properties"]["name"]
                feature_fullname = feature["properties"].get("fullname", "")

                # 简单匹配: location与name/fullname其中之一匹配
                if (
                    location == feature_name
                    or location == feature_fullname
                    or location in feature_name
                    or location in feature_fullname
                    or feature_name in location
                    or (feature_fullname and feature_fullname in location)
                ):

                    matched = True
                    location_to_feature[location] = feature_name

                    # 如果已有统计数据，合并
                    if feature_name in merged_stats:
                        existing_stat = merged_stats[feature_name]
                        existing_stat.location += stat.location
                        existing_stat.like += stat.like

                        # 合并用户集合
                        if hasattr(stat, "users") and stat.users:
                            existing_stat.users.update(stat.users)

                        # 合并等级统计
                        if hasattr(stat, "level") and hasattr(existing_stat, "level"):
                            for i in range(
                                min(len(stat.level), len(existing_stat.level))
                            ):
                                existing_stat.level[i] += stat.level[i]

                        # 合并性别统计
                        if hasattr(stat, "user_sex_map") and stat.user_sex_map:
                            for user_id, sex in stat.user_sex_map.items():
                                existing_stat.update_user_sex(user_id, sex)
                    else:
                        merged_stats[feature_name] = stat

                    break  # 找到匹配后跳出循环

            # 如果未匹配，记录
            if not matched:
                user_count = (
                    len(stat.users) if hasattr(stat, "users") and stat.users else 0
                )
                unmatched_regions[location] = {
                    "comments": stat.location,
                    "users": user_count,
                }

        # 打印匹配结果
        logger.info("地区匹配结果:")
        for location, feature_name in location_to_feature.items():
            logger.info(f"  {location} -> {feature_name}")

        # 打印未匹配地区
        if unmatched_regions:
            logger.warning(f"未匹配地区: {', '.join(unmatched_regions.keys())}")

        # 更新GeoJSON特征的属性
        for feature in geojson_data["features"]:
            province = feature["properties"]["name"]
            stat = merged_stats.get(province)

            if stat:
                user_count = (
                    len(stat.users) if hasattr(stat, "users") and stat.users else 0
                )

                logger.info(
                    f"更新地区数据: {province} -> {stat.location}条评论, {user_count}位用户"
                )
                logger.info(
                    f"性别统计: 男 {stat.sex.get('男', 0)}人, 女 {stat.sex.get('女', 0)}人, 保密 {stat.sex.get('保密', 0)}人"
                )

                # 更新Feature属性
                feature["properties"]["count"] = stat.location
                feature["properties"]["like"] = stat.like
                feature["properties"]["male"] = stat.sex.get("男", 0)
                feature["properties"]["female"] = stat.sex.get("女", 0)
                feature["properties"]["sexless"] = stat.sex.get("保密", 0)
                feature["properties"]["users"] = user_count

                # 更新等级统计
                if (
                    hasattr(stat, "level")
                    and isinstance(stat.level, list)
                    and len(stat.level) == 7
                ):
                    feature["properties"]["level0"] = stat.level[0]
                    feature["properties"]["level1"] = stat.level[1]
                    feature["properties"]["level2"] = stat.level[2]
                    feature["properties"]["level3"] = stat.level[3]
                    feature["properties"]["level4"] = stat.level[4]
                    feature["properties"]["level5"] = stat.level[5]
                    feature["properties"]["level6"] = stat.level[6]
                else:
                    # 默认值
                    feature["properties"]["level0"] = 0
                    feature["properties"]["level1"] = 0
                    feature["properties"]["level2"] = 0
                    feature["properties"]["level3"] = 0
                    feature["properties"]["level4"] = 0
                    feature["properties"]["level5"] = 0
                    feature["properties"]["level6"] = 0
            else:
                # 无数据的地区设为0
                feature["properties"]["count"] = 0
                feature["properties"]["like"] = 0
                feature["properties"]["male"] = 0
                feature["properties"]["female"] = 0
                feature["properties"]["sexless"] = 0
                feature["properties"]["level0"] = 0
                feature["properties"]["level1"] = 0
                feature["properties"]["level2"] = 0
                feature["properties"]["level3"] = 0
                feature["properties"]["level4"] = 0
                feature["properties"]["level5"] = 0
                feature["properties"]["level6"] = 0
                feature["properties"]["users"] = 0

        logger.info(f"成功匹配 {len(merged_stats)}/{len(stat_map)} 个地区")

        # 保存GeoJSON文件到输出目录
        geojson_filename = f"{filename}.geojson"
        geojson_output_path = output_path / geojson_filename
        
        try:
            logger.info(f"正在保存GeoJSON文件到: {geojson_output_path}")
            with open(geojson_output_path, "w", encoding="utf-8") as f:
                json.dump(geojson_data, f, ensure_ascii=False, indent=2)
            
            # 验证文件是否真正写入
            if geojson_output_path.exists():
                file_size = geojson_output_path.stat().st_size
                if file_size > 0:
                    logger.info(f"GeoJSON文件保存成功: {geojson_output_path} (大小: {file_size} 字节)")
                else:
                    logger.error(f"GeoJSON文件为空: {geojson_output_path}")
                    return unmatched_regions
            else:
                logger.error(f"GeoJSON文件未创建: {geojson_output_path}")
                return unmatched_regions
                
        except PermissionError as e:
            logger.error(f"没有权限写入GeoJSON文件: {e}")
            return unmatched_regions
        except Exception as e:
            logger.error(f"保存GeoJSON文件失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")
            return unmatched_regions

        # 生成HTML地图，使用相同的输出路径确保一致性
        title_for_html = video_title if video_title else filename
        html_output_path = output_path / f"{filename}.html"
        
        try:
            logger.info(f"正在生成HTML地图到: {html_output_path}")
            render_html(title_for_html, geojson_filename, str(html_output_path))
            
            # 验证HTML文件是否生成
            if html_output_path.exists():
                file_size = html_output_path.stat().st_size
                if file_size > 0:
                    logger.info(f"HTML地图生成成功: {html_output_path} (大小: {file_size} 字节)")
                else:
                    logger.error(f"HTML地图文件为空: {html_output_path}")
            else:
                logger.error(f"HTML地图文件未创建: {html_output_path}")
                
        except Exception as e:
            logger.error(f"生成HTML地图失败: {e}")
            import traceback
            logger.error(f"详细错误: {traceback.format_exc()}")

        return unmatched_regions

    except Exception as e:
        logger.error(f"生成GeoJSON文件过程中发生未预期错误: {e}")
        import traceback
        logger.error(f"详细错误堆栈: {traceback.format_exc()}")
        return unmatched_regions


def render_html(title: str, geojson_filename: str, output_path: str) -> None:
    """渲染HTML地图
    
    Args:
        title: 地图标题
        geojson_filename: GeoJSON文件名（不包含路径，HTML会从同目录加载）
        output_path: HTML输出路径
    """
    try:
        template_path = get_template_path()
        logger.info(f"HTML模板路径: {template_path}")
        logger.info(f"HTML模板是否存在: {template_path.exists()}")
        
        if not template_path.exists():
            logger.error(f"HTML模板文件不存在: {template_path}")
            raise FileNotFoundError(f"HTML模板文件不存在: {template_path}")
        
        # 读取模板内容
        try:
            with open(template_path, "r", encoding="utf-8") as f:
                template_content = f.read()
            logger.info(f"成功读取HTML模板内容，长度: {len(template_content)} 字符")
        except Exception as e:
            logger.error(f"读取HTML模板失败: {e}")
            raise
        
        # 替换模板变量
        html_content = template_content.replace("{{ .Title }}", title)
        html_content = html_content.replace("{{ .GeoJsonFile }}", geojson_filename)
        logger.info(f"模板变量替换完成，标题: {title}, GeoJSON文件: {geojson_filename}")
        
        # 保存HTML文件
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(html_content)
            logger.info(f"HTML地图模板渲染完成: {output_path}")
        except Exception as e:
            logger.error(f"写入HTML文件失败: {e}")
            raise
        
    except Exception as e:
        logger.error(f"渲染HTML地图失败: {e}")
        import traceback
        logger.error(f"详细错误: {traceback.format_exc()}")
        raise
