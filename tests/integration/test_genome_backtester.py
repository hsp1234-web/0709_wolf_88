# 檔案: tests/integration/test_genome_backtester.py
import pytest
import pandas as pd
from unittest.mock import MagicMock

from src.core.services.backtesting_service import BacktestingService

@pytest.fixture
def genome_aware_service(app_context):
    """提供一個帶有模擬數據客戶端的、能解讀基因體的回測服務。"""
    service = BacktestingService(app_context.results_saver, app_context.log_manager)

    # 模擬數據，創造一個清晰的均值回歸趨勢
    dates = pd.to_datetime(pd.date_range(start="2023-01-01", periods=200))
    price_data = [100 + (i % 20) * (1 if (i // 20) % 2 == 0 else -1) for i in range(200)]
    mock_price_df = pd.Series(price_data, index=dates, name="Close")

    # 替換真實的 yf_client
    service.yf_client = MagicMock()
    service.yf_client.get_daily_data.return_value = mock_price_df

    return service

def test_rsi_genome_interpretation(genome_aware_service):
    """
    驗證 BacktestingService 能否正確解讀 RSI 策略基因體，
    並在模擬數據上計算出有效的夏普比率。
    """
    # 1. 定義一個標準的 RSI 策略基因體
    rsi_genome = {
        "strategy_name": "RSI_MeanReversion",
        "indicators": [{"name": "RSI", "params": {"window": 14}}],
        "entry_rules": [{"indicator": "RSI", "operator": "<", "value": 30}],
        "exit_rules": [{"indicator": "RSI", "operator": ">", "value": 70}]
    }
    backtest_id = "test_genome_rsi_001"

    # 2. 執行回測
    fitness = genome_aware_service.run_backtest(rsi_genome, backtest_id)

    # 3. 驗證結果
    # 在我們設計的模擬數據上，這個策略應該是盈利的
    assert isinstance(fitness, float), "適應度應為浮點數"
    assert fitness > 0, f"對於一個有效的 RSI 均值回歸策略，夏普比率應為正數，但得到 {fitness}"
