import csv
import logging
from pathlib import Path
from typing import List

from models.comment import Comment
from store.image_downloader import download_images

logger = logging.getLogger(__name__)


def comment_to_record(comment: Comment) -> List[str]:
    """将评论对象转换为CSV记录"""
    pic_urls = ";".join(pic.img_src for pic in comment.pictures)

    return [
        comment.bvid,  # BV号
        comment.uname,  # 用户名
        comment.sex,  # 性别
        comment.content,  # 评论内容
        pic_urls,  # 图片URL
        str(comment.rpid),  # 评论ID
        str(comment.oid),  # 评论区ID
        str(comment.mid),  # 发送者ID
        str(comment.parent),  # 父评论ID
        str(comment.fansgrade),  # 是否粉丝
        str(comment.ctime),  # 评论时间戳
        str(comment.like),  # 点赞数
        str(comment.following),  # 是否关注
        str(comment.current_level),  # 当前等级
        comment.location,  # 位置
    ]


def save_to_csv(
    filename: str, comments: List[Comment], output_dir: str, title: str = None, overwrite: bool = False
) -> None:
    """保存评论到CSV文件

    Args:
        filename: BV号
        comments: 评论列表
        output_dir: 输出目录
        title: 视频标题，如果提供则用于日志显示
        overwrite: 是否覆盖现有文件，True时会清空现有数据重新写入
    """
    if not comments:
        return

    # 获取配置以决定是否下载图片
    from config import Config
    config = Config()
    should_download_images = config.get("download_images", False)

    # 确保输出目录存在
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # CSV文件路径
    csv_path = output_path / f"{filename}.csv"

    # 用于日志显示的名称
    display_name = f"{filename} ({title})" if title else filename

    # 判断是否需要创建新文件或覆盖
    create_new_file = not csv_path.exists() or overwrite
    
    if create_new_file:
        # 创建新文件或覆盖现有文件
        try:
            with open(csv_path, "w", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)

                # 写入表头
                headers = [
                    "bvid",
                    "upname", 
                    "sex",
                    "content",
                    "pictures",
                    "rpid",
                    "oid",
                    "mid",
                    "parent",
                    "fans_grade",
                    "ctime",
                    "like",
                    "following",
                    "level",
                    "location",
                ]
                writer.writerow(headers)

                # 写入评论
                valid_comments = 0
                downloaded_images = 0
                for comment in comments:
                    if not comment.uname:
                        continue

                    # 根据配置决定是否下载图片
                    if should_download_images and comment.pictures:
                        download_images(
                            comment.uname, comment.pictures, str(output_path / "images")
                        )
                        downloaded_images += len(comment.pictures)

                    # 写入评论
                    record = comment_to_record(comment)
                    writer.writerow(record)
                    valid_comments += 1

            action = "覆盖写入" if overwrite else "创建并写入"
            logger.info(f"成功{action} {valid_comments} 条评论到 {display_name}")
            
            if should_download_images and downloaded_images > 0:
                logger.info(f"已下载 {downloaded_images} 张图片")
            elif not should_download_images:
                logger.info("已跳过图片下载（可在设置中启用或使用【获取图片】按钮）")

        except Exception as e:
            logger.error(f"{'覆盖' if overwrite else '创建'}CSV文件失败: {e}")
    else:
        # 追加到现有文件
        try:
            with open(csv_path, "a", newline="", encoding="utf-8") as file:
                writer = csv.writer(file)

                valid_comments = 0
                downloaded_images = 0
                for comment in comments:
                    if not comment.uname:
                        continue

                    # 根据配置决定是否下载图片
                    if should_download_images and comment.pictures:
                        download_images(
                            comment.uname, comment.pictures, str(output_path / "images")
                        )
                        downloaded_images += len(comment.pictures)

                    # 写入评论
                    record = comment_to_record(comment)
                    writer.writerow(record)
                    valid_comments += 1

            logger.info(f"成功追加 {valid_comments} 条评论到 {display_name}")
            
            if should_download_images and downloaded_images > 0:
                logger.info(f"已下载 {downloaded_images} 张图片")
            elif not should_download_images:
                logger.info("已跳过图片下载（可在设置中启用或使用【获取图片】按钮）")

        except Exception as e:
            logger.error(f"追加CSV文件失败: {e}")
