import os
from dataclasses import dataclass, field


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


@dataclass
class Settings:
    agent_name: str = field(default_factory=lambda: env("AGENT_NAME", "digital-employee"))
    backend_url: str = field(default_factory=lambda: env("BACKEND_URL", "http://localhost:8000"))
    yandex_api_key: str = field(default_factory=lambda: env("YANDEX_API_KEY"))
    yandex_folder_id: str = field(default_factory=lambda: env("YANDEX_FOLDER_ID"))
    llm_model: str = field(default_factory=lambda: env("AI_LLM_MODEL", "qwen3-235b-a22b-fp8/latest"))
    llm_base_url: str = field(
        default_factory=lambda: env("AI_LLM_BASE_URL", "https://ai.api.cloud.yandex.net/v1")
    )
    voice: str = field(default_factory=lambda: env("AI_VOICE", "dasha"))
    # пожилые люди делают паузы посреди фразы, поэтому ждём дольше обычного
    silence_seconds: float = field(default_factory=lambda: float(env("AI_SILENCE_SECONDS", "1.0")))

    @property
    def provider(self) -> str:
        return f"yandex/{self.llm_model.split('/')[0]}/yandex"
