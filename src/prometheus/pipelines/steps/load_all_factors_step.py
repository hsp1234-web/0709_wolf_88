# -*- coding: utf-8 -*-
import pandas as pd
import duckdb
from prometheus.core.pipelines.base_step import BaseStep
from prometheus.core.config import config

class LoadAllFactorsStep(BaseStep):
    """
    從 factors.duckdb 載入所有可用的因子。
    """

    async def run(self, data, context):
        """
        執行載入步驟。

        :param data: 上一個步驟的數據。
        :param context: 管線上下文。
        """
        db_path = config.get('database.main_db_path')
        with duckdb.connect(db_path) as con:
            all_factors = con.execute("SELECT * FROM factors").fetchdf()
            all_factors['date'] = pd.to_datetime(all_factors['date'])
            all_factors = all_factors.set_index('date')
            context['all_factors'] = all_factors
        return data
