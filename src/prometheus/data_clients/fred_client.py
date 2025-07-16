import asyncio
from fredapi import Fred

class FredClient:
    def __init__(self, api_key):
        self.fred = Fred(api_key=api_key)

    async def get_series(self, series_id, start_date=None, end_date=None):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.fred.get_series, series_id, start_date, end_date)
