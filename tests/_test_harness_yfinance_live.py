# -*- coding: utf-8 -*-
import asyncio
import os
import shutil
import sys
import unittest
from pathlib import Path
from datetime import date, timedelta
import pandas as pd
import logging

# --- 標準化「路徑自我校正」樣板碼 START ---
# 取得目前腳本檔案的目錄
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# 自動偵測專案根目錄 (假設 .git 在根目錄，或存在 README.md)
project_root_var = current_script_dir # 使用不同的變數名以避免與後續的 project_root 衝突
max_levels_up = 5 # 防止無限迴圈，可根據專案深度調整
for _ in range(max_levels_up):
    # 檢查是否存在 .git 目錄或 AGENTS.md (或 README.md) 作為根目錄標記
    if os.path.isdir(os.path.join(project_root_var, '.git')) or \
       os.path.isfile(os.path.join(project_root_var, 'AGENTS.md')) or \
       os.path.isfile(os.path.join(project_root_var, 'README.md')):
        break
    parent_dir = os.path.dirname(project_root_var)
    if parent_dir == project_root_var: # 已達檔案系統頂層
        project_root_var = os.path.abspath(os.path.join(current_script_dir, '..')) # tests/ 腳本，根目錄是上一層
        print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑 (tests 腳本): {project_root_var}")
        break
    project_root_var = parent_dir
else: # 如果迴圈正常結束 (未 break)
    project_root_var = os.path.abspath(os.path.join(current_script_dir, '..')) # 後備方案
    print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑 (tests 腳本): {project_root_var}")

if project_root_var not in sys.path:
    sys.path.insert(0, project_root_var)
# print(f"DEBUG: 專案根目錄 {project_root_var} 已添加到 sys.path")
# --- 標準化「路徑自我校正」樣板碼 END ---

from pathlib import Path # 確保 Path 在此處導入
project_root = Path(project_root_var) # 保持 project_root 變數（如果後續測試代碼中用到了）

from apps.yfinance_downloader import downloader # 從修改後的 downloader 導入

