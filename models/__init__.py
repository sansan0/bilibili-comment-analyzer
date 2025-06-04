"""
数据模型模块
定义评论和视频的数据结构
"""

from .comment import Comment, Stat, Picture
from .video import Video

__all__ = ['Comment', 'Stat', 'Picture', 'Video']