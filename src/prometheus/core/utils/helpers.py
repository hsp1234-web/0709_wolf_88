# -*- coding: utf-8 -*-
"""
核心工具模組：中央快取引擎 (v2.0 - 永久保存版)

功能：
- 提供一個全專案共用的、配置好快取策略的 requests Session 物件。
- 預設永久保存所有成功獲取的數據。
- 支援透過上下文管理器手動禁用快取，以實現強制刷新。
"""

from contextlib import contextmanager

try:
    import requests_cache
except ImportError:
    requests_cache = None
from prometheus.core.logging.log_manager import LogManager

logger = LogManager.get_instance().get_logger("Helpers")

# 定義快取檔案的路徑與名稱
CACHE_NAME = ".financial_data_cache"
# 關鍵變更：將過期時間設定為 None，代表「永不過期」
# 數據一經寫入，除非手動清理快取檔案，否則將永久保存。
CACHE_EXPIRE_AFTER = None


def get_cached_session() -> requests_cache.CachedSession:
    """
    獲取一個配置好的、帶有永久快取的 Session 物件。

    Returns:
        requests_cache.CachedSession: 配置完成的快取 Session。
    """
    return requests_cache.CachedSession(
        cache_name=CACHE_NAME,
        backend="sqlite",
        expire_after=CACHE_EXPIRE_AFTER,
        allowable_methods=["GET", "POST"],
    )


@contextmanager
def temporary_disabled_cache(session: requests_cache.CachedSession):
    """
    一個上下文管理器，用於暫時禁用給定 Session 的快取功能。
    這對於實現「強制刷新」功能至關重要。

    Args:
        session (requests_cache.CachedSession): 需要暫時禁用快取的 Session。
    """
    with session.cache_disabled():
        yield


if __name__ == "__main__":
    # (自我測試代碼維持不變，用於驗證新策略)
    logger.info("--- [自我測試] 正在驗證中央快取引擎 (v2.0 永久保存模式) ---")
    test_url = "https://httpbin.org/delay/2"
    session = get_cached_session()
    logger.info("正在進行第一次請求 (應有 2 秒延遲)...")
    import time

    start_time = time.time()
    response1 = session.get(test_url)
    end_time = time.time()
    logger.info(
        f"第一次請求完成。耗時: {end_time - start_time:.2f} 秒。From Cache: {response1.from_cache}"
    )

    logger.info("\n正在進行第二次請求 (應立即完成)...")
    start_time = time.time()
    response2 = session.get(test_url)
    end_time = time.time()
    logger.info(
        f"第二次請求完成。耗時: {end_time - start_time:.2f} 秒。From Cache: {response2.from_cache}"
    )

    logger.info("\n正在進行強制刷新請求 (應再次有 2 秒延遲)...")
    start_time = time.time()
    with temporary_disabled_cache(session):
        response3 = session.get(test_url)
    end_time = time.time()
    logger.info(
        f"強制刷新請求完成。耗時: {end_time - start_time:.2f} 秒。From Cache: {response3.from_cache}"
    )

    logger.info("\n--- [自我測試] 完成 ---")
    session.cache.clear()
    logger.info("測試快取已清理。")


from pathlib import Path
from typing import Tuple

import pandas as pd


def load_ohlcv_data(
    file_path: Path, split_ratio: float = 0.7
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    從 CSV 檔案加載 OHLCV 數據，並將其分割為樣本內和樣本外數據集。

    :param file_path: CSV 檔案的路徑。
    :param split_ratio: 樣本內數據所佔的比例 (例如 0.7 代表 70%)。
    :return: 一個包含 (in_sample_df, out_of_sample_df) 的元組。
    """
    if not file_path.exists():
        raise FileNotFoundError(f"數據檔案不存在: {file_path}")

    # 根據作戰手冊，索引應為 'Date' 且欄位名稱應為小寫
    df = pd.read_csv(file_path, index_col="Date", parse_dates=True)
    df.columns = [col.lower() for col in df.columns]

    # 根據比例計算分割點
    split_point = int(len(df) * split_ratio)

    in_sample_df = df.iloc[:split_point]
    out_of_sample_df = df.iloc[split_point:]

    logger.info(
        f"[DataLoader] 數據已分割：樣本內 {len(in_sample_df)} 筆, 樣本外 {len(out_of_sample_df)} 筆。"
    )

    return in_sample_df, out_of_sample_df


import zipfile
from typing import Dict, Optional


def prospect_file_content(file_bytes: bytes) -> Dict[str, str]:
    """嘗試解碼並讀取第一行(標頭)。"""
    for encoding in ["ms950", "big5", "utf-8", "utf-8-sig"]:
        try:
            content = file_bytes.decode(encoding)
            header = content.splitlines()[0].strip()
            return {"status": "success", "encoding": encoding, "header": header}
        except (UnicodeDecodeError, IndexError):
            continue
    return {"status": "failure", "error": "無法解碼或檔案為空"}


def read_file_content(file_path: str) -> Optional[bytes]:
    """讀取檔案內容，支援 ZIP 檔案。"""
    if zipfile.is_zipfile(file_path):
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                for member_name in zf.namelist():
                    if member_name.lower().endswith((".csv", ".txt")):
                        return zf.read(member_name)
        except zipfile.BadZipFile:
            return None
    elif file_path.lower().endswith((".csv", ".txt")):
        with open(file_path, "rb") as f:
            return f.read()
    return None


def correct_path():
    pass
