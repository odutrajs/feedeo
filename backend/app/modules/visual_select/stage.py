import json

from app.db.models import AssetKind, SourceSegment
from app.modules.script.creative_stage import build_segment_inventory
from app.modules.visual_select.service import select_visuals
from app.pipeline.stage import Stage, StageContext


class VisualSelectStage(Stage):
    """Modo creative: casa cada cena da copy com o melhor trecho enviado (ou imagem IA)."""

    name = "visual_plan"
    label = "Seleção de trechos"

    def run(self, ctx: StageContext) -> None:
        project = ctx.project
        scenes = sorted(project.scenes, key=lambda s: s.index)
        if not scenes:
            raise RuntimeError("Projeto não tem cenas; rode a etapa de copy primeiro")

        inventory = build_segment_inventory(ctx)
        ctx.set_status("Escolhendo os melhores trechos para cada cena...")
        ctx.log(f"Selecionando visuais: {len(scenes)} cenas x {len(inventory)} trechos")

        selection = select_visuals(
            scenes=[
                {
                    "index": s.index,
                    "role": s.role,
                    "narration": s.narration_text,
                    "visual_description": s.visual_description,
                    "duration": (
                        (s.end_time - s.start_time)
                        if s.start_time is not None and s.end_time is not None
                        else s.estimated_duration
                    ),
                }
                for s in scenes
            ],
            inventory=inventory,
            brief=project.topic,
        )

        valid_ids = {seg["id"] for seg in inventory}
        by_index = {sel.scene_index: sel for sel in selection.selections}
        for scene in scenes:
            sel = by_index.get(scene.index)
            if sel is None:
                raise RuntimeError(f"Seleção visual não cobriu a cena {scene.index}")
            if sel.choice == "segment" and sel.segment_id in valid_ids:
                segment = ctx.db.get(SourceSegment, sel.segment_id)
                kind = (segment.meta or {}).get("kind", "video")
                scene.visual_source = "segment" if kind == "video" else "source_image"
                scene.source_segment_id = segment.id
                scene.source_asset_id = segment.source_id
                scene.image_prompt = None
                scene.motion = "zoom_in"  # usado apenas se o visual for imagem
                ctx.log(
                    f"Cena {scene.index} ({scene.role}): trecho #{segment.id} "
                    f"({segment.duration:.1f}s) — {sel.reason}"
                )
            else:
                if not sel.image_prompt:
                    raise RuntimeError(
                        f"Cena {scene.index}: fallback de imagem IA sem prompt definido"
                    )
                scene.visual_source = "ai_image"
                scene.source_segment_id = None
                scene.source_asset_id = None
                scene.image_prompt = sel.image_prompt
                scene.motion = "zoom_in"
                ctx.log(f"Cena {scene.index} ({scene.role}): imagem IA — {sel.reason}")
        ctx.db.commit()

        path = ctx.project_dir / "visual_plan.json"
        path.write_text(selection.model_dump_json(indent=2), encoding="utf-8")
        ctx.save_asset(
            AssetKind.style_guide,
            path,
            meta={"mode": "creative", "scenes": len(scenes)},
        )
        used = sum(1 for s in scenes if s.visual_source != "ai_image")
        ctx.set_status(f"{used}/{len(scenes)} cenas usam trechos reais enviados")
