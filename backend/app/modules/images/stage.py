from concurrent.futures import ThreadPoolExecutor

from app.core.config import get_settings
from app.db.models import AssetKind
from app.modules.images.service import generate_image
from app.pipeline.stage import Stage, StageContext


class ImagesStage(Stage):
    name = "images"
    label = "Imagens"

    def run(self, ctx: StageContext) -> None:
        project = ctx.project
        all_scenes = sorted(project.scenes, key=lambda s: s.index)
        # Cenas que usam trechos/imagens enviados não precisam de imagem IA
        scenes = [s for s in all_scenes if (s.visual_source or "ai_image") == "ai_image"]
        if not scenes:
            ctx.set_status("Nenhuma imagem IA necessária (cenas usam trechos enviados)")
            ctx.log("Todas as cenas usam mídia enviada; etapa de imagens pulada")
            return
        missing = [s for s in scenes if not s.image_prompt]
        if missing:
            raise RuntimeError(
                f"{len(missing)} cenas sem prompt de imagem; rode o planejamento visual primeiro"
            )

        total = len(scenes)
        ctx.set_status(f"Gerando {total} imagens com IA...")
        ctx.log(
            f"Gerando {total} imagens via {get_settings().fal_image_model} "
            "(1024x1536, qualidade premium)"
        )

        generated = 0

        def _generate_and_track(scene):
            return generate_image(scene.image_prompt)

        with ThreadPoolExecutor(max_workers=3) as pool:
            results = list(pool.map(_generate_and_track, scenes))

        for scene, png in zip(scenes, results):
            generated += 1
            ctx.set_status(f"Salvando imagem {generated}/{total}...")
            version = ctx.next_version(AssetKind.image, scene.id)
            path = ctx.subdir("images") / f"scene_{scene.index:02d}_v{version}.png"
            path.write_bytes(png)
            ctx.save_asset(AssetKind.image, path, scene=scene, meta={"prompt": scene.image_prompt})
            ctx.log(f"Cena {scene.index}: {path.name} salvo")
