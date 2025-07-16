from prometheus.data_clients.fred_client import FredClient
from prometheus.core.engines.robust_acquisition_engine import RobustDataAcquisitionEngine
from prometheus.core.config import ConfigManager

import logging

logger = logging.getLogger(__name__)

class ClientFactory:
    def __init__(self):
        self.config = ConfigManager()._config
        self._clients = {}

    def get_client(self, client_name):
        logger.info(f"Attempting to get client for: {client_name}")
        if client_name not in self._clients:
            if client_name == "fred":
                logger.info("Getting fred client")
                api_key = self.config.get("api_keys", {}).get("fred")
                self._clients[client_name] = FredClient(api_key=api_key)
            elif client_name == "default":
                self._clients[client_name] = RobustDataAcquisitionEngine(tickers=self.config.get("auxiliary_tickers", {}).values())
            else:
                raise ValueError(f"Unknown client name: {client_name}")
        return self._clients[client_name]
