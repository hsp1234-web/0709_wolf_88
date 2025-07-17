import os

# Add project root to sys.path to allow imports from pipelines
import sys
from unittest.mock import MagicMock

import pytest
import requests

PROJECT_ROOT_FROM_TEST_P0 = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..")
)
if PROJECT_ROOT_FROM_TEST_P0 not in sys.path:
    sys.path.insert(0, PROJECT_ROOT_FROM_TEST_P0)

from prometheus.cli.main import execute_download

# Define the path to the fixture files
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


@pytest.fixture
def mock_session():
    """Fixture to create a mock requests.Session."""
    return MagicMock(spec=requests.Session)


def test_execute_download_success(mock_session, tmp_path):
    """
    測試案例一 (成功情境):
    模擬 requests.post 回傳 sample_daily_ohlc_20250711.zip 的位元組內容。
    執行下載器函式。
    斷言 (Assert): 驗證目標路徑下是否成功創建了檔案，且檔案內容與我們的模擬位元組完全一致。
    """
    zip_fixture_path = os.path.join(FIXTURES_DIR, "sample_daily_ohlc_20250711.zip")
    with open(zip_fixture_path, "rb") as f:
        zip_content_bytes = f.read()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = zip_content_bytes
    mock_response.text = ""  # No "查無資料"

    # Assuming the downloader uses session.post for this type of task
    mock_session.post.return_value = mock_response

    task_info = {
        "url": "http://fakeurl.com/Daily_2025_07_11.zip",
        "file_name": "Daily_2025_07_11.zip",  # Target filename
        "min_delay": 0,  # No delay for test
        "max_delay": 0,
        "payload": {"key": "value"},  # Assuming POST request
    }
    output_dir = str(tmp_path)

    status, message = execute_download(mock_session, task_info, output_dir)

    assert status == "success"
    expected_file_path = os.path.join(output_dir, task_info["file_name"])
    assert os.path.exists(expected_file_path)
    with open(expected_file_path, "rb") as f_downloaded:
        assert f_downloaded.read() == zip_content_bytes

    mock_session.post.assert_called_once()


def test_execute_download_not_found(mock_session, tmp_path):
    """
    測試案例二 (失敗情境 - 404 Not Found):
    模擬 requests.get 回傳 404 狀態碼。
    執行下載器函式。
    斷言 (Assert): 驗證函式是否回傳了 not_found 狀態，並且沒有在本地創建任何檔案。
    """
    mock_response = MagicMock()
    mock_response.status_code = 404

    # Assuming the downloader might use session.get if no payload
    mock_session.get.return_value = mock_response

    task_info = {
        "url": "http://fakeurl.com/nonexistent.zip",
        "file_name": "nonexistent.zip",
        "min_delay": 0,
        "max_delay": 0,
        # No payload, so execute_download might use GET
    }
    output_dir = str(tmp_path)

    status, message = execute_download(mock_session, task_info, output_dir)

    assert status == "not_found"
    expected_file_path = os.path.join(output_dir, task_info["file_name"])
    assert not os.path.exists(expected_file_path)
    mock_session.get.assert_called_once()  # or post, depending on logic


def test_execute_download_no_data_response(mock_session, tmp_path):
    """
    測試案例三 (失敗情境 - 查無資料):
    模擬 requests.post 回傳 tests/fixtures/no_data_response.html 的位元組內容。
    模擬 response.status_code = 200 和 response.text = "查無資料".
    執行下載器函式。
    斷言函式回傳 'error' 或類似的失敗狀態，且沒有創建任何檔案。
    """
    html_fixture_path = os.path.join(FIXTURES_DIR, "no_data_response.html")
    with open(html_fixture_path, "rb") as f:
        html_content_bytes = f.read()

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = html_content_bytes
    mock_response.text = "查無資料"  # Key part of the condition in execute_download

    # Assuming a POST request for this scenario
    mock_session.post.return_value = mock_response

    task_info = {
        "url": "http://fakeurl.com/find_nothing_here",
        "file_name": "find_nothing_here.html",
        "min_delay": 0,
        "max_delay": 0,
        "payload": {"query": "data"},  # Assuming POST
    }
    output_dir = str(tmp_path)

    status, message = execute_download(mock_session, task_info, output_dir)

    # Based on execute_download logic:
    # "查無資料" in response.text with status 200 leads to 'error'
    assert status == "error"
    assert "伺服器錯誤 200" in message  # Check specific message if possible
    expected_file_path = os.path.join(output_dir, task_info["file_name"])
    assert not os.path.exists(expected_file_path)
    mock_session.post.assert_called_once()


def test_execute_download_file_already_exists(mock_session, tmp_path):
    """
    測試檔案已存在的情境。
    """
    task_info = {
        "url": "http://fakeurl.com/Daily_2025_07_11.zip",
        "file_name": "Daily_2025_07_11.zip",
        "min_delay": 0,
        "max_delay": 0,
    }
    output_dir = str(tmp_path)
    # Create the file beforehand
    existing_file_path = os.path.join(output_dir, task_info["file_name"])
    os.makedirs(output_dir, exist_ok=True)
    with open(existing_file_path, "w") as f:
        f.write("dummy content")

    status, message = execute_download(mock_session, task_info, output_dir)

    assert status == "exists"
    assert f"檔案已存在: {task_info['file_name']}" in message
    # Ensure no network call was made
    mock_session.post.assert_not_called()
    mock_session.get.assert_not_called()


def test_execute_download_request_exception(mock_session, tmp_path):
    """
    測試 requests.exceptions.RequestException 的情境 (重試後依然失敗)。
    """
    # Simulate a requests.exceptions.RequestException on post/get
    mock_session.post.side_effect = requests.exceptions.RequestException(
        "Test network error"
    )
    # Also mock get if it could be called
    mock_session.get.side_effect = requests.exceptions.RequestException(
        "Test network error"
    )

    task_info = {
        "url": "http://fakeurl.com/network_error_target.zip",
        "file_name": "network_error_target.zip",
        "min_delay": 0,
        "max_delay": 0,
        "payload": {"data": "somepayload"},  # To ensure POST is tried
    }
    output_dir = str(tmp_path)

    status, message = execute_download(mock_session, task_info, output_dir)

    assert status == "error"
    assert (
        "網路請求失敗" in message
    )  # Or "達到最大重試次數" depending on how many times side_effect is called
    expected_file_path = os.path.join(output_dir, task_info["file_name"])
    assert not os.path.exists(expected_file_path)

    # execute_download retries 3 times
    assert mock_session.post.call_count == 3
    # assert mock_session.get.call_count == 3 # if get is also an option


# To make this test file runnable with `python tests/test_p0_downloader.py` for quick checks (optional)
if __name__ == "__main__":
    pytest.main([__file__])
