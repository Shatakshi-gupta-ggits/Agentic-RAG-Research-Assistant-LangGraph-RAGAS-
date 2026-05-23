from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Agentic RAG Research Assistant"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "mistral"          # change to "llama3" if preferred
    OLLAMA_EMBED_MODEL: str = "nomic-embed-text"
    CHROMA_PERSIST_DIR: str = "./chroma_db"
    UPLOAD_DIR: str = "./uploads"
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 150
    TOP_K_RETRIEVAL: int = 6
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"

settings = Settings()
