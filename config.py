from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    openai_api_key:  str = ""
    ollama_base_url: str = ""
    vision_model:    str = ""
    code_model:      str = ""
    output_dir:      str = ""

    # COCO annotation image IDs (mirrors ring_generation_pipeline)
    top_image_id:    int = 2
    side_image_id:   int = 0

    # Refinement loop
    max_refinement_iterations: int = 3   # keep low for API latency
    iou_threshold:  float = 0.75
    max_error_mm:   float = 1.0

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()