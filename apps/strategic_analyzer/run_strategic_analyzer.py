# -*- coding: utf-8 -*-
"""
普羅米修斯之火 - 戰略分析器每日執行腳本

本腳本負責每日自動運行戰略分析器 (StrategicAnalyzer)，
生成市場核心指標的紅黃綠信號，並將結果存儲到 StrategicDashboard_Daily 資料庫。

執行順序建議：應在因子 ETL 流程 (run_factor_etl.py) 完成之後執行。
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

PROJECT_ROOT = project_root # 保持原有 PROJECT_ROOT 變數的可用性，如果後續代碼依賴它

import pandas as pd
# import os # os 已在上面導入
# import sys # sys 已在上面導入

from apps.daily_market_analyzer.db_manager import DBManager
from apps.strategic_analyzer.analyzer import StrategicAnalyzer

def run_daily_strategic_analysis():
    """
    執行每日的戰略分析流程。
    1. 初始化資料庫管理器和戰略分析器。
    2. 調用分析器生成每日信號。
    3. 將生成的信號存入資料庫。
    """
    print("INFO: 開始執行每日戰略分析流程...")

    # TODO: 數據庫路徑應從統一的配置文件中讀取
    # 暫時硬編碼，與 run_factor_etl.py 中的路徑保持一致
    db_file_path = os.path.join(PROJECT_ROOT, 'data_workspace', 'market_data.duckdb')

    # 檢查資料庫檔案是否存在
    if not os.path.exists(db_file_path):
        print(f"錯誤: 資料庫檔案 {db_file_path} 不存在。請先執行相關數據準備流程。")
        print("每日戰略分析流程終止。")
        return

    try:
        db_manager = DBManager(db_path=db_file_path)
        strategic_analyzer = StrategicAnalyzer(db_manager=db_manager)
    except Exception as e:
        print(f"錯誤: 初始化 DBManager 或 StrategicAnalyzer 失敗: {e}")
        print("每日戰略分析流程終止。")
        return

    print("INFO: 正在生成每日戰略信號...")
    # 呼叫 generate_daily_signals 時不傳遞 analysis_date_str,
    # 讓 StrategicAnalyzer 自動判斷最新分析日期
    daily_signals_df = strategic_analyzer.generate_daily_signals()

    if daily_signals_df is not None and not daily_signals_df.empty:
        print(f"INFO: 成功生成 {len(daily_signals_df)} 條戰略信號數據。")
        print("INFO: 準備將信號數據寫入 StrategicDashboard_Daily 資料庫...")
        try:
            db_manager.insert_strategic_signals(daily_signals_df)
            print("INFO: 每日戰略信號已成功寫入資料庫。")
        except Exception as e:
            print(f"錯誤: 將戰略信號寫入資料庫失敗: {e}")
    elif daily_signals_df is not None and daily_signals_df.empty:
        print("INFO: StrategicAnalyzer 生成了空的信號 DataFrame，無需寫入資料庫。")
    else: # daily_signals_df is None (理論上 analyzer 應該返回空 DF 而不是 None)
        print("警告: StrategicAnalyzer 未返回有效的信號 DataFrame (可能為 None)。")

    print("INFO: 每日戰略分析流程執行完畢。")

if __name__ == '__main__':
    run_daily_strategic_analysis()
