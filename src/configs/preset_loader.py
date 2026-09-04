import json
import os
from typing import Any, Dict, List

from src.configs.app_config import BASE_DIR

PRESETS_DIR = os.path.join(BASE_DIR, "src", "configs", "presets")


def load_preset_api_configs() -> List[Dict[str, Any]]:
    """读取预置的聚合 API 配置列表。"""
    path = os.path.join(PRESETS_DIR, "api_configs_preset.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def load_preset_tg_channels() -> List[Dict[str, Any]]:
    """读取预置的 Telegram 频道及标题元数据。"""
    path = os.path.join(PRESETS_DIR, "tg_channels_preset.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def load_preset_plugin_settings() -> Dict[str, bool]:
    """读取预置的第三方插件启禁用状态。"""
    path = os.path.join(PRESETS_DIR, "plugin_settings_preset.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}
