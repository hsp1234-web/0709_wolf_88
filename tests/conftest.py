import os
import sys

# 將專案根目錄添加到 sys.path
# __file__ 是 conftest.py 的路徑: /app/tests/conftest.py
# os.path.dirname(__file__) 是 /app/tests
# os.path.abspath(os.path.join(os.path.dirname(__file__), '..')) 是 /app (專案根目錄)
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, PROJECT_ROOT)

print(f"DEBUG: [tests/conftest.py] Added {PROJECT_ROOT} to sys.path")
print(f"DEBUG: [tests/conftest.py] Current sys.path: {sys.path}")

# 如果需要，可以在這裡定義全局的 fixtures 等
# 例如，如果 BaseAPIClient 需要 mock 的 session，可以在這裡統一定義
# import pytest
# from unittest.mock import MagicMock

# @pytest.fixture(scope="session", autouse=True) # autouse=True 會自動應用於所有測試
# def mock_global_requests_session():
#     """
#     如果 BaseAPIClient 或其子類在初始化時就發起網路請求，
#     或者為了避免任何真實網路調用，可以全局 mock requests.Session。
#     但更常見的做法是針對性地 mock client 實例的 _session.get 或 _session.post。
#     """
#     # from requests import Session
#     # original_session_get = Session.get
#     # Session.get = MagicMock(return_value=MagicMock(status_code=503, text="Global mock: Service Unavailable"))
#     # yield
#     # Session.get = original_session_get # 還原
#     pass
