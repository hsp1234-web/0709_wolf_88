# prometheus_fire_backend/modules/data_fetcher.py

import logging
from typing import Any, Dict, List, Optional
from pathlib import Path # <--- 導入 Path

# Imports for TaifexClient and DataFetcher
import pandas as pd
import requests # HttpClient 可能會拋出 requests.exceptions.RequestException
import time # HttpClient 內部有延遲機制
# import os # <--- 移除 os，如果不再需要
from io import StringIO # 用於將文字內容視為檔案進行讀取
from .http_client import HttpClient # 引入新的 HttpClient
from core.config import PROJECT_ROOT # <--- 導入 PROJECT_ROOT

# Module-level logger
logger = logging.getLogger(__name__)


class TaifexClient:
    """
    臺灣期貨交易所 (TAIFEX) 資料客戶端。
    負責抓取三大法人未平倉量、P/C Ratio 等數據。
    使用 HttpClient 進行網路請求。
    """
    # 這些 URL 是 CSV 下載的 POST 目標
    URL_FUT_CONTRACTS_CSV = "https://www.taifex.com.tw/cht/3/futContractsDateCsv"
    URL_PC_RATIO_CSV = "https://www.taifex.com.tw/cht/3/pcRatioCsv"

    # DATA_LAKE_ROOT = "data_lake/raw/taifex" # <--- 改為動態設定

    def __init__(self, log_manager: Any, http_client: HttpClient):
        self.log_manager = log_manager
        self.http_client = http_client
        # 設定基於 PROJECT_ROOT 的 data_lake_root
        self.data_lake_root = PROJECT_ROOT / "data_lake" / "raw" / "taifex"
        logger.info(f"TaifexClient 初始化完畢，使用 HttpClient。Data Lake Root: {self.data_lake_root}")

    # _make_request 方法不再需要，將直接使用 http_client
    # def _make_request(...)

    def _save_to_data_lake(self, df: pd.DataFrame, data_type: str, date_str: str, source: str = "taifex") -> Optional[Path]:
        # dir_path = os.path.join(self.DATA_LAKE_ROOT, data_type) # <--- 修改
        # file_name = f"{date_str}.parquet"
        # file_path = os.path.join(dir_path, file_name) # <--- 修改
        dir_path: Path = self.data_lake_root / data_type
        file_path: Path = dir_path / f"{date_str}.parquet"
        try:
            # os.makedirs(dir_path, exist_ok=True) # <--- 修改
            dir_path.mkdir(parents=True, exist_ok=True)
            df.to_parquet(file_path, index=False)
            logger.info(f"數據已儲存到: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"儲存數據到 {file_path} 失敗: {e}")
            if self.log_manager:
                self.log_manager.log_event(
                    event_type="data_save_failed",
                    message=f"儲存 {data_type} 數據到 {str(file_path)} 失敗。", # file_path 是 Path 物件
                    details={"error": str(e), "path": str(file_path), "data_type": data_type, "date": date_str},
                    level="ERROR", source_module="TaifexClient"
                )
            return None

    def fetch_institutional_investors(self, date_str: str, use_mock_data: bool = True, mock_csv_content: Optional[str] = None) -> Optional[pd.DataFrame]:
        logger.info(f"開始抓取 {date_str} 的三大法人數據... (use_mock_data: {use_mock_data})")
        taifex_date_str = date_str.replace('-', '/')
        form_data = {'queryType': '1', 'goDay': '', 'doQuery': '1', 'queryDate': taifex_date_str}

        csv_text_content: Optional[str] = None
        source_type = "模擬"

        if use_mock_data:
            if mock_csv_content is not None:
                logger.info(f"使用提供的模擬 CSV 內容進行三大法人數據處理 ({date_str})。")
                csv_text_content = mock_csv_content
            else:
                # 如果 use_mock_data 為 True 但沒有 mock_csv_content，我們可以選擇返回 None 或記錄警告
                logger.warning(f"TaifexClient: 要求使用模擬數據，但未提供 mock_csv_content for institutional_investors ({date_str})。")
                return None
        else: # 真實數據抓取
            source_type = "網路"
            logger.info(f"TaifexClient: 嘗試從網路抓取 {date_str} 的三大法人數據。URL: {self.URL_FUT_CONTRACTS_CSV}")
            try:
                # 期交所的 CSV 下載通常是 POST 請求，Content-Type 可能是 application/x-www-form-urlencoded
                # HttpClient 的 post 方法預設 data 參數會使用 form-urlencoded
                response = self.http_client.post(self.URL_FUT_CONTRACTS_CSV, data=form_data)
                response.raise_for_status() # 確認請求成功
                # 需要注意期交所回應的編碼，常見的是 'cp950' 或 'big5'
                # requests 函式庫會嘗試猜測編碼，但有時可能需要手動指定
                # response.encoding = response.apparent_encoding # 或者直接設為 'cp950'
                # 為求穩定，若期交所固定用某編碼，可直接指定
                # 檢查回應內容是否為 CSV，而不是錯誤頁面的 HTML
                if 'text/csv' in response.headers.get('Content-Type', '').lower() or "日期" in response.text[:100]: # 簡單檢查
                    csv_text_content = response.text
                    logger.info(f"成功從網路獲取三大法人 CSV 內容 ({date_str})。")
                else:
                    logger.error(f"從網路獲取三大法人數據失敗 ({date_str})：回應非預期 CSV。Content-Type: {response.headers.get('Content-Type')}, Preview: {response.text[:200]}")
                    if self.log_manager:
                        self.log_manager.log_event(
                            event_type="taifex_fetch_unexpected_content",
                            message=f"獲取三大法人數據時得到非CSV回應 ({date_str})。",
                            details={"url": self.URL_FUT_CONTRACTS_CSV, "date": date_str, "content_type": response.headers.get('Content-Type')},
                            level="ERROR", source_module="TaifexClient"
                        )
                    return None

            except requests.exceptions.RequestException as e:
                logger.error(f"TaifexClient 網路請求失敗 (三大法人, {date_str}): {e}")
                if self.log_manager:
                    self.log_manager.log_event(
                        event_type="taifex_request_failed",
                        message=f"請求三大法人數據失敗 ({date_str})。",
                        details={"error": str(e), "url": self.URL_FUT_CONTRACTS_CSV, "date": date_str, "data_type": "institutional_investors"},
                        level="ERROR", source_module="TaifexClient"
                    )
                return None
            except Exception as e: # 其他未知錯誤
                logger.error(f"處理三大法人網路回應時發生未知錯誤 ({date_str}): {e}", exc_info=True)
                if self.log_manager:
                    self.log_manager.log_event(event_type="taifex_response_process_error", message=f"處理三大法人網路回應失敗 ({date_str})", details={"error": str(e)}, level="ERROR", source_module="TaifexClient")
                return None

        if csv_text_content is not None:
            try:
                # 處理期交所CSV常見問題：可能以Big5編碼，且內容中可能有 "查無資料" 或 HTML 錯誤訊息
                if "查無資料" in csv_text_content or "<html" in csv_text_content.lower():
                    logger.warning(f"{date_str} ({taifex_date_str}) 的三大法人數據查無資料或格式不符 (來源: {source_type})。")
                    if self.log_manager:
                         self.log_manager.log_event(event_type="data_fetch_nodata", message=f"{date_str} 的三大法人數據查無資料。", details={"date": date_str, "source": "taifex", "data_type": "institutional_investors", "fetch_source": source_type}, level="WARNING", source_module="TaifexClient")
                    return None

                # 使用 StringIO 將 CSV 字串讀取為 DataFrame
                df = pd.read_csv(StringIO(csv_text_content))
                df.dropna(how='all', inplace=True) # 去除全為NA的行

                if df.empty:
                    logger.warning(f"{date_str} 的三大法人數據解析後為空 DataFrame (來源: {source_type})。")
                    return None

                logger.info(f"成功解析 {date_str} 的三大法人數據 (來源: {source_type})，共 {len(df)} 筆。")
                file_path = self._save_to_data_lake(df, "institutional_investors", date_str)
                if file_path and self.log_manager:
                    self.log_manager.log_event(
                        event_type="data_fetch_success", message=f"成功抓取並儲存 {date_str} 的三大法人數據。",
                        details={"source": "taifex", "data_type": "institutional_investors", "date": date_str, "path": file_path, "rows": len(df), "columns": list(df.columns), "fetch_source": source_type},
                        level="INFO", source_module="TaifexClient"
                    )
                return df
            except Exception as e:
                logger.error(f"處理 {date_str} 的三大法人數據時發生錯誤 (來源: {source_type}, 內容預覽: {csv_text_content[:200]}): {e}", exc_info=True)
                if self.log_manager:
                    self.log_manager.log_event(event_type="data_process_failed", message=f"處理 {date_str} 的三大法人數據時失敗。",details={"error": str(e), "date": date_str, "data_type": "institutional_investors", "fetch_source": source_type}, level="ERROR", source_module="TaifexClient")
                return None
        return None

    def fetch_pc_ratio(self, date_str: str, use_mock_data: bool = True, mock_csv_content: Optional[str] = None) -> Optional[pd.DataFrame]:
        logger.info(f"開始抓取 {date_str} 的 P/C Ratio 數據... (use_mock_data: {use_mock_data})")
        taifex_date_str = date_str.replace('-', '/')
        form_data = {'queryType': '1', 'goDay': '', 'doQuery': '1', 'queryDate': taifex_date_str }

        csv_text_content: Optional[str] = None
        source_type = "模擬"

        if use_mock_data:
            if mock_csv_content is not None:
                logger.info(f"使用提供的模擬 CSV 內容進行 P/C Ratio 數據處理 ({date_str})。")
                csv_text_content = mock_csv_content
            else:
                logger.warning(f"TaifexClient: 要求使用模擬數據，但未提供 mock_csv_content for pc_ratio ({date_str})。")
                return None
        else: # 真實數據抓取
            source_type = "網路"
            logger.info(f"TaifexClient: 嘗試從網路抓取 {date_str} 的 P/C Ratio 數據。URL: {self.URL_PC_RATIO_CSV}")
            try:
                response = self.http_client.post(self.URL_PC_RATIO_CSV, data=form_data)
                response.raise_for_status()
                if 'text/csv' in response.headers.get('Content-Type', '').lower() or "日期" in response.text[:100]:
                    csv_text_content = response.text
                    logger.info(f"成功從網路獲取 P/C Ratio CSV 內容 ({date_str})。")
                else:
                    logger.error(f"從網路獲取 P/C Ratio 數據失敗 ({date_str})：回應非預期 CSV。Content-Type: {response.headers.get('Content-Type')}, Preview: {response.text[:200]}")
                    if self.log_manager:
                        self.log_manager.log_event(
                            event_type="taifex_fetch_unexpected_content",
                            message=f"獲取 P/C Ratio 數據時得到非CSV回應 ({date_str})。",
                            details={"url": self.URL_PC_RATIO_CSV, "date": date_str, "content_type": response.headers.get('Content-Type')},
                            level="ERROR", source_module="TaifexClient"
                        )
                    return None
            except requests.exceptions.RequestException as e:
                logger.error(f"TaifexClient 網路請求失敗 (P/C Ratio, {date_str}): {e}")
                if self.log_manager:
                    self.log_manager.log_event(
                        event_type="taifex_request_failed",
                        message=f"請求 P/C Ratio 數據失敗 ({date_str})。",
                        details={"error": str(e), "url": self.URL_PC_RATIO_CSV, "date": date_str, "data_type": "pc_ratio"},
                        level="ERROR", source_module="TaifexClient"
                    )
                return None
            except Exception as e:
                logger.error(f"處理 P/C Ratio 網路回應時發生未知錯誤 ({date_str}): {e}", exc_info=True)
                if self.log_manager:
                    self.log_manager.log_event(event_type="taifex_response_process_error", message=f"處理 P/C Ratio 網路回應失敗 ({date_str})", details={"error": str(e)}, level="ERROR", source_module="TaifexClient")
                return None

        if csv_text_content is not None:
            try:
                if "查無資料" in csv_text_content or "<html" in csv_text_content.lower():
                    logger.warning(f"{date_str} ({taifex_date_str}) 的 P/C Ratio 數據查無資料或格式不符 (來源: {source_type})。")
                    if self.log_manager:
                        self.log_manager.log_event(event_type="data_fetch_nodata",message=f"{date_str} 的 P/C Ratio 數據查無資料。",details={"date": date_str, "source": "taifex", "data_type": "pc_ratio", "fetch_source": source_type},level="WARNING",source_module="TaifexClient")
                    return None

                # P/C Ratio 的 CSV 可能最後一列是空的，導致解析問題，需要特別處理
                header_line = csv_text_content.splitlines(keepends=False)[0]
                num_expected_cols = len(header_line.split(','))
                # 如果最後一個字元是逗號，表示最後一欄可能為空，pd.read_csv 可能會多讀一欄都是 NaN
                # 因此 usecols 只取到倒數第二欄 (如果原始欄數大於1)
                use_cols_range = range(num_expected_cols -1 if header_line.endswith(',') and num_expected_cols > 1 else num_expected_cols)

                df = pd.read_csv(StringIO(csv_text_content), usecols=use_cols_range if len(use_cols_range) > 0 else None)
                df.dropna(how='all', inplace=True)

                if df.empty:
                    logger.warning(f"{date_str} 的 P/C Ratio 數據解析後為空 DataFrame (來源: {source_type})。")
                    return None

                logger.info(f"成功解析 {date_str} 的 P/C Ratio 數據 (來源: {source_type})，共 {len(df)} 筆。")
                file_path = self._save_to_data_lake(df, "pc_ratio", date_str)
                if file_path and self.log_manager:
                    self.log_manager.log_event(
                        event_type="data_fetch_success", message=f"成功抓取並儲存 {date_str} 的 P/C Ratio 數據。",
                        details={"source": "taifex", "data_type": "pc_ratio", "date": date_str, "path": file_path, "rows": len(df), "columns": list(df.columns), "fetch_source": source_type},
                        level="INFO", source_module="TaifexClient"
                    )
                return df
            except Exception as e:
                logger.error(f"處理 {date_str} 的 P/C Ratio 數據時發生錯誤 (來源: {source_type}, 內容預覽: {csv_text_content[:200]}): {e}", exc_info=True)
                if self.log_manager:
                     self.log_manager.log_event(event_type="data_process_failed",message=f"處理 {date_str} 的 P/C Ratio 數據時失敗。",details={"error": str(e), "date": date_str, "data_type": "pc_ratio", "fetch_source": source_type},level="ERROR",source_module="TaifexClient")
                return None
        return None

class DataFetcher:
    """
    資料獲取器 (Data Fetcher)。
    負責根據任務需求，從不同的資料來源（真實 API 或模擬客戶端）獲取原始數據。
    """
    def __init__(self,
                 log_manager: Any,
                 http_client: HttpClient, # HttpClient 必須傳入
                 execution_mode: str = "SIMULATION", # 保留 execution_mode 以便未來擴展
                 clients: Optional[Dict[str, Any]] = None):
        self.log_manager = log_manager
        self.http_client = http_client # 保存 HttpClient 實例
        self.execution_mode = execution_mode # 目前主要由 mission_params 中的 use_mock 控制
        self.clients = clients if clients else {}
        # 初始化 TaifexClient 時傳入 HttpClient
        self.taifex_client = TaifexClient(log_manager=self.log_manager, http_client=self.http_client)
        # 初始化 YFinanceClient 時傳入 HttpClient
        self.yfinance_client = YFinanceClient(log_manager=self.log_manager, http_client=self.http_client)

        logger.info(f"資料獲取器 (DataFetcher) 初始化完畢。Execution_mode: {self.execution_mode}")
        if self.clients:
            logger.info(f"已配置的外部客戶端: {list(self.clients.keys())}")

    def fetch_data_for_mission(self, mission_id: str, mission_params: Dict[str, Any]) -> Dict[str, Any]:
        logger.info(f"任務 {mission_id}: 開始獲取數據。參數: {mission_params}")
        results: Dict[str, Any] = {}
        task_type = mission_params.get("task_type")

        # 從 mission_params 獲取 use_mock，預設為 True (模擬)
        use_mock: bool = mission_params.get("use_mock", True)

        self.log_manager.log_event(
            event_type="data_fetcher_task_started",
            message=f"DataFetcher 開始處理任務 {mission_id}，類型: {task_type}, use_mock: {use_mock}",
            details={"mission_id": mission_id, "task_type": task_type, "params": mission_params, "use_mock": use_mock},
            source_module="DataFetcher", mission_id=mission_id
        )

        if task_type == "FETCH_TAIFEX":
            target_date = mission_params.get("date")
            if not target_date:
                logger.error(f"任務 {mission_id} (FETCH_TAIFEX): 未指定日期 (date)。")
                results["error"] = "FETCH_TAIFEX 任務未指定日期。"
                self.log_manager.log_event(event_type="data_fetcher_task_failed", message="FETCH_TAIFEX 任務參數錯誤：未指定日期。", details={"mission_id": mission_id}, level="ERROR", source_module="DataFetcher", mission_id=mission_id)
                return results

            data_types_to_fetch = mission_params.get("data_types", ["institutional_investors", "pc_ratio"])

            if use_mock:
                logger.info(f"任務 {mission_id} (FETCH_TAIFEX): 模擬模式執行 (use_mock=True)。")
                mock_institutional_investors_csv = mission_params.get("mock_data", {}).get("institutional_investors_csv")
                mock_pc_ratio_csv = mission_params.get("mock_data", {}).get("pc_ratio_csv")

                if "institutional_investors" in data_types_to_fetch:
                    df_inv = self.taifex_client.fetch_institutional_investors(
                        date_str=target_date,
                        use_mock_data=True,
                        mock_csv_content=mock_institutional_investors_csv
                    )
                    if df_inv is not None:
                        results["taifex_institutional_investors"] = df_inv
                    else:
                        results["taifex_institutional_investors_error"] = f"為日期 {target_date} 獲取三大法人模擬數據失敗。"

                if "pc_ratio" in data_types_to_fetch:
                    df_pc = self.taifex_client.fetch_pc_ratio(
                        date_str=target_date,
                        use_mock_data=True,
                        mock_csv_content=mock_pc_ratio_csv
                    )
                    if df_pc is not None:
                        results["taifex_pc_ratio"] = df_pc
                    else:
                        results["taifex_pc_ratio_error"] = f"為日期 {target_date} 獲取P/C Ratio模擬數據失敗。"
            else: # not use_mock (real data)
                logger.info(f"任務 {mission_id} (FETCH_TAIFEX): 真實數據抓取模式執行 (use_mock=False)。")
                if "institutional_investors" in data_types_to_fetch:
                    df_inv = self.taifex_client.fetch_institutional_investors(
                        date_str=target_date,
                        use_mock_data=False,
                        mock_csv_content=None
                    )
                    if df_inv is not None:
                        results["taifex_institutional_investors"] = df_inv
                    else:
                        results["taifex_institutional_investors_error"] = f"為日期 {target_date} 獲取三大法人真實數據失敗。"

                if "pc_ratio" in data_types_to_fetch:
                    df_pc = self.taifex_client.fetch_pc_ratio(
                        date_str=target_date,
                        use_mock_data=False,
                        mock_csv_content=None
                    )
                    if df_pc is not None:
                        results["taifex_pc_ratio"] = df_pc
                    else:
                        results["taifex_pc_ratio_error"] = f"為日期 {target_date} 獲取P/C Ratio真實數據失敗。"

        elif task_type == "FETCH_YFINANCE":
            target_date = mission_params.get("date")
            ticker_symbol = mission_params.get("ticker_symbol")

            if not target_date or not ticker_symbol:
                error_msg = f"任務 {mission_id} (FETCH_YFINANCE): 未指定日期 (date) 或股票代號 (ticker_symbol)。"
                logger.error(error_msg)
                results["error"] = error_msg
                self.log_manager.log_event(event_type="data_fetcher_task_failed", message="FETCH_YFINANCE 任務參數錯誤。", details={"mission_id": mission_id, "missing_date": not target_date, "missing_ticker": not ticker_symbol}, level="ERROR", source_module="DataFetcher", mission_id=mission_id)
                return results

            if use_mock:
                logger.info(f"任務 {mission_id} (FETCH_YFINANCE): 模擬模式執行 (use_mock=True) for {ticker_symbol} on {target_date}.")
                mock_payload = mission_params.get("mock_data", {}).get("ohlcv_df")
                mock_ohlcv_df_for_client: Optional[pd.DataFrame] = None

                if isinstance(mock_payload, dict):
                    try:
                        # 假設 API 傳來的 dict 是 to_dict(orient='split') 的結果
                        mock_ohlcv_df_for_client = pd.DataFrame.from_dict(mock_payload, orient='split')
                        # yfinance history() 返回的 DataFrame 索引是基於時區的 DatetimeIndex (例如 'America/New_York')
                        # to_dict(orient='split') 會將索引轉換為 ISO 格式的字串列表。
                        # from_dict(orient='split') 會將其讀回為普通 Index。
                        # 我們需要將其轉換回 DatetimeIndex 以匹配 YFinanceClient 儲存和比較時的預期。
                        if 'index' in mock_payload and mock_payload['index']:
                             mock_ohlcv_df_for_client.index = pd.to_datetime(mock_ohlcv_df_for_client.index)
                        logger.info(f"成功從 dict 重建 mock_ohlcv_df for {ticker_symbol}, shape: {mock_ohlcv_df_for_client.shape}")
                    except Exception as e:
                        logger.error(f"從 dict 重建 mock_ohlcv_df 失敗 for {ticker_symbol}: {e}", exc_info=True)
                        results[f"yfinance_ohlcv_{ticker_symbol.replace('.', '_')}_error"] = f"為股票 {ticker_symbol} 日期 {target_date} 重建模擬數據 DataFrame 失敗: {e}"
                        # 如果重建失敗，則不繼續調用 fetch_ohlcv
                        final_message = f"DataFetcher 完成任務 {mission_id}。結果鍵: {list(results.keys())}"
                        logger.info(final_message)
                        self.log_manager.log_event(
                            event_type="data_fetcher_task_completed",
                            message=final_message,
                            details={"mission_id": mission_id, "results_summary": {k:type(v).__name__ for k,v in results.items()}},
                            source_module="DataFetcher", mission_id=mission_id
                        )
                        return results
                elif isinstance(mock_payload, pd.DataFrame): # 如果直接傳入 DataFrame (例如非 API 調用時)
                    mock_ohlcv_df_for_client = mock_payload
                else:
                    logger.warning(f"未提供有效的 ohlcv_df 模擬數據 (應為 dict 或 DataFrame) for {ticker_symbol}。")

                df_ohlcv = self.yfinance_client.fetch_ohlcv(
                    ticker_symbol=ticker_symbol,
                    date_str=target_date,
                    use_mock_data=True,
                    mock_data_content=mock_ohlcv_df
                )
                if df_ohlcv is not None:
                    results[f"yfinance_ohlcv_{ticker_symbol.replace('.', '_')}"] = df_ohlcv
                else:
                    results[f"yfinance_ohlcv_{ticker_symbol.replace('.', '_')}_error"] = f"為股票 {ticker_symbol} 日期 {target_date} 獲取 OHLCV 模擬數據失敗。"

            else: # not use_mock (real data)
                logger.info(f"任務 {mission_id} (FETCH_YFINANCE): 真實數據抓取模式執行 (use_mock=False) for {ticker_symbol} on {target_date}.")
                df_ohlcv = self.yfinance_client.fetch_ohlcv(
                    ticker_symbol=ticker_symbol,
                    date_str=target_date,
                    use_mock_data=False,
                    mock_data_content=None # 真實抓取時不應有 mock_data_content
                )
                if df_ohlcv is not None:
                    results[f"yfinance_ohlcv_{ticker_symbol.replace('.', '_')}"] = df_ohlcv
                else:
                    results[f"yfinance_ohlcv_{ticker_symbol.replace('.', '_')}_error"] = f"為股票 {ticker_symbol} 日期 {target_date} 獲取 OHLCV 真實數據失敗。"

        else:
            logger.warning(f"任務 {mission_id}: 未知的 task_type '{task_type}' 或未實現的處理邏輯。")
            results["error"] = f"未知的 task_type: {task_type}"
            self.log_manager.log_event(event_type="data_fetcher_task_failed", message=f"未知任務類型 {task_type}", details={"mission_id": mission_id, "task_type": task_type}, level="ERROR", source_module="DataFetcher", mission_id=mission_id)

        final_message = f"DataFetcher 完成任務 {mission_id}。結果鍵: {list(results.keys())}"
        logger.info(final_message)
        self.log_manager.log_event(
            event_type="data_fetcher_task_completed",
            message=final_message,
            details={"mission_id": mission_id, "results_summary": {k:type(v).__name__ for k,v in results.items()}},
            source_module="DataFetcher", mission_id=mission_id
        )
        return results

    def _get_default_mock_data(self, source_name: str) -> Any:
        if source_name == "mock_source_A":
            return {"content": "來自模擬來源 A 的數據", "items": [1, 2, 3]}
        elif source_name == "mock_source_B":
            return {"content": "來自模擬來源 B 的數據", "value": 123.45}
        else:
            return {"content": f"未知模擬來源 {source_name} 的數據"}

# --- DataFetcher __main__ test block (這是此檔案唯一的 __main__ 區塊) ---
if __name__ == '__main__':
    # --- Setup Logger for DataFetcher tests ---
    df_logger = logging.getLogger('prometheus_fire_backend.modules.data_fetcher') # Get the module's logger
    df_logger.setLevel(logging.DEBUG)
    if not df_logger.hasHandlers():
        ch = logging.StreamHandler()
        ch.setLevel(logging.DEBUG)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        ch.setFormatter(formatter)
        df_logger.addHandler(ch)

    class MockLoggerMain:
        def __init__(self, name="MockLogger"):
            self.name = name
            self.logs = []
        def log_event(self, event_type, message, details=None, level="INFO", source_module=None, mission_id=None):
            log_entry = f"[{level}] ({source_module or self.name} for mission {mission_id or 'N/A'}): {event_type} - {message} | Details: {details}"
            print(log_entry) # Print to console for live test feedback
            self.logs.append(log_entry)
        def get_logs(self): return self.logs

    mock_log_manager_for_df = MockLoggerMain("DF_Logger")

    MOCK_DATA_ROOT_DF = "mock_data/taifex"
    GOLDEN_DATE = "2025-07-08"

    print(f"\n--- 設定 DataFetcher SIMULATION 模式的模擬數據 ({GOLDEN_DATE}) ---")
    # Use a temporary TaifexClient to generate parquet files for mock_data
    # This client also needs a logger, can use a sub-logger or a different mock
    setup_mock_logger = MockLoggerMain("SetupTaifexClient")
    # DataFetcher 內部 TaifexClient 的 __init__ 簽名是 (log_manager, http_client)
    # 我們需要一個 mock http_client 給它
    mock_http_client_for_setup = HttpClient() # 可以是一個真實的 HttpClient，因為 fetch_* 會用 mock_csv_content
    temp_taifex_client_for_setup = TaifexClient(log_manager=setup_mock_logger, http_client=mock_http_client_for_setup)


    golden_investors_csv = (
        "日期,身份別,多方交易口數,多方交易契約金額(百萬元),空方交易口數,空方交易契約金額(百萬元),多空交易口數淨額,多空交易契約金額淨額(百萬元),多方未平倉口數,多方未平倉契約金額(百萬元),空方未平倉口數,空方未平倉契約金額(百萬元),多空未平倉口數淨額,多空未平倉契約金額淨額(百萬元)\n"
        "2025/07/08,自營商,266543,51886,240474,51465,26069,421,302016,101867,183199,43319,118817,58548\n"
        "2025/07/08,投信,1357,3511,2647,8580,-1290,-5069,55561,213816,14379,57387,41182,156429\n"
        "2025/07/08,外資及陸資,442679,367852,424911,334839,17768,33013,154210,139387,538032,416068,-383822,-276681\n"
    )
    golden_pc_ratio_csv = (
        "日期,賣權成交量,買權成交量,買賣權成交量比率%,賣權未平倉量,買權未平倉量,買賣權未平倉量比率%\n"
        "2025/07/08,341931,385728,88.65,161864,150408,107.62,\n"
    )

    # MOCK_DATA_ROOT_DF 是字串 "mock_data/taifex"
    # 我們應該將其定義為 Path 物件，基於 PROJECT_ROOT
    mock_data_root_path = PROJECT_ROOT / MOCK_DATA_ROOT_DF # MOCK_DATA_ROOT_DF 仍是 "mock_data/taifex"

    df_inv_setup = temp_taifex_client_for_setup.fetch_institutional_investors(GOLDEN_DATE, use_mock_data=True, mock_csv_content=golden_investors_csv)
    if df_inv_setup is not None:
        # path_inv_setup = os.path.join(MOCK_DATA_ROOT_DF, "institutional_investors", f"{GOLDEN_DATE}.parquet") # 修改
        path_inv_setup = mock_data_root_path / "institutional_investors" / f"{GOLDEN_DATE}.parquet"
        # os.makedirs(os.path.dirname(path_inv_setup), exist_ok=True) # 修改
        path_inv_setup.parent.mkdir(parents=True, exist_ok=True)
        df_inv_setup.to_parquet(path_inv_setup, index=False)
        print(f"模擬三大法人 Parquet 已生成到: {path_inv_setup}")

    df_pc_setup = temp_taifex_client_for_setup.fetch_pc_ratio(GOLDEN_DATE, use_mock_data=True, mock_csv_content=golden_pc_ratio_csv)
    if df_pc_setup is not None:
        # path_pc_setup = os.path.join(MOCK_DATA_ROOT_DF, "pc_ratio", f"{GOLDEN_DATE}.parquet") # 修改
        path_pc_setup = mock_data_root_path / "pc_ratio" / f"{GOLDEN_DATE}.parquet"
        # os.makedirs(os.path.dirname(path_pc_setup), exist_ok=True) # 修改
        path_pc_setup.parent.mkdir(parents=True, exist_ok=True)
        df_pc_setup.to_parquet(path_pc_setup, index=False)
        print(f"模擬 P/C Ratio Parquet 已生成到: {path_pc_setup}")

    print("--- 模擬數據設定完畢 ---")

    print("\n--- 測試 DataFetcher (SIMULATION Mode) ---")
    data_fetcher_sim = DataFetcher(log_manager=mock_log_manager_for_df, execution_mode="SIMULATION")
    mission_params_sim = {"task_type": "FETCH_TAIFEX", "date": GOLDEN_DATE, "data_types": ["institutional_investors", "pc_ratio"]}
    sim_results = data_fetcher_sim.fetch_data_for_mission("mission_sim_001", mission_params_sim)

    print("\nDataFetcher SIMULATION mode 結果:")
    assert f"taifex_institutional_investors" in sim_results
    assert isinstance(sim_results["taifex_institutional_investors"], pd.DataFrame)
    assert len(sim_results["taifex_institutional_investors"]) == 3
    print(f"SIMULATION - 三大法人數據 ({type(sim_results['taifex_institutional_investors'])}): {len(sim_results['taifex_institutional_investors'])} 行")

    assert f"taifex_pc_ratio" in sim_results
    assert isinstance(sim_results["taifex_pc_ratio"], pd.DataFrame)
    assert len(sim_results["taifex_pc_ratio"]) == 1
    print(f"SIMULATION - P/C Ratio數據 ({type(sim_results['taifex_pc_ratio'])}): {len(sim_results['taifex_pc_ratio'])} 行")
    assert "買賣權未平倉量比率%" in sim_results["taifex_pc_ratio"].columns

    print("\n--- 測試 DataFetcher (SIMULATION Mode - 數據不存在) ---")
    mission_params_sim_nodata = {"task_type": "FETCH_TAIFEX", "date": "2000-01-01", "data_types": ["institutional_investors"]}
    sim_results_nodata = data_fetcher_sim.fetch_data_for_mission("mission_sim_002", mission_params_sim_nodata)
    print("\nDataFetcher SIMULATION mode (數據不存在) 結果:")
    assert "taifex_institutional_investors_error" in sim_results_nodata
    print(f"SIMULATION (數據不存在) - institutional_investors_error: {sim_results_nodata['taifex_institutional_investors_error']}")

    print("\n--- 測試 DataFetcher (PRODUCTION Mode - 使用黃金數據模擬) ---")
    data_fetcher_prod = DataFetcher(log_manager=mock_log_manager_for_df, execution_mode="PRODUCTION")
    mission_params_prod = {"task_type": "FETCH_TAIFEX", "date": GOLDEN_DATE, "data_types": ["institutional_investors", "pc_ratio"]}
    prod_results = data_fetcher_prod.fetch_data_for_mission("mission_prod_001", mission_params_prod)

    print("\nDataFetcher PRODUCTION mode 結果:")
    assert f"taifex_institutional_investors" in prod_results
    assert isinstance(prod_results["taifex_institutional_investors"], pd.DataFrame)
    assert len(prod_results["taifex_institutional_investors"]) == 3
    print(f"PRODUCTION - 三大法人數據 ({type(prod_results['taifex_institutional_investors'])}): {len(prod_results['taifex_institutional_investors'])} 行")

    assert f"taifex_pc_ratio" in prod_results
    assert isinstance(prod_results["taifex_pc_ratio"], pd.DataFrame)
    assert len(prod_results["taifex_pc_ratio"]) == 1
    print(f"PRODUCTION - P/C Ratio數據 ({type(prod_results['taifex_pc_ratio'])}): {len(prod_results['taifex_pc_ratio'])} 行")
    assert "買賣權未平倉量比率%" in prod_results["taifex_pc_ratio"].columns # This should now pass

    print("\n--- 測試 DataFetcher (PRODUCTION Mode - 非黃金數據日期) ---")
    mission_params_prod_other_date = {"task_type": "FETCH_TAIFEX", "date": "2024-01-01", "data_types": ["institutional_investors"]}
    prod_results_other_date = data_fetcher_prod.fetch_data_for_mission("mission_prod_002", mission_params_prod_other_date)
    print("\nDataFetcher PRODUCTION mode (非黃金數據日期) 結果:")
    assert "taifex_institutional_investors_error" in prod_results_other_date or \
           prod_results_other_date.get("taifex_institutional_investors") is None
    if "taifex_institutional_investors_error" in prod_results_other_date:
        print(f"PRODUCTION (非黃金數據日期) - institutional_investors_error: {prod_results_other_date['taifex_institutional_investors_error']}")
    elif prod_results_other_date.get("taifex_institutional_investors") is None:
         print(f"PRODUCTION (非黃金數據日期) - institutional_investors data is None (as expected).")

    print("\n--- DataFetcher 測試完畢 ---")


class YFinanceClient:
    """
    Yahoo Finance 資料客戶端。
    負責抓取股票的日線 OHLCV 數據。
    """
    def __init__(self, log_manager: Any, http_client: HttpClient): # http_client 暫時未直接使用，但保持 API 一致性
        self.log_manager = log_manager
        self.http_client = http_client # yfinance 內部處理其請求，但保留 http_client 以符合統一接口和未來可能的擴展
        self.data_lake_root = PROJECT_ROOT / "data_lake" / "raw" / "yfinance" / "ohlcv"
        logger.info(f"YFinanceClient 初始化完畢。Data Lake Root: {self.data_lake_root}")

    def _save_to_data_lake(self, df: pd.DataFrame, ticker_symbol: str, date_str: str) -> Optional[Path]:
        """
        將 DataFrame 儲存到 Data Lake 的 Parquet 檔案中。
        路徑結構: data_lake/raw/yfinance/ohlcv/{ticker_symbol}/{date_str}.parquet
        """
        dir_path: Path = self.data_lake_root / ticker_symbol
        file_path: Path = dir_path / f"{date_str}.parquet"
        try:
            dir_path.mkdir(parents=True, exist_ok=True)
            df.to_parquet(file_path, index=True) # yfinance 的 history() 返回的 DataFrame 索引是 Date
            logger.info(f"股票 {ticker_symbol} 的 OHLCV 數據已儲存到: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"儲存股票 {ticker_symbol} 的 OHLCV 數據到 {file_path} 失敗: {e}")
            if self.log_manager:
                self.log_manager.log_event(
                    event_type="data_save_failed",
                    message=f"儲存股票 {ticker_symbol} 的 OHLCV 數據到 {str(file_path)} 失敗。",
                    details={"error": str(e), "path": str(file_path), "ticker": ticker_symbol, "date": date_str},
                    level="ERROR", source_module="YFinanceClient"
                )
            return None

    def fetch_ohlcv(self, ticker_symbol: str, date_str: str, use_mock_data: bool = True, mock_data_content: Optional[pd.DataFrame] = None) -> Optional[pd.DataFrame]:
        """
        獲取指定股票和日期的日線 OHLCV 數據。
        yfinance 的 history() 方法獲取的是一個時間段的數據。
        為了獲取特定一天的數據，我們需要將 start 設定為 date_str，end 設定為 date_str 的後一天。
        """
        logger.info(f"開始抓取股票 {ticker_symbol} 在日期 {date_str} 的 OHLCV 數據... (use_mock_data: {use_mock_data})")

        source_type = "模擬"
        df_ohlcv: Optional[pd.DataFrame] = None

        if use_mock_data:
            if mock_data_content is not None and isinstance(mock_data_content, pd.DataFrame):
                logger.info(f"使用提供的模擬 DataFrame 進行 {ticker_symbol} ({date_str}) 的 OHLCV 數據處理。")
                df_ohlcv = mock_data_content
            else:
                # 可以選擇從預定義的模擬檔案路徑讀取，或簡單返回 None
                logger.warning(f"YFinanceClient: 要求使用模擬數據，但未提供有效的 mock_data_content (DataFrame) for {ticker_symbol} ({date_str})。")
                # 在此樁實現中，若無 mock_data_content 則返回 None
                # 未來可以擴展為從 mock_data/yfinance/ohlcv/{ticker_symbol}/{date_str}.parquet 讀取
                return None
        else: # 真實數據抓取
            source_type = "網路 (yfinance)"
            logger.info(f"YFinanceClient: 嘗試從 yfinance 抓取 {ticker_symbol} 在 {date_str} 的 OHLCV 數據。")
            try:
                import yfinance as yf
                ticker = yf.Ticker(ticker_symbol)

                # 計算結束日期 (開始日期的後一天)
                from datetime import datetime, timedelta
                start_date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                end_date_obj = start_date_obj + timedelta(days=1)
                end_date_str = end_date_obj.strftime("%Y-%m-%d")

                # 獲取歷史數據
                # yfinance 的 history() 返回的 DataFrame，其索引是 DatetimeIndex
                # 如果指定日期沒有數據 (例如假日或非交易日)，返回的 DataFrame 會是空的
                hist_df = ticker.history(start=date_str, end=end_date_str, interval="1d")

                if hist_df.empty:
                    logger.warning(f"YFinanceClient: 股票 {ticker_symbol} 在日期 {date_str} (查詢區間 {date_str} 至 {end_date_str}) 查無 OHLCV 數據 (來源: {source_type})。可能是假日或非交易日。")
                    if self.log_manager:
                        self.log_manager.log_event(
                            event_type="data_fetch_nodata",
                            message=f"股票 {ticker_symbol} 在 {date_str} 查無 OHLCV 數據。",
                            details={"ticker": ticker_symbol, "date": date_str, "source": "yfinance", "data_type": "ohlcv", "fetch_source": source_type},
                            level="WARNING", source_module="YFinanceClient"
                        )
                    return None

                # 篩選確保只取目標日期的數據 (儘管 yfinance 通常只會返回該日)
                # hist_df.index 是 DatetimeIndex，需要比較日期部分
                # df_ohlcv = hist_df[hist_df.index.strftime('%Y-%m-%d') == date_str]
                # 由於我們查詢的是單日，如果 hist_df 非空，它就應該是我們要的數據
                df_ohlcv = hist_df.copy() # 創建副本以避免 SettingWithCopyWarning

                if df_ohlcv.empty: # 再次檢查，以防萬一
                    logger.warning(f"YFinanceClient: 篩選後，股票 {ticker_symbol} 在日期 {date_str} 仍無 OHLCV 數據 (來源: {source_type})。")
                    return None

                logger.info(f"成功從 yfinance 獲取 {ticker_symbol} 在 {date_str} 的 OHLCV 數據，共 {len(df_ohlcv)} 筆 (來源: {source_type})。")

            except ImportError:
                logger.error("YFinanceClient: yfinance 套件未安裝。請先安裝 yfinance。")
                # 這種情況通常不應該發生在已部署的環境，但在開發時可能遇到
                raise
            except Exception as e: # 捕捉 yfinance 可能拋出的其他錯誤，或網路問題
                logger.error(f"YFinanceClient: 抓取 {ticker_symbol} ({date_str}) OHLCV 數據時發生錯誤: {e}", exc_info=True)
                if self.log_manager:
                    self.log_manager.log_event(
                        event_type="yfinance_fetch_failed",
                        message=f"抓取 {ticker_symbol} OHLCV 數據失敗 ({date_str})。",
                        details={"error": str(e), "ticker": ticker_symbol, "date": date_str, "data_type": "ohlcv"},
                        level="ERROR", source_module="YFinanceClient"
                    )
                return None

        if df_ohlcv is not None and not df_ohlcv.empty:
            try:
                # 可在此處添加對 df_ohlcv 的欄位檢查或轉換 (例如確保 Open, High, Low, Close, Volume 存在)
                # yfinance 返回的欄位名通常是 'Open', 'High', 'Low', 'Close', 'Volume', 'Dividends', 'Stock Splits'
                # 我們主要關心 OHLCV
                required_cols = ['Open', 'High', 'Low', 'Close', 'Volume']
                missing_cols = [col for col in required_cols if col not in df_ohlcv.columns]
                if missing_cols:
                    logger.warning(f"YFinanceClient: 從 {source_type} 獲取的 {ticker_symbol} ({date_str}) OHLCV 數據缺少必要欄位: {missing_cols}。可用欄位: {df_ohlcv.columns.tolist()}")
                    # 根據需求決定是否要返回部分數據或 None
                    # 此處選擇如果缺少核心欄位則返回 None
                    return None

                # 為了與 TaifexClient 的儲存行為保持某種程度的一致性 (雖然 TaifexClient 目前不處理 OHLCV)
                # 我們將 DataFrame 儲存，並返回 DataFrame 本身
                file_path = self._save_to_data_lake(df_ohlcv, ticker_symbol, date_str)

                if file_path and self.log_manager:
                    self.log_manager.log_event(
                        event_type="data_fetch_success",
                        message=f"成功抓取並儲存 {ticker_symbol} 在 {date_str} 的 OHLCV 數據。",
                        details={"source": "yfinance", "data_type": "ohlcv", "ticker": ticker_symbol, "date": date_str, "path": str(file_path), "rows": len(df_ohlcv), "columns": list(df_ohlcv.columns), "fetch_source": source_type},
                        level="INFO", source_module="YFinanceClient"
                    )
                # 如果儲存失敗，file_path 會是 None，但我們仍然返回獲取的 df_ohlcv
                # 或者，我們可以選擇如果儲存失敗則也返回 None，取決於需求
                return df_ohlcv
            except Exception as e:
                logger.error(f"YFinanceClient: 處理或儲存 {ticker_symbol} ({date_str}) OHLCV 數據時發生錯誤: {e}", exc_info=True)
                if self.log_manager:
                    self.log_manager.log_event(
                        event_type="data_process_failed",
                        message=f"處理或儲存 {ticker_symbol} OHLCV 數據時失敗 ({date_str})。",
                        details={"error": str(e), "ticker": ticker_symbol, "date": date_str, "data_type": "ohlcv", "fetch_source": source_type},
                        level="ERROR", source_module="YFinanceClient"
                    )
                return None
        elif df_ohlcv is not None and df_ohlcv.empty: # 如果模擬數據是空的 DataFrame
             logger.warning(f"YFinanceClient: 提供的模擬數據 for {ticker_symbol} ({date_str}) 是空的 DataFrame。")

        return None # 如果 df_ohlcv 是 None (例如抓取失敗或無模擬數據)
