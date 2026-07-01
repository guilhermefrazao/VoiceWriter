"""
Interface mínima para integração de modelos ASR ao sistema de métricas.

Para adicionar um novo modelo:
1. Crie uma classe que satisfaça o protocolo ASRModel
2. Implemente os 3 métodos: transcribe(), get_name(), get_source()
3. Passe a instância para create_session() e use transcribe() no lugar de model.transcribe()

O sistema de métricas só precisa de TranscriptionResult — não importa qual modelo gerou.
"""

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class TranscriptionResult:
    text: str
    language: str
    segments: list = field(default_factory=list)
    audio_duration_s: float = 0.0
    latency_s: float = 0.0
    peak_memory_mb: float = 0.0


class ASRModel(Protocol):
    def transcribe(self, audio_path: str, language: str) -> TranscriptionResult:
        """Transcreve o áudio e retorna TranscriptionResult."""
        ...

    def get_name(self) -> str:
        """Retorna o nome do modelo, ex: 'distil-large-v3'."""
        ...

    def get_source(self) -> str:
        """Retorna a origem do modelo: 'huggingface' | 'nemo' | 'local'."""
        ...
