"""
工具模块
提供通用的辅助功能
"""

from .assets_helper import (
    get_template_path,
    get_geojson_template_path, 
    get_wordcloud_template_path,
    get_stopwords_path,
    get_weixin_image_path,
    get_pkuseg_model_path
)

__all__ = [
    'get_template_path',
    'get_geojson_template_path',
    'get_wordcloud_template_path', 
    'get_stopwords_path',
    'get_weixin_image_path',
    'get_pkuseg_model_path'
]