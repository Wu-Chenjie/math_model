# -*- coding: utf-8 -*-
"""版本与发布信息。"""

from __future__ import annotations

__version__ = "1.0.0"
RELEASE_NAME = "26B 本地测试环境"
BUILD_DATE = "2026-09-10"

#: 本研究环境对标的问题
SUPPORTED_PROBLEMS = (3, 4)

#: 官方模拟器默认接口地址 (与本地环境一致, 便于直接切换)
OFFICIAL_BASE_URL = "http://127.0.0.1:2026"
OFFICIAL_PORT = 2026

#: 官方模拟器关键截止时间 (北京时间, 题目正文)
FORMAL_TEST_DEADLINE = "2026-09-13 17:30"
FORMAL_TEST_ADVICE = "2026-09-13 15:30"

BANNER = rf"""
============================================================
  {RELEASE_NAME}  v{__version__}
  2026 高教社杯 B 题 · 无线电干扰源的快速自动定位与清除
  内部演练用 · 不消耗官方正式测试机会
============================================================
""".strip("\n")
