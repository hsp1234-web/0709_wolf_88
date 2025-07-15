import os
import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

PROJECT_ROOT_FROM_TEST_P1 = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT_FROM_TEST_P1) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT_FROM_TEST_P1))

from src.prometheus.pipelines.p1_explorer import (
    get_header_fingerprint,
    run_explorer as p1_explorer_main,
    prospect_file_content,
)

FIXTURES_DIR = PROJECT_ROOT_FROM_TEST_P1 / "tests" / "fixtures"


@pytest.fixture(scope="function")
def p1_test_environment(tmp_path):
    temp_input_dir = tmp_path / "downloads"
    temp_metadata_dir = tmp_path / "metadata"
    temp_input_dir.mkdir()
    temp_metadata_dir.mkdir()
    db_path = temp_metadata_dir / "schema_registry.db"

    fixture_files_to_copy = [
        "sample_daily_ohlc_20250711.zip",
        "corrupted.zip",
        "no_data_response.html",
    ]
    for f_name in fixture_files_to_copy:
        shutil.copy(FIXTURES_DIR / f_name, temp_input_dir / f_name)

    yield {"input_dir": str(temp_input_dir), "db_path": str(db_path)}


def test_p1_explorer_end_to_end(p1_test_environment):
    input_dir = p1_test_environment["input_dir"]
    db_path = p1_test_environment["db_path"]

    p1_explorer_main(input_dir=input_dir, db_path=db_path)

    assert os.path.exists(db_path)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT format_fingerprint, header, encoding, file_count, first_seen_file FROM schema_registry"
    )
    results = cursor.fetchall()
    conn.close()

    assert len(results) == 1

    fingerprint_map = {res[0]: res[1:] for res in results}

    expected_ohlc_header = "交易日期,契約代碼,到期月份(週別),開盤價,最高價,最低價,收盤價,成交量"

    expected_ohlc_fingerprint = get_header_fingerprint(expected_ohlc_header)

    assert expected_ohlc_fingerprint in fingerprint_map

    for fingerprint, details in fingerprint_map.items():
        header, encoding, file_count, first_seen_file = details
        if fingerprint == expected_ohlc_fingerprint:
            assert header.replace('"', "") == expected_ohlc_header
            assert first_seen_file == "sample_daily_ohlc_20250711.zip"
            assert encoding.lower() == "utf-8"
            assert file_count == 1
        else:
            pytest.fail(
                f"Unexpected fingerprint {fingerprint} found in schema registry."
            )
