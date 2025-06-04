import sys
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

_base_dir_cache = None
_is_frozen = getattr(sys, "frozen", False)


def _get_base_dir():
    """获取资源文件基础目录"""
    global _base_dir_cache

    if _base_dir_cache is None:
        if _is_frozen:
            if hasattr(sys, "_MEIPASS"):
                base_dir = Path(sys._MEIPASS)
                logger.info("检测到PyInstaller环境")
            else:
                base_dir = Path(sys.executable).parent
                logger.info("检测到cx_Freeze环境")
            logger.info(f"打包环境基础目录: {base_dir}")
        else:
            current_file = Path(__file__)
            project_root = current_file.parent.parent
            base_dir = project_root / "assets"
            logger.info(f"开发环境基础目录: {base_dir}")

        _base_dir_cache = base_dir

    return _base_dir_cache


def _get_resource_path(filename):
    """获取资源文件路径"""
    base_dir = _get_base_dir()
    resource_path = base_dir / filename

    if not resource_path.exists():
        logger.warning(f"资源文件不存在: {resource_path}")

    return resource_path


def get_template_path():
    """获取模板文件路径"""
    return _get_resource_path("map_template.html")


def get_geojson_template_path():
    """获取地理JSON模板文件路径"""
    return _get_resource_path("china-provinces.geojson")


def get_wordcloud_template_path():
    """获取词云模板文件路径"""
    return _get_resource_path("wordcloud_template.html")


def get_stopwords_path():
    """获取停用词文件路径"""
    return _get_resource_path("stopwords.txt")


def get_weixin_image_path():
    """获取微信图片路径"""
    return _get_resource_path("weixin.png")


def get_pkuseg_model_path():
    """获取pkuseg模型路径"""
    if _is_frozen:
        return _get_resource_path("web")
    else:
        return _get_resource_path("pkuseg/web")


def get_icon_path():
    """获取图标文件路径"""
    return _get_resource_path("icon.ico")
