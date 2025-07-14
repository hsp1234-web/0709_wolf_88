# 檔案: src/apps/evolution_app.py
from src.core.context import AppContext
from src.core.services.evolution_chamber import EvolutionChamber

async def main(context: AppContext):
    print("演化流程開始...")
    chamber = EvolutionChamber(context.queue)
    await chamber.evolve()
    print("演化流程完成。")
