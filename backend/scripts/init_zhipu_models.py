"""智谱模型配置初始化脚本"""

import asyncio
import sys
import os
import uuid
from datetime import datetime, timezone

# 添加项目根目录到 Python 路径
sys.path.insert(0, '/app')

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_write_session
from app.models.model_config import ModelConfig


async def init_zhipu_models():
    """初始化智谱模型配置"""
    async with get_write_session() as session:
        # 检查是否已存在智谱模型
        existing = await session.execute(
            select(ModelConfig).where(ModelConfig.provider == "zhipu")
        )
        if existing.scalars().all():
            print("智谱模型已存在，跳过初始化")
            return

        # 智谱模型配置列表
        zhipu_models = [
            {
                "name": "glm-4-plus",
                "display_name": "智谱 GLM-4 Plus",
                "description": "智谱最强通用大模型，支持复杂推理和长文本",
                "model_type": "generation",
                "provider": "zhipu",
                "model_id": "glm-4-plus",
                "temperature": 0.1,
                "top_p": 0.8,
                "max_tokens": 8192,
                "context_window": 128000,
                "supports_function_calling": True,
                "supports_streaming": True,
                "timeout_seconds": 120,
                "max_retries": 3,
                "max_concurrent_requests": 50,
                "requests_per_minute": 600,
                "api_endpoint": "https://open.bigmodel.cn/api/coding/paas/v4",
                "api_key_encrypted": "0a78f4761b674c51a4e91e5dd210a73d.mwbkM8IwMct7Yukl",
                "is_active": True,
                "is_default": True,
            },
            {
                "name": "glm-4",
                "display_name": "智谱 GLM-4",
                "description": "智谱通用大模型，平衡性能与成本",
                "model_type": "generation",
                "provider": "zhipu",
                "model_id": "glm-4",
                "temperature": 0.1,
                "top_p": 0.8,
                "max_tokens": 8192,
                "context_window": 128000,
                "supports_function_calling": True,
                "supports_streaming": True,
                "timeout_seconds": 120,
                "max_retries": 3,
                "max_concurrent_requests": 50,
                "requests_per_minute": 600,
                "api_endpoint": "https://open.bigmodel.cn/api/coding/paas/v4",
                "api_key_encrypted": "0a78f4761b674c51a4e91e5dd210a73d.mwbkM8IwMct7Yukl",
                "is_active": True,
                "is_default": False,
            },
            {
                "name": "glm-4-air",
                "display_name": "智谱 GLM-4 Air",
                "description": "智谱轻量级大模型，快速响应",
                "model_type": "generation",
                "provider": "zhipu",
                "model_id": "glm-4-air",
                "temperature": 0.1,
                "top_p": 0.8,
                "max_tokens": 8192,
                "context_window": 128000,
                "supports_function_calling": True,
                "supports_streaming": True,
                "timeout_seconds": 120,
                "max_retries": 3,
                "max_concurrent_requests": 100,
                "requests_per_minute": 1000,
                "api_endpoint": "https://open.bigmodel.cn/api/coding/paas/v4",
                "api_key_encrypted": "0a78f4761b674c51a4e91e5dd210a73d.mwbkM8IwMct7Yukl",
                "is_active": True,
                "is_default": False,
            },
            {
                "name": "glm-4-flash",
                "display_name": "智谱 GLM-4 Flash",
                "description": "智谱极速大模型，超低延迟",
                "model_type": "generation",
                "provider": "zhipu",
                "model_id": "glm-4-flash",
                "temperature": 0.1,
                "top_p": 0.8,
                "max_tokens": 8192,
                "context_window": 128000,
                "supports_function_calling": True,
                "supports_streaming": True,
                "timeout_seconds": 60,
                "max_retries": 3,
                "max_concurrent_requests": 200,
                "requests_per_minute": 2000,
                "api_endpoint": "https://open.bigmodel.cn/api/coding/paas/v4",
                "api_key_encrypted": "0a78f4761b674c51a4e91e5dd210a73d.mwbkM8IwMct7Yukl",
                "is_active": True,
                "is_default": False,
            },
            {
                "name": "glm-4-long",
                "display_name": "智谱 GLM-4 Long",
                "description": "智谱长文本大模型，支持超长上下文",
                "model_type": "generation",
                "provider": "zhipu",
                "model_id": "glm-4-long",
                "temperature": 0.1,
                "top_p": 0.8,
                "max_tokens": 8192,
                "context_window": 1000000,
                "supports_function_calling": True,
                "supports_streaming": True,
                "timeout_seconds": 300,
                "max_retries": 3,
                "max_concurrent_requests": 20,
                "requests_per_minute": 200,
                "api_endpoint": "https://open.bigmodel.cn/api/coding/paas/v4",
                "api_key_encrypted": "0a78f4761b674c51a4e91e5dd210a73d.mwbkM8IwMct7Yukl",
                "is_active": True,
                "is_default": False,
            },
            {
                "name": "embedding-3",
                "display_name": "智谱 Embedding-3",
                "description": "智谱文本嵌入模型，用于语义检索",
                "model_type": "embedding",
                "provider": "zhipu",
                "model_id": "embedding-3",
                "temperature": 0.0,
                "top_p": 1.0,
                "max_tokens": 8192,
                "context_window": 8192,
                "supports_function_calling": False,
                "supports_streaming": False,
                "timeout_seconds": 60,
                "max_retries": 3,
                "max_concurrent_requests": 100,
                "requests_per_minute": 1000,
                "api_endpoint": "https://open.bigmodel.cn/api/coding/paas/v4",
                "api_key_encrypted": "0a78f4761b674c51a4e91e5dd210a73d.mwbkM8IwMct7Yukl",
                "is_active": True,
                "is_default": True,
            },
        ]

        # 插入模型配置
        for model_data in zhipu_models:
            model = ModelConfig(
                tenant_id="default",
                **model_data,
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            session.add(model)
            print(f"添加模型: {model.display_name}")

        await session.commit()
        print(f"成功添加 {len(zhipu_models)} 个智谱模型配置")


if __name__ == "__main__":
    asyncio.run(init_zhipu_models())