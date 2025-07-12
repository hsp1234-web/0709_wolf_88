# apps/run_taifex_prototype_test.py
# TaifexFileReader 原型實戰驗證腳本 (模擬檔案版)

import os
import sys
from pathlib import Path
import pandas as pd

# --- 標準路徑自我校正樣板 ---
try:
    current_path = Path(__file__).resolve()
    project_root = current_path.parent.parent
    if (project_root / "pyproject.toml").exists() and str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
        print(f"資訊：已將專案根目錄 '{project_root}' 添加到 sys.path")
except Exception as e:
    print(f"錯誤：路徑校正失敗。{e}", file=sys.stderr)
    sys.exit(1)
# --- 樣板結束 ---

class TaifexFileReader:
    """
    台灣期貨交易所每日 CSV 檔案讀取器 (原型)。
    專為處理從檔案系統讀取數據而設計。
    """
    def __init__(self, base_path: str):
        self.base_path = Path(base_path)
        if not self.base_path.exists():
            raise FileNotFoundError(f"指定的模擬數據基礎路徑不存在: {self.base_path}")
        print(f"TaifexFileReader (原型) 已初始化，模擬數據基礎路徑: {self.base_path}")

    def read_put_call_ratio(self, date_str: str) -> pd.DataFrame:
        file_name = f"PC_Ratio_{date_str.replace('-', '_')}.csv"
        file_path = self.base_path / file_name
        print(f"\n>>> [任務1] 正在嘗試讀取乾淨的 P/C Ratio 檔案: {file_path}")
        if not file_path.exists():
            print(f"❌ [失敗] 檔案不存在")
            return pd.DataFrame()
        try:
            df = pd.read_csv(file_path, encoding='ms950')
            print(f"✅ [成功] 成功讀取並解析！")
            return df
        except Exception as e:
            print(f"❌ [失敗] 讀取或解析時發生錯誤: {e}")
            return pd.DataFrame()

    def read_delta(self, date_str: str) -> pd.DataFrame:
        file_name = f"Delta值_{date_str.replace('-', '_')}.csv"
        file_path = self.base_path / file_name
        print(f"\n>>> [任務2] 正在嘗試讀取需跳過首行的 Delta 值檔案: {file_path}")
        if not file_path.exists():
            print(f"❌ [失敗] 檔案不存在")
            return pd.DataFrame()
        try:
            # 根據情報，此格式需跳過第一行
            df = pd.read_csv(file_path, encoding='ms950', skiprows=1)
            print(f"✅ [成功] 成功讀取並解析！")
            return df
        except Exception as e:
            print(f"❌ [失敗] 讀取或解析時發生錯誤: {e}")
            return pd.DataFrame()

def main():
    """主執行函數"""
    print("--- [開始] TaifexFileReader 模擬環境驗證 ---")

    # 使用相對於專案根目錄的路徑，確保在任何環境下都能執行
    base_data_path = Path(__file__).resolve().parent.parent / "tests" / "fixtures" / "taifex_data"

    try:
        reader = TaifexFileReader(base_path=str(base_data_path))

        # 驗證讀取乾淨的 P/C Ratio
        pc_ratio_data = reader.read_put_call_ratio(date_str="2025-07-01")
        if not pc_ratio_data.empty:
            print("P/C Ratio 數據預覽:")
            print(pc_ratio_data)

        # 驗證讀取複雜的 Delta 值
        delta_data = reader.read_delta(date_str="2025-07-03")
        if not delta_data.empty:
            print("Delta 值數據預覽:")
            print(delta_data)

    except FileNotFoundError as e:
        print(f"\n錯誤：初始化失敗，請確認 `tests/fixtures/taifex_data` 目錄及模擬檔案是否已建立。詳細資訊: {e}", file=sys.stderr)
    except Exception as e:
        print(f"\n❌ [災難性失敗] 執行過程中發生未預期的錯誤：{e}", file=sys.stderr)
    finally:
        print("\n--- [結束] TaifexFileReader 模擬環境驗證 ---")

if __name__ == "__main__":
    main()
