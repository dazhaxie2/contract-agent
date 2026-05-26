"""评估测试集结构质量门禁：CI 中拦截结构错误或重复 ID 的新增用例。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from scripts.validate_evaluation_set import validate_test_set


@pytest.mark.asyncio
async def test_evaluation_set_passes_schema(app_client: AsyncClient) -> None:
    # 依赖 app_client 仅为触发 conftest 的 DB schema 初始化（autouse 清理 fixture 需要建表）。
    errors = validate_test_set()
    assert errors == [], "评估测试集校验失败：\n" + "\n".join(errors)
