"""Application settings."""

from __future__ import annotations

from typing import Optional

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseSettings):
    """Relational database settings (HiDB PG-compatible / PostgreSQL)."""

    db_provider: str = Field(default="hidb_pg", validation_alias=AliasChoices("DB_PROVIDER"))

    host: str = Field(default="localhost", validation_alias=AliasChoices("DB_HOST", "DATABASE_HOST"))
    port: int = Field(default=5432, validation_alias=AliasChoices("DB_PORT", "DATABASE_PORT"))
    user: str = Field(default="contract_agent", validation_alias=AliasChoices("DB_USER", "DATABASE_USER"))
    password: str = Field(default="", validation_alias=AliasChoices("DB_PASSWORD", "DATABASE_PASSWORD"))
    name: str = Field(default="contract_agent", validation_alias=AliasChoices("DB_NAME", "DATABASE_NAME"))

    # DSN-first configuration.
    dsn_write: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("DB_DSN_WRITE", "DATABASE_URL"),
    )
    dsn_read: Optional[str] = Field(default=None, validation_alias=AliasChoices("DB_DSN_READ"))
    ssl_mode: str = Field(default="prefer", validation_alias=AliasChoices("DB_SSL_MODE"))

    # Read replica compatibility.
    read_host: Optional[str] = Field(
        default=None,
        validation_alias=AliasChoices("DB_READ_HOST", "DATABASE_READ_HOST"),
    )
    read_port: int = Field(default=5432, validation_alias=AliasChoices("DB_READ_PORT", "DATABASE_READ_PORT"))

    # Cutover / migration flags.
    dual_write_enabled: bool = Field(default=False, validation_alias=AliasChoices("DB_DUAL_WRITE_ENABLED"))
    read_target: str = Field(default="hidb", validation_alias=AliasChoices("DB_READ_TARGET"))
    cutover_percent: int = Field(default=100, ge=0, le=100, validation_alias=AliasChoices("DB_CUTOVER_PERCENT"))
    legacy_dsn_write: Optional[str] = Field(default=None, validation_alias=AliasChoices("DB_LEGACY_DSN_WRITE"))
    legacy_dsn_read: Optional[str] = Field(default=None, validation_alias=AliasChoices("DB_LEGACY_DSN_READ"))

    # Connection pools.
    pool_size: int = Field(default=20, validation_alias=AliasChoices("DB_POOL_SIZE"))
    max_overflow: int = Field(default=40, validation_alias=AliasChoices("DB_MAX_OVERFLOW"))
    pool_timeout: int = Field(default=30, validation_alias=AliasChoices("DB_POOL_TIMEOUT"))
    pool_recycle: int = Field(default=1800, validation_alias=AliasChoices("DB_POOL_RECYCLE"))

    hidb_pool_size: int = Field(default=30, validation_alias=AliasChoices("HIDB_DB_POOL_SIZE"))
    hidb_max_overflow: int = Field(default=60, validation_alias=AliasChoices("HIDB_DB_MAX_OVERFLOW"))
    hidb_pool_recycle: int = Field(default=900, validation_alias=AliasChoices("HIDB_DB_POOL_RECYCLE"))

    # Startup strategy: None => development/test auto-create, production requires migrations.
    auto_create_schema: Optional[bool] = Field(
        default=None,
        validation_alias=AliasChoices("DB_AUTO_CREATE_SCHEMA"),
    )

    echo: bool = Field(default=False, validation_alias=AliasChoices("DB_ECHO"))

    def _build_pg_dsn(self, host: str, port: int) -> str:
        dsn = f"postgresql+asyncpg://{self.user}:{self.password}@{host}:{port}/{self.name}"
        if self.ssl_mode:
            return f"{dsn}?sslmode={self.ssl_mode}"
        return dsn

    @property
    def write_url(self) -> str:
        if self.dsn_write:
            return self.dsn_write
        return self._build_pg_dsn(self.host, self.port)

    @property
    def read_url(self) -> str:
        if self.dsn_read:
            return self.dsn_read
        host = self.read_host or self.host
        port = self.read_port or self.port
        return self._build_pg_dsn(host, port)

    def pool_config(self, is_hidb: bool = False) -> dict:
        if is_hidb:
            return {
                "pool_size": self.hidb_pool_size,
                "max_overflow": self.hidb_max_overflow,
                "pool_timeout": self.pool_timeout,
                "pool_recycle": self.hidb_pool_recycle,
                "echo": self.echo,
            }
        return {
            "pool_size": self.pool_size,
            "max_overflow": self.max_overflow,
            "pool_timeout": self.pool_timeout,
            "pool_recycle": self.pool_recycle,
            "echo": self.echo,
        }

    model_config = {"env_prefix": "", "extra": "ignore"}


