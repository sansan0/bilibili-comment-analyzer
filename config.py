import json
from pathlib import Path
from typing import Dict, Any

# 基础目录配置
BASE_DIR = Path.home() / ".BiCoDown"
LOG_DIR = BASE_DIR / "logs"
CONFIG_FILE = BASE_DIR / "config.json"

# 默认配置
DEFAULT_CONFIG = {
    "cookie": "",
    "output": str(BASE_DIR / "output"),
    "mapping": True,
    "workers": 3,
    "corder": 1,  # 评论排序方式，0：按时间，1：按点赞数，2：按回复数
    "vorder": "pubdate",  # 视频排序方式，最新发布：pubdate最多播放：click最多收藏：stow
    "request_delay_min": 1.0,  # 最小请求延迟（秒）
    "request_delay_max": 2.0,  # 最大请求延迟（秒）
    "request_retry_delay": 5.0,  # 请求失败重试等待时间（秒）
    "max_retries": 2,  # 统一的最大重试次数
    "consecutive_empty_limit": 1,  # 连续空页面的限制数，超过此数认为评论已获取完毕
    "download_images": False,  # 是否在下载评论时自动下载图片
    "log_level": "INFO",  # 日志级别：DEBUG, INFO, WARNING, ERROR, CRITICAL
    "max_log_files": 10,  # 保留的最大日志文件数量
}


class Config:
    """配置管理类"""

    _instance = None
    _config: Dict[str, Any] = {}

    def __new__(cls):
        """单例模式"""
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    def _load_config(self):
        """加载配置"""
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    self._config = json.load(f)

                    # 检查是否有新增的配置项，如果没有则使用默认值
                    for key, value in DEFAULT_CONFIG.items():
                        if key not in self._config:
                            self._config[key] = value

                    # 处理旧版本配置的兼容性
                    if (
                        "request_max_retries" in self._config
                        or "empty_page_max_retries" in self._config
                    ):
                        # 取两者中的较大值作为新的统一重试次数
                        old_request_retries = self._config.get("request_max_retries", 3)
                        old_empty_retries = self._config.get(
                            "empty_page_max_retries", 3
                        )
                        self._config["max_retries"] = max(
                            old_request_retries, old_empty_retries
                        )

                        # 移除旧的配置项
                        self._config.pop("request_max_retries", None)
                        self._config.pop("empty_page_max_retries", None)

                        # 保存更新后的配置
                        self._save_config()

            except Exception as e:
                print(f"加载配置文件失败: {e}")
                self._config = DEFAULT_CONFIG.copy()
        else:
            self._config = DEFAULT_CONFIG.copy()
            self._save_config()

    def _save_config(self):
        """保存配置"""
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(CONFIG_FILE, "w", encoding="utf-8") as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"保存配置文件失败: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """获取配置项"""
        return self._config.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """设置配置项"""
        self._config[key] = value
        self._save_config()

    def get_all(self) -> Dict[str, Any]:
        """获取所有配置"""
        return self._config.copy()
