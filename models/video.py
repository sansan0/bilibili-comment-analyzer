from dataclasses import dataclass


@dataclass
class Video:
    """视频信息"""

    aid: int  # AV号
    bvid: str  # BV号
    title: str  # 标题
    mid: int  # UP主ID
    author: str  # UP主名称
    pic: str  # 封面图
    description: str  # 描述
    created: int  # 发布时间
    comment: int  # 评论数
    play: int  # 播放数

    @classmethod
    def from_api_response(cls, item: dict) -> "Video":
        """从API响应创建Video对象"""
        return cls(
            aid=item.get("aid", 0),
            bvid=item.get("bvid", ""),
            title=item.get("title", ""),
            mid=item.get("mid", 0),
            author=item.get("author", ""),
            pic=item.get("pic", ""),
            description=item.get("description", ""),
            created=item.get("created", 0),
            comment=item.get("comment", 0),
            play=item.get("play", 0),
        )