class RedisSettings(BaseSettings):
    host: str = Field(default="localhost", alias="REDIS_HOST")
    port: int = Field(default=6379, alias="REDIS_PORT")
    password: str = Field(default="", alias="REDIS_PASSWORD")
    db: int = Field(default=0, alias="REDIS_DB")
    max_connections: int = Field(default=100, alias="REDIS_MAX_CONNECTIONS")
    socket_timeout: int = Field(default=5, alias="REDIS_SOCKET_TIMEOUT")
    decode_responses: bool = True

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
    host: str = Field(default="localhost", alias="MILVUS_HOST")
    port: int = Field(default=19530, alias="MILVUS_PORT")
    user: str = Field(default="", alias="MILVUS_USER")
    password: str = Field(default="", alias="MILVUS_PASSWORD")
    collection_name: str = Field(default="contract_chunks", alias="MILVUS_COLLECTION")
    dimension: int = Field(default=1024, alias="MILVUS_DIMENSION")
    index_type: str = Field(default="HNSW", alias="MILVUS_INDEX_TYPE")
    metric_type: str = Field(default="COSINE", alias="MILVUS_METRIC_TYPE")
    hnsw_m: int = Field(default=16, alias="MILVUS_HNSW_M")
    hnsw_ef_construction: int = Field(default=200, alias="MILVUS_HNSW_EF_CONSTRUCTION")
    hnsw_ef_search: int = Field(default=64, alias="MILVUS_HNSW_EF_SEARCH")
    partition_by_doc_type: bool = Field(default=True, alias="MILVUS_PARTITION_BY_DOC_TYPE")

    model_config = {"env_prefix": "MILVUS_", "extra": "ignore"}


class NebulaSettings(BaseSettings):
    host: str = Field(default="localhost", alias="NEBULA_HOST")
    port: int = Field(default=9669, alias="NEBULA_PORT")
    user: str = Field(default="root", alias="NEBULA_USER")
    password: str = Field(default="nebula", alias="NEBULA_PASSWORD")
    space: str = Field(default="contract_graph", alias="NEBULA_SPACE")
    max_connection_pool_size: int = Field(default=50, alias="NEBULA_POOL_SIZE")

    model_config = {"env_prefix": "NEBULA_", "extra": "ignore"}


class MinioSettings(BaseSettings):
    endpoint: str = Field(default="localhost:9000", alias="MINIO_ENDPOINT")
    access_key: str = Field(default="minioadmin", alias="MINIO_ACCESS_KEY")
    secret_key: str = Field(default="minioadmin", alias="MINIO_SECRET_KEY")
    bucket: str = Field(default="contract-documents", alias="MINIO_BUCKET")
    secure: bool = Field(default=False, alias="MINIO_SECURE")

    model_config = {"env_prefix": "MINIO_", "extra": "ignore"}


