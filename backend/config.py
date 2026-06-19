"""
配置管理模块
从 config.json 读取配置
"""
import os
import json
from typing import Dict, Any
from backend.paths import get_app_dir


class Config:
    """配置管理类"""

    # 用户配置默认值
    DEFAULT_USER_CONFIG = {
        "inputPath": "",
        "outputPath": "",
        "repkgPath": "./static/assets/RePKG.exe",
        "options": {
            "convertTex": True,
            "copyProject": True,
            "overwrite": False,
            "recursive": True,
            "copyPreview": True
        },
        "appearance": {
            "backgroundImage": "",
            "backgroundOpacity": 0.15,
            "backgroundBlur": 0
        }
    }

    # Steam 检测到的路径（不持久化）
    DEFAULT_STEAM_CONFIG = {
        "inputPath": "",
        "outputPath": ""
    }

    def __init__(self, config_file: str = None):
        if config_file is None:
            config_file = os.path.join(get_app_dir(), 'config.json')
        self.config_file = config_file
        self.steam_config = self.DEFAULT_STEAM_CONFIG.copy()
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """加载配置文件，只加载用户配置"""
        default = {"user": self.DEFAULT_USER_CONFIG.copy()}
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    return self._merge_config(default, loaded)
            except (json.JSONDecodeError, IOError):
                pass
        return default

    def save(self) -> bool:
        """保存配置到文件"""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            return True
        except IOError:
            return False

    @staticmethod
    def _merge_config(default: Dict, loaded: Dict) -> Dict:
        """深度合并配置"""
        result = default.copy()
        for key, value in loaded.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = Config._merge_config(result[key], value)
            else:
                result[key] = value
        return result

    def get_full_config(self) -> Dict[str, Any]:
        """获取完整配置（用户配置 + Steam 配置）"""
        return {
            "user": self.config.get("user", self.DEFAULT_USER_CONFIG.copy()),
            "steam": self.steam_config
        }

    def update_steam_config(self, steam_data: Dict[str, Any]):
        """更新 Steam 检测到的路径"""
        self.steam_config = {
            "inputPath": steam_data.get("workshop_path", ""),
            "outputPath": steam_data.get("wallpaper_projects_my", "")
        }


# 全局配置实例
_config: 'Config' = None


def get_config() -> Config:
    """获取全局配置实例"""
    global _config
    if _config is None:
        _config = Config()
    return _config


def save_config(data: Dict) -> tuple:
    """保存用户配置"""
    config = get_config()
    user_data = data.get("user", data)
    config.config["user"] = Config._merge_config(config.DEFAULT_USER_CONFIG, user_data)
    if config.save():
        return True, None
    return False, "保存失败"


def update_steam(data: Dict) -> tuple:
    """更新 Steam 检测路径"""
    config = get_config()
    config.update_steam_config(data)
    return True, None
