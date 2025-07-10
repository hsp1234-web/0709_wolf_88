import datetime
from pydantic import BaseModel, Field

class MarketOHLCV1M(BaseModel):
    """
    定義銀層 1 分鐘 OHLCV 數據的標準結構。
    """
    timestamp: datetime.datetime = Field(..., description="時間戳（每分鐘的開始時間）")
    instrument: str = Field(..., description="合約標的")
    open: float = Field(..., description="開盤價")
    high: float = Field(..., description="最高價")
    low: float = Field(..., description="最低價")
    close: float = Field(..., description="收盤價")
    volume: int = Field(..., description="總成交量")
