# apps/finmind_client/client.py
import os
import requests
import pandas as pd
from io import StringIO
from datetime import datetime
from typing import Optional, Dict, Any

FINMIND_API_TOKEN = os.getenv("FINMIND_API_TOKEN")
BASE_URL = "https://api.finmindtrade.com/api/v4/data"

class FinMindClient:
    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or FINMIND_API_TOKEN
        if not self.api_token:
            raise ValueError("FinMind API token 未設定。請設定 FINMIND_API_TOKEN 環境變數或在初始化時傳入 api_token。")

    def _make_request(self, params: Dict[str, Any]) -> Optional[pd.DataFrame]:
        headers = {"Authorization": f"Bearer {self.api_token}"}
        try:
            params["token"] = self.api_token
            response = requests.get(BASE_URL, params=params, headers=headers)
            response.raise_for_status()
            if 'text/csv' in response.headers.get('Content-Type', ''):
                return pd.read_csv(StringIO(response.text))
            else:
                json_response = response.json()
                if json_response.get("status") != 200:
                    print(f"FinMind API 錯誤：{json_response.get('msg', '未知錯誤')}")
                    return None
                data_list = json_response.get("data")
                return pd.DataFrame(data_list) if data_list else pd.DataFrame()
        except requests.exceptions.RequestException as e:
            print(f"請求 FinMind API 時發生錯誤：{e}")
            return None
        except Exception as e:
            print(f"處理 FinMind API 回應時發生未知錯誤：{e}")
            return None

    def get_taiwan_stock_institutional_investors_buy_sell(self, data_id: str, start_date: str, end_date: Optional[str] = None) -> Optional[pd.DataFrame]:
        params = {
            "dataset": "TaiwanStockInstitutionalInvestorsBuySell",
            "data_id": data_id,
            "start_date": start_date,
            "end_date": end_date or datetime.now().strftime("%Y-%m-%d"),
        }
        return self._make_request(params)
