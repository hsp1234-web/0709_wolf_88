# 檔案: tests/unit/core/test_genome_evolution_chamber.py
import pytest
from unittest.mock import MagicMock
from src.core.services.evolution_chamber import EvolutionChamber, create_rsi_genome, mutate_genome

@pytest.fixture
def genome_chamber():
    """提供一個用於單元測試的、無需真實佇列的 EvolutionChamber 實例。"""
    mock_queue = MagicMock()
    mock_log_manager = MagicMock()
    return EvolutionChamber(mock_queue, mock_log_manager)

def test_genome_creation(genome_chamber):
    """驗證演化室的 toolbox 能否生成一個結構正確的策略基因體。"""
    # 1. 使用 toolbox 生成一個個體
    individual = genome_chamber.toolbox.individual()

    # 2. 驗證其結構
    assert isinstance(individual, dict)
    assert "strategy_name" in individual
    assert individual["strategy_name"] == "RSI_MeanReversion"
    assert "indicators" in individual and len(individual["indicators"]) == 1
    assert "params" in individual["indicators"][0]
    assert "window" in individual["indicators"][0]["params"]
    assert "entry_rules" in individual
    assert "exit_rules" in individual

def test_genome_mutation(genome_chamber):
    """驗證自定義的突變函數能否正確修改基因體字典。"""
    # 1. 創建一個原始個體
    original_individual = genome_chamber.toolbox.individual()
    # 創建一個深拷貝用於比較
    import copy
    individual_to_mutate = copy.deepcopy(original_individual)

    # 2. 執行突變
    mutated_individual, = mutate_genome(individual_to_mutate) # 返回的是元組

    # 3. 驗證結果
    # 至少有一個參數值應該與原始的不同
    original_params = (
        original_individual["indicators"][0]["params"]["window"],
        original_individual["entry_rules"][0]["value"],
        original_individual["exit_rules"][0]["value"]
    )
    mutated_params = (
        mutated_individual["indicators"][0]["params"]["window"],
        mutated_individual["entry_rules"][0]["value"],
        mutated_individual["exit_rules"][0]["value"]
    )

    assert original_params != mutated_params, "突變後參數應與原始參數不同"
    assert isinstance(mutated_individual, dict), "突變後應保持字典結構"