class KafkaSettings(BaseSettings):
    bootstrap_servers: str = Field(default="localhost:9092", alias="KAFKA_BOOTSTRAP_SERVERS")
    group_id: str = Field(default="contract-agent-group", alias="KAFKA_GROUP_ID")
    topic_document_upload: str = "contract.document.upload"
    topic_document_process: str = "contract.document.process"
    topic_vector_generate: str = "contract.vector.generate"
    topic_graph_build: str = "contract.graph.build"
    topic_dead_letter: str = "contract.dead-letter"
    max_poll_records: int = Field(default=100, alias="KAFKA_MAX_POLL_RECORDS")
    session_timeout_ms: int = Field(default=30000, alias="KAFKA_SESSION_TIMEOUT")
    auto_offset_reset: str = "earliest"

    model_config = {"env_prefix": "KAFKA_", "extra": "ignore"}


class IngestionRuntimeSettings(BaseSettings):
    use_kafka: bool = Field(default=True, alias="INGESTION_USE_KAFKA")
    max_retries: int = Field(default=3, ge=1, le=10, alias="INGESTION_MAX_RETRIES")
    strict_connector: bool = Field(default=False, alias="INGESTION_STRICT_CONNECTOR")
    consumer_enabled: bool = Field(default=True, alias="INGESTION_CONSUMER_ENABLED")
    consumer_topic: str = Field(default="contract.document.upload", alias="INGESTION_CONSUMER_TOPIC")
    dead_letter_topic: str = Field(default="contract.dead-letter", alias="INGESTION_DEAD_LETTER_TOPIC")

    model_config = {"env_prefix": "INGESTION_", "extra": "ignore"}


class LegalSourceSettings(BaseSettings):
    enabled: bool = Field(default=False, alias="LEGAL_SOURCE_ENABLED")
    seed_urls: str = Field(
        default="https://www.gov.cn/zhengce/zhengceku/",
        alias="LEGAL_SOURCE_SEED_URLS",
    )
    tenant_allowlist: str = Field(default="default", alias="LEGAL_SOURCE_TENANT_ALLOWLIST")
    sync_interval_minutes: int = Field(default=360, ge=15, alias="LEGAL_SOURCE_SYNC_INTERVAL_MINUTES")
    max_documents_per_sync: int = Field(default=20, ge=1, le=500, alias="LEGAL_SOURCE_MAX_DOCS")
    request_timeout_seconds: int = Field(default=20, ge=3, le=120, alias="LEGAL_SOURCE_TIMEOUT_SECONDS")

    @property
    def seed_url_list(self) -> list[str]:
        return [item.strip() for item in self.seed_urls.split(",") if item.strip()]

    @property
    def tenant_allowlist_values(self) -> set[str]:
        return {item.strip() for item in self.tenant_allowlist.split(",") if item.strip()}

    model_config = {"env_prefix": "LEGAL_SOURCE_", "extra": "ignore"}


class AliyunLLMSettings(BaseSettings):
    api_key: str = Field(default="", alias="DASHSCOPE_API_KEY")
    require_external: bool = Field(default=True, alias="LLM_REQUIRE_EXTERNAL")
    generation_model: str = Field(default="qwen-max", alias="LLM_GENERATION_MODEL")
    generation_temperature: float = Field(default=0.1, alias="LLM_GENERATION_TEMPERATURE")
    generation_top_p: float = Field(default=0.8, alias="LLM_GENERATION_TOP_P")
    generation_max_tokens: int = Field(default=8192, alias="LLM_GENERATION_MAX_TOKENS")
    light_model: str = Field(default="qwen-plus", alias="LLM_LIGHT_MODEL")
    light_temperature: float = Field(default=0.1, alias="LLM_LIGHT_TEMPERATURE")
    light_max_tokens: int = Field(default=4096, alias="LLM_LIGHT_MAX_TOKENS")
    embedding_model: str = Field(default="text-embedding-v3", alias="LLM_EMBEDDING_MODEL")
    embedding_dimension: int = Field(default=1024, alias="LLM_EMBEDDING_DIMENSION")
    reranker_model: str = Field(default="gte-rerank", alias="LLM_RERANKER_MODEL")
    max_concurrent_requests: int = Field(default=50, alias="LLM_MAX_CONCURRENT")
    requests_per_minute: int = Field(default=600, alias="LLM_RPM")
    tokens_per_minute: int = Field(default=1_000_000, alias="LLM_TPM")
    max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")
    retry_delay: float = Field(default=1.0, alias="LLM_RETRY_DELAY")
    timeout: int = Field(default=120, alias="LLM_TIMEOUT")

    model_config = {"env_prefix": "LLM_", "extra": "ignore"}


