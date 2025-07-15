# 檔案: src/apps/evolution_app.py
from src.core.context import AppContext
from src.core.services.evolution_chamber import EvolutionChamber

async def main(context: AppContext, resume: bool = False):
    """
    應用程式主入口點：初始化並運行演化室。
    這個應用現在只負責“生產”基因體事件。
    """
    print("演化流程開始...")
    chamber = EvolutionChamber(context)
    # 這裡的參數可以來自配置文件或命令列參數
    await chamber.evolve(generations=5, population_size=10, resume=resume)
    print("演化流程完成，基因體事件已全部發布。")
