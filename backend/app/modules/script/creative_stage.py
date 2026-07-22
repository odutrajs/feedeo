import json

from app.db.models import AssetKind, Scene, SourceSegment, SourceStatus
from app.modules.script.creative import generate_creative_copy
from app.pipeline.stage import Stage, StageContext


def build_segment_inventory(ctx: StageContext) -> list[dict]:
    """Inventário dos trechos habilitados, ordenado por nota, para alimentar a IA."""
    segments = (
        ctx.db.query(SourceSegment)
        .filter(
            SourceSegment.project_id == ctx.project.id,
            SourceSegment.enabled.is_(True),
        )
        .order_by(SourceSegment.score.desc())
        .all()
    )
    return [
        {
            "id": s.id,
            "duration": s.duration,
            "description": s.description,
            "tags": s.tags or [],
            "transcript": s.transcript,
            "score": s.score,
            "hook_potential": (s.meta or {}).get("hook_potential", 0.0),
            "kind": (s.meta or {}).get("kind", "video"),
        }
        for s in segments
    ]


class CreativeScriptStage(Stage):
    """Modo creative: gera a copy do anúncio (hook -> problema -> solução -> prova -> CTA)."""

    name = "script"
    label = "Copy do criativo"

    def run(self, ctx: StageContext) -> None:
        project = ctx.project
        config = project.config or {}

        pending = [
            s for s in project.sources if s.status in (SourceStatus.uploaded, SourceStatus.processing)
        ]
        if pending:
            raise RuntimeError(
                f"{len(pending)} arquivo(s) ainda em análise; aguarde a análise terminar antes de gerar o criativo"
            )

        inventory = build_segment_inventory(ctx)
        ctx.set_status("Escrevendo a copy do criativo com IA...")
        ctx.log(
            f"Gerando copy para o brief: {project.topic!r} "
            f"({len(inventory)} trechos de mídia disponíveis)"
        )

        from app.modules.workspace.context import project_extra_instructions

        if project.workspace is not None:
            ctx.log(f"Usando contexto do projeto: {project.workspace.name!r}")
        copy = generate_creative_copy(
            brief=project.topic,
            language=project.language,
            min_seconds=int(config.get("min_duration", 10)),
            max_seconds=int(config.get("max_duration", 15)),
            extra_instructions=project_extra_instructions(project, config),
            segment_inventory=inventory,
        )
        ctx.set_status(f"Copy pronta! Salvando {len(copy.scenes)} cenas...")
        ctx.log(f"Copy gerada: {copy.title!r} | ângulo: {copy.angle}")
        ctx.log(f"Hooks alternativos: {len(copy.alternative_hooks)}")

        path = ctx.project_dir / "script.json"
        path.write_text(copy.model_dump_json(indent=2), encoding="utf-8")
        ctx.save_asset(
            AssetKind.script,
            path,
            meta={
                "title": copy.title,
                "angle": copy.angle,
                "alternative_hooks": copy.alternative_hooks,
            },
        )

        for old in list(project.scenes):
            ctx.db.delete(old)
        project.scenes.clear()
        ctx.db.flush()

        for i, s in enumerate(copy.scenes):
            scene = Scene(
                project_id=project.id,
                index=i,
                role=s.role,
                narration_text=s.narration,
                visual_description=s.visual_description,
                estimated_duration=s.estimated_duration_seconds,
            )
            project.scenes.append(scene)

        if not project.title:
            project.title = copy.title
        ctx.db.commit()

        total = sum(s.estimated_duration_seconds for s in copy.scenes)
        ctx.log(f"Duração estimada total: {total:.0f}s")
