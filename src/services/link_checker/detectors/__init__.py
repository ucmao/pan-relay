# src/services/link_checker/detectors/__init__.py

from typing import List
from ..base import BaseDetector
from .quark import QuarkDetector
from .baidu import BaiduDetector
from .aliyun import AliyunDetector
from .uc import UCDetector
from .xunlei import XunleiDetector
from .pan123 import Pan123Detector
from .tianyi import TianyiDetector
from .pan115 import Pan115Detector
from .cmcc import CMCCDetector
from .unicom import UnicomDetector
from .wukong import WukongDetector
from .guangya import GuangyaDetector

ALL_DETECTORS: List[BaseDetector] = [
    QuarkDetector(),
    BaiduDetector(),
    AliyunDetector(),
    UCDetector(),
    XunleiDetector(),
    Pan123Detector(),
    TianyiDetector(),
    Pan115Detector(),
    CMCCDetector(),
    UnicomDetector(),
    WukongDetector(),
    GuangyaDetector(),
]

__all__ = [
    "ALL_DETECTORS",
    "QuarkDetector",
    "BaiduDetector",
    "AliyunDetector",
    "UCDetector",
    "XunleiDetector",
    "Pan123Detector",
    "TianyiDetector",
    "Pan115Detector",
    "CMCCDetector",
    "UnicomDetector",
    "WukongDetector",
    "GuangyaDetector",
]