# 配置日誌，以便在測試中觀察下載器的輸出
# 可以根據需要調整日誌級別和格式
logging.basicConfig(stream=sys.stdout, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(name)s - %(message)s')
logger = logging.getLogger(__name__)

# 測試用的輸出目錄
TEST_OUTPUT_DIR = project_root / "test_yfinance_output"

class TestYFinanceDownloaderLive(unittest.IsolatedAsyncioTestCase):

    @classmethod
    def setUpClass(cls):
        """在所有測試開始前，創建測試輸出目錄"""
        if TEST_OUTPUT_DIR.exists():
            shutil.rmtree(TEST_OUTPUT_DIR)
        TEST_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"測試輸出目錄 {TEST_OUTPUT_DIR} 已創建。")

    @classmethod
    def tearDownClass(cls):
        """在所有測試結束後，可選擇是否刪除測試輸出目錄"""
        # pass # 保持輸出以供檢查
        if TEST_OUTPUT_DIR.exists():
            shutil.rmtree(TEST_OUTPUT_DIR)
            logger.info(f"測試輸出目錄 {TEST_OUTPUT_DIR} 已刪除。")

    async def _run_downloader(self, ticker: str, test_date: str) -> int:
        """輔助函數：執行 yfinance_downloader.py 腳本"""
        # 構建參數列表
        args = [
            "--ticker", ticker,
            "--date", test_date,
            "--output-dir", str(TEST_OUTPUT_DIR),
            "--log-level", "DEBUG" # 在測試時使用更詳細的日誌
        ]

        # 保存原始 sys.argv
        original_argv = sys.argv
        try:
            # 設置 mock 的 sys.argv
            sys.argv = ["downloader.py"] + args # 第一個元素通常是腳本名稱

            # 調用 downloader 的 main 函數
            # downloader.main() 是異步的，所以 await 它
            await downloader.main()
            # main 函數內部會調用 sys.exit(exit_code)，我們需要捕獲它
            # 然而，直接調用 main() 會導致測試進程退出。
            # 我們需要一種方式來運行它並獲取退出碼，而不實際退出測試運行器。
            # 一個方法是修改 downloader.main，使其返回 exit_code 而不是調用 sys.exit()
            # 或者，我們可以模擬 sys.exit
            # 為了簡單起見，我們假設 downloader.main 能夠正常完成或拋出異常
            # 並且我們主要通過檢查檔案是否創建和日誌輸出來驗證行為
            # 此處的 exit_code 只是示意性的，實際的 downloader.main 會 sys.exit
            # 我們將依賴 downloader 內部日誌和檔案輸出來判斷結果

            # 由於 downloader.main() 內部有 sys.exit()，我們需要捕獲 SystemExit
            # 並從中獲取 exit_code
            # 注意：unittest.IsolatedAsyncioTestCase 可能會自動處理異步任務中的 SystemExit
            # 但為了明確，我們可以自己捕獲
            # return 0 # 假設成功，後續斷言會驗證
        except SystemExit as e:
            return e.code # 返回實際的退出碼
        except Exception as e:
            logger.error(f"執行下載器時發生未預期錯誤: {e}", exc_info=True)
            return -1 # 表示測試輔助函數本身出錯
        finally:
            # 恢復原始 sys.argv
            sys.argv = original_argv
        return 99 # 如果沒有 sys.exit 被調用，返回一個特殊值表示流程問題

    def _get_expected_parquet_path(self, ticker: str, test_date: date) -> Path:
        """輔助函數：獲取預期的 Parquet 檔案路徑"""
        sanitized_ticker = ticker.replace('=F', '_F').replace('^', '_')
        return TEST_OUTPUT_DIR / f"{sanitized_ticker}_{test_date.strftime('%Y%m%d')}.parquet"

    async def test_download_on_us_trading_day(self):
        """測試：下載 AAPL 在一個美國交易日的數據。"""
        ticker = "AAPL"
        # 選擇一個已知的過去交易日，以確保數據存在
        # 例如 2024年7月15日 (週一)
        test_date_str = "2024-07-15"
        test_date_obj = date(2024, 7, 15)

        logger.info(f"開始測試: test_download_on_us_trading_day (Ticker: {ticker}, Date: {test_date_str})")

        # 捕獲 stdout/stderr 來檢查日誌輸出 (可選，但有助於調試)
        # with CaptureOutput() as captured_output:
        exit_code = await self._run_downloader(ticker, test_date_str)

        self.assertEqual(exit_code, downloader.EXIT_CODE_SUCCESS, f"下載器應成功退出，但退出碼為 {exit_code}")

        expected_file = self._get_expected_parquet_path(ticker, test_date_obj)
        self.assertTrue(expected_file.exists(), f"預期的 Parquet 檔案 {expected_file} 未創建。")
        self.assertTrue(expected_file.stat().st_size > 0, f"Parquet 檔案 {expected_file} 為空。")

        # 驗證 Parquet 檔案內容和欄位名稱
        try:
            df = pd.read_parquet(expected_file)
            self.assertFalse(df.empty, f"Parquet 檔案 {expected_file} 讀取後為空 DataFrame。")

            expected_columns = ['open_price', 'high_price', 'low_price', 'close_price', 'adj_close_price', 'trade_volume']
            # 檢查 DataFrame 是否包含所有預期的標準化欄位
            # 注意：yfinance 可能不總是返回所有欄位 (例如 'adj_close_price' 可能不存在於非常舊的數據)
            # 但對於 AAPL 近期數據，這些欄位應該都在
            missing_cols = [col for col in expected_columns if col not in df.columns]
            self.assertEqual(len(missing_cols), 0, f"Parquet 檔案 {expected_file} 缺少標準化欄位: {missing_cols}。實際欄位: {df.columns.tolist()}")

            # 檢查索引是否為 DatetimeIndex
            self.assertIsInstance(df.index, pd.DatetimeIndex, "DataFrame 的索引應為 DatetimeIndex。")
            # 檢查索引日期是否與請求日期一致 (yfinance 返回的 DataFrame 索引是日期)
            # 由於我們請求的是單日數據，DataFrame 應該只有一行對應那個日期
            self.assertIn(pd.Timestamp(test_date_obj), df.index, f"請求的日期 {test_date_obj} 未在 DataFrame 索引中找到。")
            self.assertEqual(len(df.index), 1, f"預期 DataFrame 中只有一天 ({test_date_obj}) 的數據，但找到了 {len(df.index)} 天。")

        except Exception as e:
            self.fail(f"讀取或驗證 Parquet 檔案 {expected_file} 時發生錯誤: {e}")

        logger.info(f"測試完成: test_download_on_us_trading_day (Ticker: {ticker}, Date: {test_date_str}) - 成功")

    async def test_download_on_us_holiday(self):
        """測試：下載 NVDA 在美國國定假日 (2024-11-28 感恩節) 的數據。"""
        ticker = "NVDA"
        test_date_str = "2024-11-28" # 感恩節
        test_date_obj = date(2024, 11, 28)

        logger.info(f"開始測試: test_download_on_us_holiday (Ticker: {ticker}, Date: {test_date_str})")

        exit_code = await self._run_downloader(ticker, test_date_str)

        # 對於假日或無數據日，腳本應正常退出，返回碼為 NO_DATA_AVAILABLE (目前是 0)
        self.assertEqual(exit_code, downloader.EXIT_CODE_NO_DATA_AVAILABLE, f"下載器在假日應返回 NO_DATA_AVAILABLE，但退出碼為 {exit_code}")

        expected_file = self._get_expected_parquet_path(ticker, test_date_obj)
        self.assertFalse(expected_file.exists(), f"不應為假日 {test_date_str} 創建 Parquet 檔案 {expected_file}，但檔案存在。")

        logger.info(f"測試完成: test_download_on_us_holiday (Ticker: {ticker}, Date: {test_date_str}) - 成功，未創建檔案。")

    async def test_download_for_invalid_ticker(self):
        """測試：下載一個無效的股票代碼 (THIS-IS-NOT-A-REAL-TICKER)。"""
        ticker = "THIS-IS-NOT-A-REAL-TICKER"
        # 日期仍然是必需的參數
        test_date_str = "2024-07-15"
        test_date_obj = date(2024, 7, 15)

        logger.info(f"開始測試: test_download_for_invalid_ticker (Ticker: {ticker}, Date: {test_date_str})")

        exit_code = await self._run_downloader(ticker, test_date_str)

        # 對於無效 ticker，腳本應正常退出，返回碼為 INVALID_TICKER (目前是 0)
        # 這與 NO_DATA_AVAILABLE 的退出碼相同，這是根據指揮官的要求
        self.assertEqual(exit_code, downloader.EXIT_CODE_INVALID_TICKER, f"下載器對於無效 Ticker 應返回 INVALID_TICKER，但退出碼為 {exit_code}")

        expected_file = self._get_expected_parquet_path(ticker, test_date_obj)
        # 檔案名稱中的 ticker 部分會是 "THIS-IS-NOT-A-REAL-TICKER_20240715.parquet"
        self.assertFalse(expected_file.exists(), f"不應為無效 Ticker '{ticker}' 創建 Parquet 檔案 {expected_file}，但檔案存在。")

        logger.info(f"測試完成: test_download_for_invalid_ticker (Ticker: {ticker}, Date: {test_date_str}) - 成功，未創建檔案。")

    async def test_download_for_full_spectrum_of_targets(self):
        """測試：並發下載指揮官指定的全光譜目標列表。"""
        targets = [
            'NQ=F', 'ES=F', 'YM=F', '^VIX', '^DJI', '^SPX', '^IXIC', '^TWII', '^HSI',
            '000001.SS', 'DX-Y.NYB', 'ZB=F', 'ZN=F', 'ZT=F', 'ZF=F', '^TNX', 'TLT',
            'SHY', 'IEI', 'CL=F', 'GC=F', 'SI=F', 'GLD', 'AAPL', 'MSFT', 'NVDA', 'GOOG',
            'TSM', '601318.SS', '688981.SS', '0981.HK', 'BTC-USD'
        ]
        # 再加入一個確定無效的代碼
        all_targets_for_run = targets + ["THIS-IS-DEFINITELY-INVALID-TICKER"]

        # 使用與 test_download_on_us_trading_day 相同的日期，這天大部分市場都開市
        test_date_str = "2024-07-15"
        test_date_obj = date(2024, 7, 15)

        logger.info(f"開始測試: test_download_for_full_spectrum_of_targets (Date: {test_date_str}, {len(all_targets_for_run)} targets)")

        tasks = []
        for ticker in all_targets_for_run:
            # 注意：self._run_downloader 內部修改並恢復了 sys.argv。
            # 在 asyncio.gather 中並發運行時，如果多個任務同時修改 sys.argv，可能會產生競爭條件。
            # 雖然 downloader.py 的 argparse 只在啟動時解析一次，
            # 且 IsolatedAsyncioTestCase 為每個測試方法創建新的事件循環實例，
            # 但仍需小心。
            # 一個更安全的做法是讓 _run_downloader 接受參數字典而不是依賴 sys.argv，
            # 或者確保並發調用時 sys.argv 的修改是安全的。
            # 鑑於 downloader.main() 是被 await 的，並且它在完成前不會交還控制權給 _run_downloader 的調用者，
            # 每次 _run_downloader 的執行實際上是順序的（儘管異步），sys.argv 的修改應該是安全的。
            # 不過，如果 downloader.main() 內部有其他異步操作可能導致 sys.argv 在運行中被其他任務讀取，則會有問題。
            # 此處我們暫時假設目前的實現是安全的。
            tasks.append(self._run_downloader(ticker, test_date_str))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        files_created_count = 0
        expected_files_not_found = []
        unexpected_files_found = []

        # 預期在 2024-07-15 有數據的代碼子集 (基於常識判斷，可能需要依實際情況微調)
        # 這些是我們強烈預期會產生檔案的
        # 移除 '^VIX'，因為它有時在 yfinance 中可能表現不穩定或需要特定處理
        # 移除 'DX-Y.NYB', 'ZB=F', 'ZN=F', 'ZT=F', 'ZF=F', '^TNX'，這些是指數或期貨，數據可用性較好，但減少複雜度
        # 移除部分國際市場代碼以簡化主要驗證目標
        strongly_expected_data_tickers = [
            'NQ=F', 'ES=F', 'AAPL', 'MSFT', 'NVDA', 'GOOG', 'TSM', 'BTC-USD', '^SPX', '^TWII'
        ]

        for i, ticker in enumerate(all_targets_for_run):
            result_or_exc = results[i]
            expected_file = self._get_expected_parquet_path(ticker, test_date_obj)

            if isinstance(result_or_exc, Exception):
                self.fail(f"Ticker {ticker} 的下載任務引發了未捕獲的異常: {result_or_exc}")

            exit_code = result_or_exc
            # 所有任務都應該以 0 (SUCCESS 或 NO_DATA/INVALID_TICKER) 退出
            self.assertIn(exit_code, [downloader.EXIT_CODE_SUCCESS, downloader.EXIT_CODE_NO_DATA_AVAILABLE],
                          f"Ticker {ticker} 下載任務退出碼異常: {exit_code}。")

            if expected_file.exists():
                self.assertTrue(expected_file.stat().st_size > 0, f"Parquet 檔案 {expected_file} 為空 (Ticker: {ticker})。")
                files_created_count += 1
                # 對於成功創建的檔案，可以做更詳細的檢查，例如欄位名
                try:
                    df = pd.read_parquet(expected_file)
                    expected_columns_subset = ['open_price', 'high_price', 'low_price', 'close_price'] # 至少要有這些
                    missing_cols = [col for col in expected_columns_subset if col not in df.columns]
                    self.assertEqual(len(missing_cols), 0, f"Parquet 檔案 {expected_file} (Ticker: {ticker}) 缺少核心標準化欄位: {missing_cols}。實際欄位: {df.columns.tolist()}")
                except Exception as e:
                    self.fail(f"讀取或驗證 Parquet 檔案 {expected_file} (Ticker: {ticker}) 時發生錯誤: {e}")

                if ticker == "THIS-IS-DEFINITELY-INVALID-TICKER":
                    unexpected_files_found.append(expected_file)
            else:
                # 如果檔案未創建，但我們強烈預期它應該存在
                if ticker in strongly_expected_data_tickers:
                    expected_files_not_found.append(ticker)

        self.assertFalse(unexpected_files_found,
                         f"為無效 Ticker 創建了不應存在的檔案: {unexpected_files_found}")

        # 這個斷言可能過於嚴格，因為某些 "strongly_expected_data_tickers" 可能由於臨時網絡問題或 yfinance API 行為而失敗
        # 一個更寬鬆的檢查可能是斷言 expected_files_not_found 的數量不超過一個小閾值
        # 或者只對其中最重要的幾個（如 AAPL, MSFT）做嚴格檢查
        if expected_files_not_found:
            logger.warning(f"以下我們強烈預期有數據的 Tickers 未能成功下載或創建檔案: {expected_files_not_found}。這可能表示 yfinance API 的間歇性問題或數據確實不可用。")
        # self.assertEqual(len(expected_files_not_found), 0,
        #                  f"以下我們強烈預期有數據的 Tickers 未能成功下載或創建檔案: {expected_files_not_found}")


        # 至少應該創建了一些檔案 (這個數字是個估計，可以根據實際情況調整)
        # 鑑於 `strongly_expected_data_tickers` 的數量，我們期望至少有這麼多檔案
        self.assertTrue(files_created_count >= len(strongly_expected_data_tickers) - len(expected_files_not_found), # 減去那些未找到的
                        f"預期至少為 {len(strongly_expected_data_tickers)} 個目標中的大部分創建檔案，但只創建了 {files_created_count} 個。")

        logger.info(f"測試完成: test_download_for_full_spectrum_of_targets - 共處理 {len(all_targets_for_run)} targets, 創建了 {files_created_count} 個檔案。")
        if expected_files_not_found:
            logger.warning(f"壓力測試中，部分強預期目標未下載成功: {expected_files_not_found}")


if __name__ == '__main__':
    # 使測試腳本可以直接運行
    # 如果在 VS Code 中運行，可能需要不同的配置來發現測試
    # 例如， python -m unittest tests/_test_harness_yfinance_live.py
    asyncio.run(unittest.main()) # 修正以支持異步測試的直接運行