class TracingSettings(BaseSettings):
    enabled: bool = Field(default=True, alias="TRACING_ENABLED")
    service_name: str = Field(default="contract-agent", alias="TRACING_SERVICE_NAME")
    otlp_endpoint: str = Field(default="http://localhost:4317", alias="OTLP_ENDPOINT")
    jaeger_endpoint: str = Field(default="http://localhost:14268/api/traces", alias="JAEGER_ENDPOINT")
    sample_rate: float = Field(default=1.0, alias="TRACING_SAMPLE_RATE")
    log_correlation: bool = Field(default=True, alias="TRACING_LOG_CORRELATION")

    model_config = {"env_prefix": "TRACING_", "extra": "ignore"}


class PrometheusSettings(BaseSettings):
    enabled: bool = Field(default=True, alias="PROMETHEUS_ENABLED")
    port: int = Field(default=9090, alias="PROMETHEUS_PORT")
    path: str = Field(default="/metrics", alias="PROMETHEUS_PATH")

    model_config = {"env_prefix": "PROMETHEUS_", "extra": "ignore"}


class SecuritySettings(BaseSettings):
    secret_key: str = Field(default="change-me-in-production-use-256-bit-key", alias="SECRET_KEY")
    algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    access_token_expire_minutes: int = Field(default=30, alias="JWT_ACCESS_TOKEN_EXPIRE")
    refresh_token_expire_days: int = Field(default=7, alias="JWT_REFRESH_TOKEN_EXPIRE")
    cors_origins: str = Field(default="http://localhost:3000,http://localhost:5173", alias="CORS_ORIGINS")
    encryption_key: str = Field(default="", alias="ENCRYPTION_KEY")
    ip_whitelist: str = Field(default="", alias="IP_WHITELIST")
    ip_blacklist: str = Field(default="", alias="IP_BLACKLIST")

    model_config = {"env_prefix": "SECURITY_", "extra": "ignore"}


class RateLimitSettings(BaseSettings):
    enabled: bool = Field(default=True, alias="RATE_LIMIT_ENABLED")
    global_rate: int = Field(default=1000, alias="RATE_LIMIT_GLOBAL")
    global_period: int = Field(default=60, alias="RATE_LIMIT_GLOBAL_PERIOD")
    user_rate: int = Field(default=60, alias="RATE_LIMIT_USER")
    user_period: int = Field(default=60, alias="RATE_LIMIT_USER_PERIOD")
    api_rate: int = Field(default=100, alias="RATE_LIMIT_API")
    api_period: int = Field(default=60, alias="RATE_LIMIT_API_PERIOD")
    llm_rate: int = Field(default=30, alias="RATE_LIMIT_LLM")
    llm_period: int = Field(default=60, alias="RATE_LIMIT_LLM_PERIOD")

    model_config = {"env_prefix": "RATE_LIMIT_", "extra": "ignore"}


class CircuitBreakerSettings(BaseSettings):
    enabled: bool = Field(default=True, alias="CIRCUIT_BREAKER_ENABLED")
    failure_threshold: int = Field(default=5, alias="CB_FAILURE_THRESHOLD")
    recovery_timeout: int = Field(default=30, alias="CB_RECOVERY_TIMEOUT")
    expected_exception_count: int = Field(default=3, alias="CB_EXPECTED_EXCEPTION_COUNT")

    model_config = {"env_prefix": "CB_", "extra": "ignore"}


