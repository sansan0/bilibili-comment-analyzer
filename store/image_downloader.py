import logging
import threading
import csv
from pathlib import Path
from typing import List
import httpx

from models.comment import Picture
from config import Config

config = Config()

logger = logging.getLogger(__name__)


def download_image(image_url: str, output_dir: str, prefix: str) -> None:
    """下载单张图片"""
    try:
        # 确保输出目录存在
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        # 获取图片文件名
        img_name = image_url.split("/")[-1]
        output_file = output_path / f"{prefix}_{img_name}"

        # 如果文件已存在，跳过下载
        if output_file.exists():
            logger.info(f"图片已存在，跳过下载: {output_file}")
            return

        # 发送HTTP请求
        with httpx.Client() as client:
            response = client.get(
                image_url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                },
                timeout=10.0,
            )
            response.raise_for_status()

            # 保存图片
            with open(output_file, "wb") as f:
                f.write(response.content)

            logger.info(f"图片下载成功: {output_file}")

    except Exception as e:
        logger.error(f"下载图片失败 ({image_url}): {e}")


def download_images(username: str, pictures: List[Picture], output_dir: str) -> None:
    """多线程下载多张图片"""
    if not pictures:
        return

    # 创建线程池
    threads = []
    max_threads = config.get("workers", 3)

    for picture in pictures:
        # 如果线程池已满，等待一个线程完成
        while len(threads) >= max_threads:
            for t in threads[:]:
                if not t.is_alive():
                    threads.remove(t)

        # 创建并启动新线程
        thread = threading.Thread(
            target=download_image, args=(picture.img_src, output_dir, username)
        )
        thread.daemon = True
        thread.start()
        threads.append(thread)

    # 等待所有线程完成
    for thread in threads:
        thread.join()

def download_images_from_csv(csv_file_path: str) -> None:
    """从CSV文件中提取图片链接并下载图片"""
    csv_path = Path(csv_file_path)
    if not csv_path.exists():
        logger.error(f"CSV文件不存在: {csv_path}")
        return

    # 图片输出目录
    images_dir = csv_path.parent / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    downloaded_count = 0
    skipped_count = 0
    error_count = 0

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            
            # 检查必要的列是否存在
            if "pictures" not in reader.fieldnames or "upname" not in reader.fieldnames:
                logger.error("CSV文件缺少必要的列：pictures 或 upname")
                return

            for row_num, row in enumerate(reader, start=2):
                try:
                    pictures_str = row.get("pictures", "").strip()
                    username = row.get("upname", "unknown").strip()
                    
                    if not pictures_str:
                        continue
                    
                    # 解析图片URL（以分号分隔）
                    picture_urls = [url.strip() for url in pictures_str.split(";") if url.strip()]
                    
                    if not picture_urls:
                        continue
                        
                    # 为每个图片URL创建Picture对象
                    pictures = [Picture(url) for url in picture_urls]
                    
                    # 下载图片
                    for picture in pictures:
                        try:
                            # 检查图片是否已存在
                            img_name = picture.img_src.split("/")[-1]
                            output_file = images_dir / f"{username}_{img_name}"
                            
                            if output_file.exists():
                                logger.debug(f"图片已存在，跳过: {output_file.name}")
                                skipped_count += 1
                                continue
                            
                            # 下载图片
                            download_image(picture.img_src, str(images_dir), username)
                            downloaded_count += 1
                            
                        except Exception as e:
                            logger.error(f"下载图片失败 ({picture.img_src}): {e}")
                            error_count += 1
                            
                except Exception as e:
                    logger.warning(f"处理第{row_num}行时出错: {e}")
                    error_count += 1
                    continue

        logger.info(f"图片下载完成: 新下载 {downloaded_count} 张，跳过 {skipped_count} 张，失败 {error_count} 张")
        
    except Exception as e:
        logger.error(f"从CSV文件下载图片时出错: {e}")