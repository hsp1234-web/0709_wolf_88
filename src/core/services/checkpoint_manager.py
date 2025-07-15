import pickle
import os
from typing import Optional, Any

class CheckpointManager:
    def __init__(self, checkpoint_path: str = "output/evolution_checkpoint.pkl"):
        self.path = checkpoint_path
    def save(self, data: Any):
        with open(self.path, "wb") as f:
            pickle.dump(data, f)
        print(f"方舟：已儲存演化檢查點至 {self.path}")
    def load(self) -> Optional[Any]:
        if not os.path.exists(self.path): return None
        with open(self.path, "rb") as f:
            print(f"方舟：從 {self.path} 讀取到演化檢查點。")
            return pickle.load(f)
    def clear(self):
        if os.path.exists(self.path):
            os.remove(self.path)
            print(f"方舟：已清除舊的演化檢查點 {self.path}。")