class AgentSettings(BaseSettings):
    max_iterations: int = Field(default=10, alias="AGENT_MAX_ITERATIONS")
    max_execution_time: int = Field(default=300, alias="AGENT_MAX_EXECUTION_TIME")
    enable_document_agent: bool = True
    enable_retrieval_agent: bool = True
    enable_compliance_agent: bool = True
    enable_comparison_agent: bool = True
    enable_legal_search_agent: bool = True
    enable_drafting_agent: bool = True
    enable_validation_agent: bool = True

    model_config = {"env_prefix": "AGENT_", "extra": "ignore"}


class RAGSettings(BaseSettings):
    chunk_size_min: int = Field(default=128, alias="RAG_CHUNK_SIZE_MIN")
    chunk_size_max: int = Field(default=1024, alias="RAG_CHUNK_SIZE_MAX")
    chunk_overlap: int = Field(default=64, alias="RAG_CHUNK_OVERLAP")
    vector_top_k: int = Field(default=50, alias="RAG_VECTOR_TOP_K")
    keyword_top_k: int = Field(default=30, alias="RAG_KEYWORD_TOP_K")
    graph_top_k: int = Field(default=20, alias="RAG_GRAPH_TOP_K")
    coarse_rerank_top_k: int = Field(default=30, alias="RAG_COARSE_RERANK_TOP_K")
    fine_rerank_top_k: int = Field(default=10, alias="RAG_FINE_RERANK_TOP_K")
    system_prompt_tokens: int = Field(default=2048, alias="RAG_SYSTEM_PROMPT_TOKENS")
    memory_tokens: int = Field(default=4096, alias="RAG_MEMORY_TOKENS")
    context_tokens: int = Field(default=16384, alias="RAG_CONTEXT_TOKENS")
    generation_tokens: int = Field(default=8192, alias="RAG_GENERATION_TOKENS")
    enable_self_rag: bool = Field(default=True, alias="RAG_ENABLE_SELF_RAG")
    enable_crag: bool = Field(default=True, alias="RAG_ENABLE_CRAG")
    max_retrieval_rounds: int = Field(default=3, alias="RAG_MAX_RETRIEVAL_ROUNDS")
    relevance_threshold: float = Field(default=0.7, alias="RAG_RELEVANCE_THRESHOLD")

    model_config = {"env_prefix": "RAG_", "extra": "ignore"}


class Settings(BaseSettings):
    app_name: str = Field(default="Contract Agent", alias="APP_NAME")
    app_version: str = Field(default="1.0.0", alias="APP_VERSION")
    environment: str = Field(default="development", alias="ENVIRONMENT")
    debug: bool = Field(default=False, alias="DEBUG")
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    workers: int = Field(default=4, alias="WORKERS")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    database: DatabaseSettings = DatabaseSettings()
    redis: RedisSettings = RedisSettings()
    milvus: MilvusSettings = MilvusSettings()
    nebula: NebulaSettings = NebulaSettings()
    minio: MinioSettings = MinioSettings()
    kafka: KafkaSettings = KafkaSettings()
    ingestion_runtime: IngestionRuntimeSettings = IngestionRuntimeSettings()
    legal_source: LegalSourceSettings = LegalSourceSettings()
    llm: AliyunLLMSettings = AliyunLLMSettings()
    tracing: TracingSettings = TracingSettings()
    prometheus: PrometheusSettings = PrometheusSettings()
    security: SecuritySettings = SecuritySettings()
    rate_limit: RateLimitSettings = RateLimitSettings()
    circuit_breaker: CircuitBreakerSettings = CircuitBreakerSettings()
    agent: AgentSettings = AgentSettings()
    rag: RAGSettings = RAGSettings()

    model_config = {"env_prefix": "", "extra": "ignore"}


settings = Settings()
