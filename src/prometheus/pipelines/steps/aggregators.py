import pandas as pd
import yfinance as yf
from prometheus.core.pipelines.base_step import BaseETLStep
from prometheus.core.logging.log_manager import LogManager

class MultiSourceAggregatorStep(BaseETLStep):
    def __init__(self, auxiliary_tickers: dict):
        self.auxiliary_tickers = auxiliary_tickers
        self.logger = LogManager.get_instance().get_logger(self.__class__.__name__)

    def execute(self, data: pd.DataFrame, **kwargs) -> pd.DataFrame:
        if data.empty:
            self.logger.warning("輸入的 DataFrame 為空，跳過聚合步驟。")
            return data

        merged_df = data.copy()

        # 獲取主數據的日期範圍
        start_date = data.index.min()
        end_date = data.index.max()

        for name, ticker in self.auxiliary_tickers.items():
            self.logger.info(f"正在為 {name} ({ticker}) 獲取輔助數據...")
            try:
                aux_data = yf.download(ticker, start=start_date, end=end_date, progress=False)
                if not aux_data.empty:
                    # 只保留 'Adj Close' 並重命名
                    aux_data = aux_data[['Adj Close']].rename(columns={'Adj Close': name})
                    merged_df = merged_df.join(aux_data, how='left')
                else:
                    self.logger.warning(f"找不到 {ticker} 的數據，將用 NaN 填充。")
                    merged_df[name] = pd.NA
            except Exception as e:
                self.logger.error(f"獲取 {ticker} 數據時發生錯誤: {e}，將用 NaN 填充。", exc_info=True)
                merged_df[name] = pd.NA

        # 填充缺失值
        merged_df.fillna(method='ffill', inplace=True)

        self.logger.info("輔助數據聚合完成。")
        return merged_df
