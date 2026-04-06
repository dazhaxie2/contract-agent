"""
全局配置中心 - 合同合规Agent系统
支持多环境配置、阿里云大模型、多数据库、消息队列、监控等全链路配置
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """关系型数据库配置 (PostgreSQL/TiDB)"""
    host: str = Field(default="localhost", alias="DB_HOST")
    port: int = Field(default=5432, alias="DB_PORT")
    user: str = Field(default="contract_agent", alias="DB_USER")
    password: str = Field(default="", alias="DB_PASSWORD")
    name: str = Field(default="contract_agent", alias="DB_NAME")
    pool_size: int = Field(default=20, alias="DB_POOL_SIZE")
    max_overflow: int = Field(default=40, alias="DB_MAX_OVERFLOW")
    pool_timeout: int = Field(default=30, alias="DB_POOL_TIMEOUT")
    pool_recycle: int = Field(default=1800, alias="DB_POOL_RECYCLE")
    echo: bool = Field(default=False, alias="DB_ECHO")

    # 读写分离
    read_host: Optional[str] = Field(default=None, alias="DB_READ_HOST")
    read_port: int = Field(default=5432, alias="DB_READ_PORT")

    @property
    def write_url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.name}"

    @property
    def read_url(self) -> str:
        host = self.read_host or self.host
        port = self.read_port or self.port
        return f"postgresql+asyncpg://{self.user}:{self.password}@{host}:{port}/{self.name}"

    model_config = {"env_prefix": "DB_", "extra": "ignore"}


class RedisSettings(BaseSettings):
    """Redis集群配置"""
    host: str = Field(default="localhost", alias="REDIS_HOST")
    port: int = Field(default=6379, alias="REDIS_PORT")
    password: str = Field(default="", alias="REDIS_PASSWORD")
    db: int = Field(default=0, alias="REDIS_DB")
    max_connections: int = Field(default=100, alias="REDIS_MAX_CONNECTIONS")
    socket_timeout: int = Field(default=5, alias="REDIS_SOCKET_TIMEOUT")
    decode_responses: bool = True

    # 缓存分区
    cache_db: int = Field(default=1, alias="REDIS_CACHE_DB")
    session_db: int = Field(default=2, alias="REDIS_SESSION_DB")
    rate_limit_db: int = Field(default=3, alias="REDIS_RATE_LIMIT_DB")
    celery_db: int = Field(default=4, alias="REDIS_CELERY_DB")

    @property
    def url(self) -> str:
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"

    model_config = {"env_prefix": "REDIS_", "extra": "ignore"}


class MilvusSettings(BaseSettings):
    """Milvus向量数据库配置"""
    host: str = Field(default="localhost", alias="MILVUS_HOST")
    port: int = Field(default=19530, alias="MILVUS_PORT")
    user: str = Field(default="", alias="MILVUS_USER")
    password: str = Field(default="", alias="MILVUS_PASSWORD")
    collection_name: str = Field(default="contract_chunks", alias="MILVUS_COLLECTION")
    dimension: int = Field(default=1024, alias="MILVUS_DIMENSION")
    index_type: str = Field(default="HNSW", alias="MILVUS_INDEX_TYPE")
    metric_type: str = Field(default="COSINE", alias="MILVUS_METRIC_TYPE")
    # HNSW参数
    hnsw_m: int = Field(default=16, alias="MILVUS_HNSW_M")
    hnsw_ef_construction: int = Field(default=200, alias="MILVUS_HNSW_EF_CONSTRUCTION")
    hnsw_ef_search: int = Field(default=64, alias="MILVUS_HNSW_EF_SEARCH")
    # 分区策略
    partition_by_doc_type: bool = Field(default=True, alias="MILVUS_PARTITION_BY_DOC_TYPE")

    model_config = {"env_prefix": "MILVUS_", "extra": "ignore"}


class NebulaSettings(BaseSettings):
    """NebulaGraph知识图谱配置"""
    host: str = Field(default="localhost", alias="NEBULA_HOST")
    port: int = Field(default=9669, alias="NEBULA_PORT")
    user: str = Field(default="root", alias="NEBULA_USER")
    password: str = Field(default="nebula", alias="NEBULA_PASSWORD")
    space: str = Field(default="contract_graph", alias="NEBULA_SPACE")
    max_connection_pool_size: int = Field(default=50, alias="NEBULA_POOL_SIZE")

    model_config = {"env_prefix": "NEBULA_", "extra": "ignore"}


class MinioSettings(BaseSettings):
    """MinIO文件存储配置"""
    endpoint: str = Field(default="localhost:9000", alias="MINIO_ENDPOINT")
    access_key: str = Field(default="minioadmin", alias="MINIO_ACCESS_KEY")
    secret_key: str = Field(default="minioadmin", alias="MINIO_SECRET_KEY")
    bucket: str = Field(default="contract-documents", alias="MINIO_BUCKET")
    secure: bool = Field(default=False, alias="MINIO_SECURE")

    model_config = {"env_prefix": "MINIO_", "extra": "ignore"}


class KafkaSettings(BaseSettings):
    """Kafka消息队列配置"""
    bootstrap_servers: str = Field(default="localhost:9092", alias="KAFKA_BOOTSTRAP_SERVERS")
    group_id: str = Field(default="contract-agent-group", alias="KAFKA_GROUP_ID")
    # Topic定义
    topic_document_upload: str = "contract.document.upload"
    topic_document_process: str = "contract.document.process"
    topic_vector_generate: str = "contract.vector.generate"
    topic_graph_build: str = "contract.graph.build"
    topic_dead_letter: str = "contract.dead-letter"
    # 消费者配置
    max_poll_records: int = Field(default=100, alias="KAFKA_MAX_POLL_RECORDS")
    session_timeout_ms: int = Field(default=30000, alias="KAFKA_SESSION_TIMEOUT")
    auto_offset_reset: str = "earliest"

    model_config = {"env_prefix": "KAFKA_", "extra": "ignore"}


class AliyunLLMSettings(BaseSettings):
    """阿里云大模型配置"""
    api_key: str = Field(default="", alias="DASHSCOPE_API_KEY")
    # 核心生成模型
    generation_model: str = Field(default="qwen-max", alias="LLM_GENERATION_MODEL")
    generation_temperature: float = Field(default=0.1, alias="LLM_GENERATION_TEMPERATURE")
    generation_top_p: float = Field(default=0.8, alias="LLM_GENERATION_TOP_P")
    generation_max_tokens: int = Field(default=8192, alias="LLM_GENERATION_MAX_TOKENS")
    # 轻量小模型(预处理)
    light_model: str = Field(default="qwen-plus", alias="LLM_LIGHT_MODEL")
    light_temperature: float = Field(default=0.1, alias="LLM_LIGHT_TEMPERATURE")
    light_max_tokens: int = Field(default=4096, alias="LLM_LIGHT_MAX_TOKENS")
    # 嵌入模型
    embedding_model: str = Field(default="text-embedding-v3", alias="LLM_EMBEDDING_MODEL")
    embedding_dimension: int = Field(default=1024, alias="LLM_EMBEDDING_DIMENSION")
    # 重排模型
    reranker_model: str = Field(default="gte-rerank", alias="LLM_RERANKER_MODEL")
    # 并发与限流
    max_concurrent_requests: int = Field(default=50, alias="LLM_MAX_CONCURRENT")
    requests_per_minute: int = Field(default=600, alias="LLM_RPM")
    tokens_per_minute: int = Field(default=1000000, alias="LLM_TPM")
    # 重试
    max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")
    retry_delay: float = Field(default=1.0, alias="LLM_RETRY_DELAY")
    timeout: int = Field(default=120, alias="LLM_TIMEOUT")

    model_config = {"env_prefix": "LLM_", "extra": "ignore"}


class TracingSettings(BaseSettings):
    """OpenTelemetry链路追踪配置"""
    enabled: bool = Field(default=True, alias="TRACING_ENABLED")
    service_name: str = Field(default="contract-agent", alias="TRACING_SERVICE_NAME")
    otlp_endpoint: str = Field(default="http://localhost:4317", alias="OTLP_ENDPOINT")
    jaeger_endpoint: str = Field(default="http://localhost:14268/api/traces", alias="JAEGER_ENDPOINT")
    sample_rate: float = Field(default=1.0, alias="TRACING_SAMPLE_RATE")
    log_correlation: bool = Field(default=True, alias="TRACING_LOG_CORRELATION")

    model_config = {"env_prefix": "TRACING_", "extra": "ignore"}


class PrometheusSettings(BaseSettings):
    """Prometheus指标配置"""
    enabled: bool = Field(default=True, alias="PROMETHEUS_ENABLED")
    port: int = Field(default=9090, alias="PROMETHEUS_PORT")
    path: str = Field(default="/metrics", alias="PROMETHEUS_PATH")

    model_config = {"env_prefix": "PROMETHEUS_", "extra": "ignore"}


class SecuritySettings(BaseSettings):
    """安全配置"""
    secret_key: str = Field(default="change-me-in-production-use-256-bit-key", alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="JWT_ACCESS_TOKEN_EXPIRE")
    refresh_token_expire_days: int = Field(default=7, alias="JWT_REFRESH_TOKEN_EXPIRE")
    # CORS
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:5173", alias="CORS_ORIGINS")
    # 加密
    encryption_key: str = Field(default="", alias="ENCRYPTION_KEY")
    # IP白名单
    ip_whitelist: str = Field(default="", alias="IP_WHITELIST")
    ip_blacklist: str = Field(default="", alias="IP_BLACKLIST")

    model_config = {"env_prefix": "SECURITY_", "extra": "ignore"}


class RateLimitSettings(BaseSettings):
    """限流配置"""
    enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    # 全局限流
    global_rate: int = Field(default=1000, alias="RATE_LIMIT_GLOBAL")
    global_period: int = Field(default=60, alias="RATE_LIMIT_GLOBAL_PERIOD")
    # 用户级限流
    user_rate: int = Field(default=60, alias="RATE_LIMIT_USER")
    user_period: int = Field(default=60, alias="RATE_LIMIT_USER_PERIOD")
    # API级限流
    api_rate: int = Field(default=100, alias="RATE_LIMIT_API")
    api_period: int = Field(default=60, alias="RATE_LIMIT_API_PERIOD")
    # 大模型调用限流
    llm_rate: int = Field(default=30, alias="RATE_LIMIT_LLM")
    llm_period: int = Field(default=60, alias="RATE_LIMIT_LLM_PERIOD")

    model_config = {"env_prefix": "RATE_LIMIT_", "extra": "ignore"}


class CircuitBreakerSettings(BaseSettings):
    """熔断器配置"""
    enabled: bool = Field(default=True, alias="CIRCUIT_BREAKER_ENABLED")
    failure_threshold: int = Field(default=5, alias="CB_FAILURE_THRESHOLD")
    recovery_timeout: int = Field(default=30, alias="CB_RECOVERY_TIMEOUT")
    expected_exception_count: int = Field(default=3, alias="CB_EXPECTED_EXCEPTION_COUNT")

    model_config = {"env_prefix": "CB_", "extra": "ignore"}


class AgentSettings(BaseSettings):
    """Agent框架配置"""
    max_iterations: int = Field(default=10, alias="AGENT_MAX_ITERATIONS")
    max_execution_time: int = Field(default=300, alias="AGENT_MAX_EXECUTION_TIME")
    # 子Agent配置
    enable_document_agent: bool = True
    enable_retrieval_agent: bool = True
    enable_compliance_agent: bool = True
    enable_comparison_agent: bool = True
    enable_legal_search_agent: bool = True
    enable_drafting_agent: bool = True
    enable_validation_agent: bool = True

    model_config = {"env_prefix": "AGENT_", "extra": "ignore"}


class RAGSettings(BaseSettings):
    """RAG管线配置"""
    # 分块策略
    chunk_size_min: int = Field(default=128, alias="RAG_CHUNK_SIZE_MIN")
    chunk_size_max: int = Field(default=1024, alias="RAG_CHUNK_SIZE_MAX")
    chunk_overlap: int = Field(default=64, alias="RAG_CHUNK_OVERLAP")
    # 检索配置
    vector_top_k: int = Field(default=50, alias="RAG_VECTOR_TOP_K")
    keyword_top_k: int = Field(default=30, alias="RAG_KEYWORD_TOP_K")
    graph_top_k: int = Field(default=20, alias="RAG_GRAPH_TOP_K")
    # 重排配置
    coarse_rerank_top_k: int = Field(default=30, alias="RAG_COARSE_RERANK_TOP_K")
    fine_rerank_top_k: int = Field(default=10, alias="RAG_FINE_RERANK_TOP_K")
    # 上下文窗口分配(token数)
    system_prompt_tokens: int = Field(default=2048, alias="RAG_SYSTEM_PROMPT_TOKENS")
    memory_tokens: int = Field(default=4096, alias="RAG_MEMORY_TOKENS")
    context_tokens: int = Field(default=16384, alias="RAG_CONTEXT_TOKENS")
    generation_tokens: int = Field(default=8192, alias="RAG_GENERATION_TOKENS")
    # Self-RAG & CRAG
    enable_self_rag: bool = Field(default=True, alias="RAG_ENABLE_SELF_RAG")
    enable_crag: bool = Field(default=True, alias="RAG_ENABLE_CRAG")
    max_retrieval_rounds: int = Field(default=3, alias="RAG_MAX_RETRIEVAL_ROUNDS")
    relevance_threshold: float = Field(default=0.7, alias="RAG_RELEVANCE_THRESHOLD")

    model_config = {"env_prefix": "RAG_", "extra": "ignore"}


class Settings(BaseSettings):
    """主配置 - 聚合所有子配置"""
    app_name: str = Field(default="合同合规Agent系统", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    workers: int = Field(default=4, alias="WORKERS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # 子配置
    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    milvus: MilvusSettings = MilvusSettings()
    nebula: NebulaSettings = NebulaSettings()
    minio: MinioSettings = MinioSettings()
    kafka: KafkaSettings = KafkaSettings()
    llm: AliyunLLMSettings = AliyunLLMSettings()
    tracing: TracingSettings = TracingSettings()
    prometheus: PrometheusSettings = PrometheusSettings()
    security: SecuritySettings = SecuritySettings()
    rate_limit: RateLimitSettings = RateLimitSettings()
    circuit_breaker: CircuitBreakerSettings = CircuitBreakerSettings()
    agent: AgentSettings = AgentSettings()
    rag: RAGSettings = RAGSettings()

    model_config = {"env_prefix": "", "extra": "ignore"}


# 全局单例
settings = Settings()
