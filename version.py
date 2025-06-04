"""
版本信息管理模块
统一管理应用程序的版本号和相关信息
"""

__version__ = "1.0.0"
__app_name__ = "哔哩哔哩评论观察者"
__app_name_en__ = "BiliBili Comment Analyzer"
__author__ = "sansan"
__description__ = "专业的B站评论数据分析下载器"
__author_url__ = "https://github.com/sansan0"
__repository__ = "https://github.com/sansan0/biliBili-comment-analyzer"


def get_version():
    """获取版本号"""
    return __version__


def get_app_name():
    """获取应用名称（中文）"""
    return __app_name__


def get_app_name_en():
    """获取应用名称（英文）"""
    return __app_name_en__


def get_author():
    """获取作者名称"""
    return __author__


def get_author_url():
    """获取作者链接"""
    return __author_url__


def get_description():
    """获取应用描述"""
    return __description__


def get_repository():
    """获取仓库地址"""
    return __repository__


def get_full_version_info():
    """获取完整版本信息"""
    return {
        "version": __version__,
        "app_name": __app_name__,
        "app_name_en": __app_name_en__,
        "author": __author__,
        "description": __description__,
        "author_url": __author_url__,
        "repository": __repository__,
    }


def get_version_display():
    """获取用于显示的版本字符串"""
    return f"v{__version__}"