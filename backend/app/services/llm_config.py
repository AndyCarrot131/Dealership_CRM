from dataclasses import dataclass


@dataclass
class LLMRuntimeConfig:
    base_url: str
    api_key: str
    model: str


_config: LLMRuntimeConfig | None = None


def get_llm_runtime_config() -> LLMRuntimeConfig:
    global _config
    if _config is None:
        from app.config import settings
        _config = LLMRuntimeConfig(
            base_url=settings.llm_base_url,
            api_key=settings.llm_api_key,
            model=settings.llm_model,
        )
    return _config


def set_llm_runtime_config(base_url: str, api_key: str, model: str) -> None:
    global _config
    _config = LLMRuntimeConfig(base_url=base_url, api_key=api_key, model=model)
