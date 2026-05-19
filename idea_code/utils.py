"""共享工具函数。"""

import re


def slugify(seed: str, max_len: int = 50) -> str:
    """从种子文本生成项目 slug。"""
    s = re.sub(r'[^\w\s-]', '', seed.lower())
    s = re.sub(r'[-\s]+', '-', s).strip('-')
    return s[:max_len] if s else 'untitled'
