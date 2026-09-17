from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    openai_api_key: str = ""
    llm_provider: str = "openai"
    llm_model: str = "gpt-4.1-mini"
    embedding_model: str = "text-embedding-3-small"
    database_url: str = "postgresql+psycopg://rag:rag@db:5432/rag"
    top_k_dense: int = 12
    top_k_lexical: int = 12
    top_k_rerank: int = 6
    rerank_candidate_multiplier: int = 4
    min_rerank_score: float = 0.15
    # --------------------------------------------------------
    # Chunking & Retrieval
    # --------------------------------------------------------
    chunk_size: int = 120
    chunk_overlap: int = 50
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
