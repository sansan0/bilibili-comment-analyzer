from dataclasses import dataclass, field
from typing import List, Dict, Any


@dataclass
class Picture:
    """图片数据"""

    img_src: str


@dataclass
class Comment:
    """评论数据"""

    uname: str = ""  # 用户名
    sex: str = ""  # 性别
    content: str = ""  # 评论内容
    rpid: int = 0  # 评论ID
    oid: int = 0  # 评论区ID
    bvid: str = ""  # 视频BV号
    mid: int = 0  # 发送者ID
    parent: int = 0  # 父评论ID
    fansgrade: int = 0  # 是否粉丝
    ctime: int = 0  # 评论时间戳
    like: int = 0  # 点赞数
    following: bool = False  # 是否关注
    current_level: int = 0  # 当前等级
    location: str = ""  # 位置
    pictures: List[Picture] = field(default_factory=list)  # 图片列表

    @classmethod
    def from_api_response(cls, item: Dict[str, Any]) -> "Comment":
        """从API响应创建Comment对象"""
        pictures = []
        if "content" in item and "pictures" in item["content"]:
            pictures = [Picture(p["img_src"]) for p in item["content"]["pictures"]]

        return cls(
            uname=item.get("member", {}).get("uname", ""),
            sex=item.get("member", {}).get("sex", ""),
            content=item.get("content", {}).get("message", ""),
            rpid=item.get("rpid", 0),
            oid=item.get("oid", 0),
            bvid="",  # 需要在外部设置
            mid=item.get("mid", 0),
            parent=item.get("parent", 0),
            fansgrade=item.get("fansgrade", 0),
            ctime=item.get("ctime", 0),
            like=item.get("like", 0),
            following=item.get("reply_control", {}).get("following", False),
            current_level=item.get("member", {})
            .get("level_info", {})
            .get("current_level", 0),
            location=item.get("reply_control", {})
            .get("location", "")
            .replace("IP属地：", ""),
            pictures=pictures,
        )


@dataclass
class Stat:
    """统计信息"""

    name: str
    location: int = 0
    sex: Dict[str, int] = field(default_factory=lambda: {"男": 0, "女": 0, "保密": 0})
    level: List[int] = field(default_factory=lambda: [0, 0, 0, 0, 0, 0, 0])
    like: int = 0
    users: set = field(default_factory=set)  # 存储用户ID的集合
    user_sex_map: Dict[str, str] = field(default_factory=dict)  # 存储用户ID到性别的映射

    def __post_init__(self):
        """初始化后确保数据类型正确"""
        # 确保users是集合
        if not isinstance(self.users, set):
            self.users = set(self.users) if self.users else set()

        # 确保user_sex_map是字典
        if not isinstance(self.user_sex_map, dict):
            self.user_sex_map = dict(self.user_sex_map) if self.user_sex_map else {}

    @property
    def user_count(self) -> int:
        """获取不同用户的数量"""
        return len(self.users)

    def update_user_sex(self, user_id: str, sex: str) -> None:
        """更新用户性别信息"""
        # 确保性别值有效
        if sex not in ["男", "女", "保密"]:
            sex = "保密"

        # 如果用户已在性别映射中，则先减去之前统计的性别计数
        if user_id in self.user_sex_map:
            old_sex = self.user_sex_map[user_id]
            if old_sex in self.sex:
                self.sex[old_sex] -= 1

        # 更新用户性别映射和计数
        self.user_sex_map[user_id] = sex
        if sex in self.sex:
            self.sex[sex] += 1

    def recalculate_sex_stats(self) -> None:
        """重新计算性别统计信息"""
        # 重置性别统计
        self.sex = {"男": 0, "女": 0, "保密": 0}

        # 根据用户性别映射重新计算
        for user_id, sex in self.user_sex_map.items():
            if sex in self.sex:
                self.sex[sex] += 1

    def to_dict(self) -> Dict[str, Any]:
        """将Stat对象转换为字典，便于序列化"""
        return {
            "name": self.name,
            "location": self.location,
            "sex": self.sex,
            "level": self.level,
            "like": self.like,
            "users": len(self.users),  # 只保存用户数量
            "user_sex_map": self.user_sex_map,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Stat":
        """从字典创建Stat对象，用于反序列化"""
        stat = cls(
            name=data.get("name", ""),
            location=data.get("location", 0),
            like=data.get("like", 0),
        )

        # 加载性别统计
        sex_data = data.get("sex", {})
        if isinstance(sex_data, dict):
            stat.sex = {
                "男": sex_data.get("男", 0),
                "女": sex_data.get("女", 0),
                "保密": sex_data.get("保密", 0),
            }

        # 加载等级统计
        level_data = data.get("level", [])
        if isinstance(level_data, list) and len(level_data) == 7:
            stat.level = level_data

        # 加载用户性别映射
        user_sex_map = data.get("user_sex_map", {})
        if isinstance(user_sex_map, dict):
            stat.user_sex_map = user_sex_map

            # 重建用户集合
            stat.users = set(user_sex_map.keys())

            # 重新计算性别统计
            stat.recalculate_sex_stats()

        return stat
