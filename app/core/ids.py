"""标识符生成。

数据库主键使用 UUID4；面向前端展示的问题/候选编号由业务层按任务顺序分配。
"""

from __future__ import annotations

import uuid


def new_id(prefix: str = "") -> str:
    value = uuid.uuid4().hex
    return f"{prefix}_{value}" if prefix else value
