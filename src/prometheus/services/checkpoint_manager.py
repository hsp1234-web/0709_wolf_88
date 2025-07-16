import pickle
from pathlib import Path
from typing import Optional

from prometheus.core.logging.log_manager import LogManager

logger = LogManager.get_instance().get_logger("CheckpointManager")


class CheckpointManager:
    """
    一個負責儲存和讀取演化過程狀態的檢查點管理器。
    """

    def __init__(self, checkpoint_path: Path):
        self.path = checkpoint_path

    def save_checkpoint(self, state: dict):
        """將演化狀態以 pickle 格式儲存到檔案。"""
        try:
            self.path.parent.mkdir(exist_ok=True, parents=True)
            with open(self.path, "wb") as f:
                pickle.dump(state, f)
            logger.info(f"演化狀態已成功儲存至: {self.path}")
        except Exception as e:
            logger.error(f"儲存檢查點失敗: {e}", exc_info=True)

    def load_checkpoint(self) -> Optional[dict]:
        """從檔案讀取演化狀態。"""
        if not self.path.exists():
            return None

        try:
            with open(self.path, "rb") as f:
                state = pickle.load(f)
            logger.info(f"成功從 {self.path} 讀取到檢查點。")
            return state
        except Exception as e:
            logger.error(f"讀取檢查點失敗: {e}", exc_info=True)
            return None

    def clear_checkpoint(self):
        """清除舊的檢查點檔案。"""
        if self.path.exists():
            self.path.unlink()
            logger.info(f"已清除舊的檢查點檔案: {self.path}")
