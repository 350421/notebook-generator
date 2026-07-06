"""文字内容获取与 OCR 模块。

当前仅提供接口框架，暂不实现网络抓取和图片文字识别逻辑。
"""

from pathlib import Path


def fetch_text_from_url(url: str) -> str:
    """从网页地址获取待处理文字。"""
    pass


def recognize_text(image_path: str | Path, engine: str = "paddleocr") -> str:
    """使用指定 OCR 引擎识别本地图片中的文字。"""
    pass
