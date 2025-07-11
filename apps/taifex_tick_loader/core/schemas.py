import datetime
from pydantic import BaseModel, Field


class TaifexTick(BaseModel):
    """
    定義台指期貨秒級 Tick 數據的標準結構，作為銅層的數據契約。
    """

    timestamp: datetime.datetime = Field(..., description="交易時間戳，精確到微秒")
    price: float = Field(..., description="成交價格")
    volume: int = Field(..., description="單筆成交量")
    instrument: str = Field(..., description="合約標的，例如 'TXF202309'")
    tick_type: str = Field(..., description="Tick 類型，例如 'Trade', 'Bid', 'Ask'")
