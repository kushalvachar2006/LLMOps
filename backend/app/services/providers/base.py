"""Provider abstraction: add a new LLM vendor by implementing LLMProvider."""
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class GenerationParams:
    prompt: str
    model: str
    system_instruction: str | None = None
    temperature: float = 0.7
    max_output_tokens: int = 1024


@dataclass(frozen=True)
class ProviderResult:
    text: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None


class LLMProvider(Protocol):
    name: str
    default_model: str

    def generate(self, params: GenerationParams) -> ProviderResult:
        """Raise a ProviderError subclass on failure (never leak credentials)."""
        ...
