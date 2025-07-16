from typing import Dict

from ..config import config
from .base import BaseAPIClient
from .fred import FredClient
from .taifex_db import TaifexDBClient
from .yfinance import YFinanceClient


class ClientFactory:
    _clients: Dict[str, BaseAPIClient] = {}

    @classmethod
    def get_client(cls, client_name: str) -> BaseAPIClient:
        if client_name not in cls._clients:
            if client_name == "fred":
                cls._clients[client_name] = FredClient(api_key=config.get("api_keys.fred"))
            elif client_name == "yfinance":
                cls._clients[client_name] = YFinanceClient()
            elif client_name == "taifex":
                cls._clients[client_name] = TaifexDBClient()
            elif client_name == "finmind":
                from .finmind import FinMindClient
                cls._clients[client_name] = FinMindClient(api_token=config.get("api_keys.finmind"))
            else:
                raise ValueError(f"Unknown client: {client_name}")
        return cls._clients[client_name]

    @classmethod
    def close_all(cls):
        for client in cls._clients.values():
            client.close_session()
        cls._clients = {}
