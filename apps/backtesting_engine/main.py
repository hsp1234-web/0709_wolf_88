# -*- coding: utf-8 -*-
"""
模擬的回測引擎應用主模組
"""
import sys
import os

# --- 標準化「路徑自我校正」樣板碼 START ---
# 取得目前腳本檔案的目錄
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# 自動偵測專案根目錄 (假設 .git 在根目錄，或存在 README.md)
project_root = current_script_dir
max_levels_up = 5 # 防止無限迴圈，可根據專案深度調整
for _ in range(max_levels_up):
    # 檢查是否存在 .git 目錄或 AGENTS.md (或 README.md) 作為根目錄標記
    if os.path.isdir(os.path.join(project_root, '.git')) or \
       os.path.isfile(os.path.join(project_root, 'AGENTS.md')) or \
       os.path.isfile(os.path.join(project_root, 'README.md')):
        break
    parent_dir = os.path.dirname(project_root)
    if parent_dir == project_root: # 已達檔案系統頂層
        project_root = os.path.abspath(os.path.join(current_script_dir, '..', '..'))
        print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑: {project_root}")
        break
    project_root = parent_dir
else: # 如果迴圈正常結束 (未 break)
    project_root = os.path.abspath(os.path.join(current_script_dir, '..', '..')) # 後備方案
    print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑: {project_root}")

if project_root not in sys.path:
    sys.path.insert(0, project_root)
# print(f"DEBUG: 專案根目錄 {project_root} 已添加到 sys.path")
# --- 標準化「路徑自我校正」樣板碼 END ---

# 指令要求：關鍵依賴項的 import 語句必須放置在模組的頂部
try:
    import vectorbt
except ModuleNotFoundError:
    # 這裡我們不處理，讓導入時的 ModuleNotFoundError 自然拋出
    # 測試腳本將模擬這個導入失敗，並由測試腳本中的頂層執行器來捕獲
    raise

def execute_backtest():
    """
    模擬執行回測的核心業務邏輯。
    在實際應用中，這裡會使用 vectorbt 進行複雜的計算。
    """
    print("回測引擎：核心業務邏輯 `execute_backtest` 已開始執行...")
    # 假設使用 vectorbt 進行了一些操作
    # if vectorbt: # 在實際代碼中，導入成功後可以直接使用
    #     print(f"vectorbt 版本: {vectorbt.__version__} (僅為示例)")
    print("回測引擎：核心業務邏輯 `execute_backtest` 已成功完成。")
    return {"status": "success", "message": "回測執行完畢"}

if __name__ == '__main__':
    # 這是一個模擬的頂層執行器，用於直接運行此模組時的演示
    # 測試腳本中將會有更受控的模擬執行器
    print("--- 模擬直接執行 backtesting_engine.main ---")
    REQUIRED_MODULE = "vectorbt"
    try:
        # 在實際的 run.py 或主執行腳本中，導入和執行會這樣組織
        from apps.backtesting_engine.main import execute_backtest as engine_execute_backtest
        engine_execute_backtest()
    except ModuleNotFoundError as e:
        if e.name == REQUIRED_MODULE:
            module_name = e.name
            print(f"指揮官，Jules 回報在執行任務時發現環境中缺少必要的依賴項（'{module_name}' 模組）。")
            print(f"這可能導致回測功能無法正常運行。請您確認專案的 requirements.txt 文件是否包含所有必需的依賴項。")
            print(f"任務無法繼續。")
        else:
            # 非預期的 ModuleNotFoundError
            print(f"發生未預期的模組未找到錯誤: {e}")
    except Exception as e:
        print(f"執行回測時發生未預期錯誤: {e}")
