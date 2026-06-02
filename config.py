from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict
 
 
class Settings(BaseSettings):
    openai_api_key: str = ""
 
    # Ollama — code generation (always) + vision (when provider="ollama")
    ollama_base_url: str = ""
    vision_model: str = ""
    code_model: str = ""
 
    output_dir: str = ""
 
    # HuggingFace local — vision only (when provider="huggingface")
    # Set to a Hub model ID ("meta-llama/Llama-3.2-11B-Vision-Instruct")
    # or an absolute/relative path to locally downloaded weights.
    # No API token is needed; the model runs entirely on your machine.
    hf_vision_model: str = ""   # e.g. "llava-hf/llava-1.5-7b-hf"
    hf_max_new_tokens: int = 1024  # cap on generated description length
 
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
 
 
@lru_cache
def get_settings() -> Settings:
    return Settings()