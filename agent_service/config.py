import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Service Configuration
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    
    # Paths - use local paths for local development
    BASE_DIR: str = os.getenv("AGENT_SERVICE_BASE_DIR", os.path.dirname(os.path.abspath(__file__)))
    WORKSPACE_ROOT: str = os.getenv("AGENT_SERVICE_WORKSPACE", os.path.join(BASE_DIR, "workspace"))
    
    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = "gpt-4o"
    
    # Conda
    CONDA_ENV_NAME: str = "gpt"
    CONDA_SH_PATH: str = "/usr0/home/weiweis/miniconda3/etc/profile.d/conda.sh"

    class Config:
        env_file = ".env"

settings = Settings()
