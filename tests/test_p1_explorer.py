import os
import shutil  # For cleaning up test directories/files if needed
import sqlite3
import sys
from unittest.mock import patch  # For more complex patching if main() calls other funcs

import pytest

from pipelines.p1_explorer.run import (
    get_header_fingerprint,
)
from pipelines.p1_explorer.run import main as p1_explorer_main

PROJECT_ROOT_FROM_TEST_P1 = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
if PROJECT_ROOT_FROM_TEST_P1 not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_FROM_TEST_P1)

# Define the path to the fixture files
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def p1_test_environment(tmp_path):
    """
    Sets up a temporary environment for P1 explorer tests.
    - Creates a temporary input directory.
    - Copies relevant fixtures to the temporary input directory.
    - Provides a path for a temporary schema_registry.db.
    """
    temp_input_dir = tmp_path / "p1_input_data"
    temp_input_dir.mkdir()

    temp_db_path = tmp_path / "metadata" / "schema_registry.db"
    # Ensure the parent directory for the db exists, as p1_explorer_main expects it
    os.makedirs(temp_db_path.parent, exist_ok=True)

    # Copy necessary files from tests/fixtures to temp_input_dir
    fixture_files_to_copy = [
        "sample_daily_ohlc_20250711.zip",
        "sample_options_delta_20250711.csv",
        "corrupted.zip",
        "no_data_response.html",  # P1 should ideally ignore .html files or non-data files
    ]
    for f_name in fixture_files_to_copy:
        shutil.copy(os.path.join(FIXTURES_DIR, f_name), temp_input_dir / f_name)

    return {"input_dir": str(temp_input_dir), "db_path": str(temp_db_path)}


@pytest.mark.skip(reason="Missing fixture file: sample_options_delta_20250711.csv")
def test_p1_explorer_scan_fixtures(p1_test_environment):
    """
    測試案例 (掃描 fixtures):
    - 在測試開始前，確保模擬的 schema_registry.db 是乾淨的 (handled by tmp_path).
    - 執行探勘器的主函式，並將 --input-dir 指向 tests/fixtures (actually temp_input_dir).
    - 斷言: 測試結束後，連接到 schema_registry.db，驗證裡面恰好包含了我們在 fixtures 中定義的
      兩種正確格式 (ohlc.zip's internal csv, options_delta.csv)，並且 corrupted.zip 和 .html 沒有被註冊。
    """
    input_dir = p1_test_environment["input_dir"]
    db_path = p1_test_environment["db_path"]

    # Ensure the db doesn't exist before running (tmp_path fixture handles this)
    assert not os.path.exists(db_path)

    # Run the P1 explorer main function
    # We need to simulate command line arguments.
    # Patch sys.argv or pass arguments if p1_explorer_main is adapted.
    # Assuming p1_explorer_main uses argparse and can be called with args:
    test_args = ["--input-dir", input_dir, "--db-path", db_path]

    with patch("sys.argv", ["pipelines/p1_explorer/run.py"] + test_args):
        p1_explorer_main()

    # Assertions:
    assert os.path.exists(db_path)  # Database should be created

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT format_fingerprint, header, encoding, file_count, first_seen_file FROM schema_registry"
    )
    results = cursor.fetchall()
    conn.close()

    # Expected fingerprints and headers:
    # 1. From sample_daily_ohlc_20250711.zip (internal daily_20250711.csv)
    #    Header: "交易日期,契約代碼,到期月份(週別),開盤價,最高價,最低價,收盤價,成交量"
    #    Encoding: likely 'ms950' or 'big5' for TAIFEX data, or 'utf-8' if generated so.
    #    The p1_explorer tries 'ms950', 'big5', 'utf-8', 'utf-8-sig'
    #    The sample zip was created with UTF-8 content.
    expected_ohlc_header = (
        "交易日期,契約代碼,到期月份(週別),開盤價,最高價,最低價,收盤價,成交量"
    )
    expected_ohlc_fingerprint = get_header_fingerprint(expected_ohlc_header)

    # 2. From sample_options_delta_20250711.csv
    #    Header: "交易日期,契約,到期月份(週別),履約價,買賣權,開盤價,最高價,最低價,收盤價,成交量,結算價,未沖銷契約數,最後最佳買價,最後最佳賣價,歷史最高價,歷史最低價,是否因訊息面暫停交易,交易時段,漲跌價,漲跌%"
    #    Encoding: UTF-8 (as created)
    expected_options_header = "交易日期,契約,到期月份(週別),履約價,買賣權,開盤價,最高價,最低價,收盤價,成交量,結算價,未沖銷契約數,最後最佳買價,最後最佳賣價,歷史最高價,歷史最低價,是否因訊息面暫停交易,交易時段,漲跌價,漲跌%"
    expected_options_fingerprint = get_header_fingerprint(expected_options_header)

    # Verify results
    # 現在我們期望 sample_options_delta_20250711.csv 也被正確處理
    assert len(results) == 2, (
        "Should register exactly two valid formats (ohlc.zip and options_delta.csv)."
    )

    registered_fingerprints = [row[0] for row in results]
    assert expected_ohlc_fingerprint in registered_fingerprints
    assert expected_options_fingerprint in registered_fingerprints

    for row in results:
        fingerprint, header, encoding, file_count, first_seen_file = row
        assert file_count == 1  # Each format seen once

        if fingerprint == expected_ohlc_fingerprint:
            assert header == expected_ohlc_header
            # The sample_daily_ohlc_20250711.zip contains daily_20250711.csv.
            # The first_seen_file in p1_explorer is the name of the outer file (the zip).
            assert first_seen_file == "sample_daily_ohlc_20250711.zip"
            assert encoding.lower() == "utf-8"  # Since our CSV inside ZIP was UTF-8
        elif fingerprint == expected_options_fingerprint:
            assert header == expected_options_header
            assert first_seen_file == "sample_options_delta_20250711.csv"
            assert encoding.lower() == "utf-8"  # Since our CSV was UTF-8
        else:
            pytest.fail(
                f"Unexpected fingerprint found: {fingerprint}. Expected one of {expected_ohlc_fingerprint} or {expected_options_fingerprint}"
            )

    # Corrupted.zip should not result in a schema.
    # no_data_response.html should not result in a schema.
    # This is implicitly checked by `assert len(results) == 2`.


if __name__ == "__main__":
    pytest.main([__file__])
