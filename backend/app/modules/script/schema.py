"""Contrato do roteiro (Módulo 1). Este JSON é consumido por todos os módulos seguintes."""

from typing import Literal

from pydantic import BaseModel, Field

SceneRole = Literal["hook", "intro", "development", "conclusion", "cta"]


class ScriptScene(BaseModel):
    role: SceneRole = Field(description="Função da cena dentro do vídeo")
    narration: str = Field(description="Texto exato que será narrado nesta cena")
    visual_description: str = Field(
        description="Descrição do que deve aparecer na tela durante esta cena"
    )
    estimated_duration_seconds: float = Field(
        description="Duração estimada da narração desta cena, em segundos"
    )


class Script(BaseModel):
    title: str = Field(description="Título chamativo do vídeo")
    hook: str = Field(description="Frase de abertura que prende a atenção nos primeiros 3 segundos")
    call_to_action: str = Field(description="Chamada para ação no final do vídeo")
    scenes: list[ScriptScene] = Field(description="Cenas em ordem, cobrindo todo o vídeo")

    @property
    def full_narration(self) -> str:
        return " ".join(scene.narration.strip() for scene in self.scenes)
