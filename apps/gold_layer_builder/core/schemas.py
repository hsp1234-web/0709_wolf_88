import datetime
from pydantic import BaseModel, Field
from typing import Optional


class GoldMarketOHLCVDaily(BaseModel):
    """
    定義金層每日 OHLCV 數據的標準結構。
    """

    date: datetime.date = Field(..., description="日期")
    instrument: str = Field(..., description="合約標的")
    open: float = Field(..., description="當日開盤價")
    high: float = Field(..., description="當日最高價")
    low: float = Field(..., description="當日最低價")
    close: float = Field(..., description="當日收盤價")
    volume: int = Field(..., description="當日總成交量")


class GoldMarketFeaturesDaily(BaseModel):
    """
    定義金層每日計算特徵的標準結構。
    """

    date: datetime.date = Field(..., description="日期")
    instrument: str = Field(..., description="合約標的")
    MA5: Optional[float] = Field(default=None, alias="ma5", description="5日移動平均線 (收盤價)") # Changed to MA5
    MA20: Optional[float] = Field(default=None, alias="ma20", description="20日移動平均線 (收盤價)") # Changed to MA20
    RSI14: Optional[float] = Field(default=None, alias="rsi14", description="14日相對強弱指數") # Changed to RSI14
    # 根據需求，未來可以擴展更多特徵，例如：
    # VOLATILITY20: Optional[float] = Field(default=None, alias="volatility20", description="20日歷史波動率")
    # macd: Optional[float] = Field(default=None, description="MACD 指標值")
    # macd_signal: Optional[float] = Field(default=None, description="MACD 信號線")
    # bollinger_upper: Optional[float] = Field(default=None, description="布林帶上軌")
    # bollinger_lower: Optional[float] = Field(default=None, description="布林帶下軌")
