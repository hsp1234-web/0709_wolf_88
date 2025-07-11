#!/bin/bash
# TAIFEX 全自動化數據作戰鏈 v1.0

# 任何指令失敗都會立即中止腳本
set -e

# --- 配置 ---
START_DATE="2025-07-01"
END_DATE="2025-07-11"
DOWNLOAD_DIR="data/downloads"
RAW_DB="data/raw_warehouse/raw_taifex.duckdb"
SCHEMA_DB="data/metadata/schema_registry.db"
ANALYTICS_DB="data/analytics_warehouse/analytics_taifex.duckdb"

# --- 執行前準備 ---
# 建立必要的數據目錄 (如果不存在)
# 腳本本身會處理子目錄，但確保 data/downloads 存在，因為 p0_downloader 可能直接寫入
echo "--- [準備階段] 確保核心數據目錄存在 ---"
mkdir -p $DOWNLOAD_DIR
mkdir -p $(dirname $RAW_DB)
mkdir -p $(dirname $SCHEMA_DB)
mkdir -p $(dirname $ANALYTICS_DB)

echo "--- [階段 0] 清理舊有下載，準備執行 ---"
# 更安全的清理方式：只刪除目錄內容，不刪除目錄本身
rm -rf $DOWNLOAD_DIR/*
# 注意: 如果 DOWNLOAD_DIR 為空或未設置， '/* ' 可能會意外擴展。
# 但由於我們在上面 mkdir -p，所以 $DOWNLOAD_DIR 應該總是有效的。

# 清理舊的資料庫檔案，確保從頭開始
echo "--- [準備階段] 清理舊的資料庫檔案 ---"
rm -f $RAW_DB
rm -f $SCHEMA_DB
rm -f $ANALYTICS_DB


echo "--- [階段 1] P0 Downloader - 執行數據採集 ---"
poetry run python pipelines/p0_downloader/run.py --start-date $START_DATE --end-date $END_DATE --output-dir $DOWNLOAD_DIR

echo "\n--- [階段 2] P1 Explorer - 執行格式探勘與註冊 ---"
poetry run python pipelines/p1_explorer/run.py --input-dir $DOWNLOAD_DIR --db-path $SCHEMA_DB

echo "\n--- [階段 3] P2/P3 ELT Pipeline - 執行數據加工 ---"
poetry run python pipelines/p2_elt_pipeline/run_elt.py --input-dir $DOWNLOAD_DIR --raw-db-path $RAW_DB --schema-db-path $SCHEMA_DB --analytics-db-path $ANALYTICS_DB

echo "\n\n✅✅✅ 全自動化作戰鏈執行完畢！ ✅✅✅"
echo "最終分析數據庫位於: $ANALYTICS_DB"
