# -*- coding: utf-8 -*-
"""
核心工具模組：中央快取引擎 (v2.0 - 永久保存版)

功能：
- 提供一個全專案共用的、配置好快取策略的 requests Session 物件。
- 預設永久保存所有成功獲取的數據。
- 支援透過上下文管理器手動禁用快取，以實現強制刷新。
"""

from contextlib import contextmanager

import requests_cache

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
    print("--- [自我測試] 正在驗證中央快取引擎 (v2.0 永久保存模式) ---")
    test_url = "https://httpbin.org/delay/2"
    session = get_cached_session()
    print("正在進行第一次請求 (應有 2 秒延遲)...")
    import time

    start_time = time.time()
    response1 = session.get(test_url)
    end_time = time.time()
    print(
        f"第一次請求完成。耗時: {end_time - start_time:.2f} 秒。From Cache: {response1.from_cache}"
    )

    print("\n正在進行第二次請求 (應立即完成)...")
    start_time = time.time()
    response2 = session.get(test_url)
    end_time = time.time()
    print(
        f"第二次請求完成。耗時: {end_time - start_time:.2f} 秒。From Cache: {response2.from_cache}"
    )

    print("\n正在進行強制刷新請求 (應再次有 2 秒延遲)...")
    start_time = time.time()
    with temporary_disabled_cache(session):
        response3 = session.get(test_url)
    end_time = time.time()
    print(
        f"強制刷新請求完成。耗時: {end_time - start_time:.2f} 秒。From Cache: {response3.from_cache}"
    )

    print("\n--- [自我測試] 完成 ---")
    session.cache.clear()
    print("測試快取已清理。")
