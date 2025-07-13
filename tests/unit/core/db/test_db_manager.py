# tests/unit/core/db/test_db_manager.py
# ==============================================================================
#  單元測試：中央數據庫管理員
# ==============================================================================
import os
import pytest
import pandas as pd
from pathlib import Path
from src.core.db.db_manager import DBManager

@pytest.fixture
def test_db_manager():
    manager = DBManager(db_path=":memory:")
    manager.connect()
    yield manager
    manager.disconnect()

@pytest.fixture
def sample_df():
    return pd.DataFrame({"id": [1, 2, 3], "name": ["Alice", "Bob", "Charlie"]})

@pytest.fixture
def another_sample_df():
    return pd.DataFrame({"id": [4, 5], "name": ["David", "Eve"]})

def test_connection(test_db_manager: DBManager):
    assert test_db_manager._connection is not None
    test_db_manager.disconnect()
    assert test_db_manager._connection is None

def test_write_and_read_replace_mode(test_db_manager: DBManager, sample_df: pd.DataFrame):
    table_name = "test_table"
    test_db_manager.write_dataframe(sample_df, table_name, mode="replace")
    result_df = test_db_manager.read_sql(f"SELECT * FROM {table_name}")
    pd.testing.assert_frame_equal(result_df, sample_df, check_dtype=False)

def test_write_and_read_append_mode(test_db_manager: DBManager, sample_df: pd.DataFrame, another_sample_df: pd.DataFrame):
    table_name = "append_test_table"
    test_db_manager.write_dataframe(sample_df, table_name, mode="replace")
    test_db_manager.write_dataframe(another_sample_df, table_name, mode="append")
    result_df = test_db_manager.read_sql(f"SELECT * FROM {table_name}")
    expected_df = pd.concat([sample_df, another_sample_df], ignore_index=True)
    pd.testing.assert_frame_equal(result_df, expected_df, check_dtype=False)

def test_context_manager(sample_df: pd.DataFrame):
    with DBManager(db_path=":memory:") as manager:
        assert manager._connection is not None
        manager.write_dataframe(sample_df, "context_table")
    assert manager._connection is None
