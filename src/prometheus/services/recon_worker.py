# -*- coding: utf-8 -*-
"""
【作戰計畫 129】鳳凰協議
獨立作戰單位 (Independent Worker) 的核心邏輯。
"""
import asyncio
import logging
from typing import Optional

from prometheus.core.logging.log_manager import LogManager
from prometheus.core.db.duckdb_writer import DuckDBWriter
from prometheus.core.queue.sqlite_queue import SQLiteQueue
from prometheus.core.engines.robust_acquisition_engine import RobustDataAcquisitionEngine

class ReconWorker:
    """
    一個獨立的偵察工人，負責從共享佇列中獲取任務、執行數據偵察並將結果持久化。
    """
    def __init__(self, worker_id: int):
        """
        初始化一個偵察工人。

        :param worker_id: 工人的唯一識別碼。
        """
        self.worker_id = worker_id
        self.logger = self._setup_logger()
        self.results_writer = self._setup_results_writer()
        self.task_queue = self._setup_task_queue()
        # 引擎在每次循環中根據任務動態創建
        self.acquisition_engine = None

        self.logger.info(f"工人 {self.worker_id} 已初始化。")

    def _setup_logger(self) -> logging.Logger:
        """根據工人 ID 配置專屬的日誌記錄器。"""
        log_manager = LogManager(
            log_file=f"data/logs/recon_worker_{self.worker_id}.log"
        )
        return log_manager.get_logger(f"ReconWorker_{self.worker_id}")

    def _setup_results_writer(self) -> DuckDBWriter:
        """根據工人 ID 配置專屬的結果寫入器。"""
        db_path = f"data/db/recon_worker_{self.worker_id}.duckdb"
        self.logger.info(f"結果寫入器指向 {db_path}")
        return DuckDBWriter(db_path=db_path)

    def _setup_task_queue(self) -> SQLiteQueue:
        """初始化共享的中央任務佇列。"""
        queue_path = "recon_tasks.sqlite"
        self.logger.info(f"任務佇列連接到 {queue_path}")
        return SQLiteQueue(db_path=queue_path, table_name="recon_tasks")

    def _analyze_data_and_get_stats(self, ticker: str, data, interval: str, label: str):
        """
        分析獲取的數據，生成統計結果。
        """
        if data is None or data.empty:
            return {
                "category": "Financial Data",
                "ticker": ticker,
                "interval": interval,
                "label": label,
                "status": "NO_DATA",
                "count": 0,
                "start_date": None,
                "end_date": None,
            }

        return {
            "category": "Financial Data",
            "ticker": ticker,
            "interval": interval,
            "label": label,
            "status": "OK",
            "count": len(data),
            "start_date": data['date'].min().strftime('%Y-%m-%d'),
            "end_date": data['date'].max().strftime('%Y-%m-%d'),
        }

    async def run_loop(self):
        """
        工人的主執行循環。
        """
        self.logger.info(f"工人 {self.worker_id} 開始進入任務循環。")

        # RobustDataAcquisitionEngine 的設計是處理一批 tickers，
        # 但我們這裡是一個工人一次處理一個任務。
        # 我們將直接調用其 `fetch_single_ticker` 方法。
        # 為了避免每個循環都重新創建 session 和斷路器，我們在循環外初始化引擎。
        # 注意：engine 的 __init__ 需要 tickers 列表，但我們在循環中處理單個 ticker。
        # 我們傳入一個空列表來初始化，然後在循環中調用 `fetch_single_ticker`。
        db_path = f"data/db/recon_worker_{self.worker_id}.duckdb"
        self.acquisition_engine = RobustDataAcquisitionEngine(tickers=[], db_path=db_path)

        while True:
            try:
                # 1. 帶超時地從佇列獲取任務
                task = self.task_queue.get(block=True, timeout=5)

                if task is None:
                    self.logger.info(f"工人 {self.worker_id} 在等待5秒後未收到任務，循環終止。")
                    break

                self.logger.info(f"工人 {self.worker_id} 獲取到任務: {task}")

                ticker = task.get("ticker")
                interval = task.get("interval", "1d")
                period = task.get("period", "10y")
                label = task.get("label", "Default")

                if not ticker:
                    self.logger.warning(f"任務格式不正確，缺少 'ticker': {task}")
                    continue

                # 2. 執行數據探測
                _ticker, data_df = await self.acquisition_engine.fetch_single_ticker(
                    ticker, interval=interval, period=period
                )

                # 3. 分析數據並生成統計結果
                recon_result = self._analyze_data_and_get_stats(ticker, data_df, interval, label)

                # 4. 將結果寫入私有資料庫
                self.results_writer.write(recon_result)
                self.logger.info(f"工人 {self.worker_id} 已將 '{ticker}' 的偵察結果寫入私有資料庫。")

                # 5. 確認 (ACK) 任務
                # 在目前的 SQLiteQueue 實作中，get() 成功即代表任務已從佇列移除。
                # self.task_queue.task_done(task) # 保留此行以符合標準佇列模式
                self.logger.info(f"工人 {self.worker_id} 已完成任務: {ticker}")

            except Exception as e:
                self.logger.error(f"工人 {self.worker_id} 在執行任務時發生未預期的錯誤: {e}", exc_info=True)
                await asyncio.sleep(5)

        self.logger.info(f"工人 {self.worker_id} 已完成所有任務，正常關閉。")
        self.close()

    def close(self):
        """關閉所有資源。"""
        if self.results_writer:
            self.results_writer.close()
        if self.task_queue:
            self.task_queue.close()
        if self.acquisition_engine:
            self.acquisition_engine.close()
        self.logger.info(f"工人 {self.worker_id} 的所有資源已關閉。")
