import unittest
from unittest.mock import MagicMock
import pandas as pd
from datetime import datetime
import statistics # Required for mean if not mocked

# Path adjustments
import sys
import os
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(current_dir, '..', '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from apps.daily_market_analyzer.report_generator import ReportGenerator
from apps.daily_market_analyzer.analysis_engine import AnalysisEngine # For mocking

class TestReportGeneratorHardware(unittest.TestCase):

    def setUp(self):
        self.mock_analysis_engine = MagicMock(spec=AnalysisEngine)
        self.sample_execution_log = {
            "2023-01-01": { "AAPL": {"status": "success", "interval": "1d", "count": 1, "message": "OK"}}
        }
        self.report_time = datetime(2023, 1, 2, 10, 0, 0)
        self.start_date = "2023-01-01"
        self.end_date = "2023-01-01"

    def test_generate_hardware_summary_md_with_data(self):
        hardware_stats = [
            {"timestamp": "t1", "stage": "s1", "cpu_percent": 10.0, "ram_percent": 20.0},
            {"timestamp": "t2", "stage": "s2", "cpu_percent": 30.0, "ram_percent": 40.0},
        ]
        csv_path = "mock_path/hardware_report.csv"
        reporter = ReportGenerator(
            execution_log=self.sample_execution_log,
            analysis_engine_instance=self.mock_analysis_engine,
            hardware_stats=hardware_stats,
            hardware_report_csv_path=csv_path
        )
        summary_md = reporter._generate_hardware_summary_md()

        self.assertIn("硬體資源使用情況摘要", summary_md)
        self.assertIn("CPU 使用率**: 平均 20.00%", summary_md)
        self.assertIn("峰值: 30.00%", summary_md)
        self.assertIn("記憶體使用率**: 平均 30.00%", summary_md)
        self.assertIn("峰值: 40.00%", summary_md)
        self.assertIn(f"`{csv_path}`", summary_md)

    def test_generate_hardware_summary_md_no_data(self):
        reporter = ReportGenerator(
            execution_log=self.sample_execution_log,
            analysis_engine_instance=self.mock_analysis_engine,
            hardware_stats=[], # No stats
            hardware_report_csv_path=None
        )
        summary_md = reporter._generate_hardware_summary_md()
        self.assertIn("本次執行未記錄詳細硬體監控數據", summary_md)

    def test_generate_hardware_summary_md_missing_keys_in_stats(self):
        hardware_stats = [
            {"timestamp": "t1", "stage": "s1", "cpu_percent": 10.0}, # RAM missing
            {"timestamp": "t2", "stage": "s2", "ram_percent": 40.0}, # CPU missing
        ]
        reporter = ReportGenerator(
            execution_log=self.sample_execution_log,
            analysis_engine_instance=self.mock_analysis_engine,
            hardware_stats=hardware_stats,
            hardware_report_csv_path="path.csv"
        )
        summary_md = reporter._generate_hardware_summary_md()
        self.assertIn("CPU 使用率**: 平均 10.00%", summary_md)
        self.assertIn("記憶體使用率**: 平均 40.00%", summary_md)


    def test_full_report_includes_hardware_summary(self):
        hardware_stats = [{"timestamp": "t1", "stage": "s1", "cpu_percent": 10.0, "ram_percent": 20.0}]
        csv_path = "final_hw_report.csv"
        reporter = ReportGenerator(
            execution_log=self.sample_execution_log,
            analysis_engine_instance=self.mock_analysis_engine,
            hardware_stats=hardware_stats,
            hardware_report_csv_path=csv_path
        )
        full_report = reporter.generate_full_report(
            overall_start_date_str=self.start_date,
            overall_end_date_str=self.end_date,
            report_generation_time=self.report_time,
            task_duration_seconds=10.0,
            target_tickers=["AAPL"],
            db_table_name="test_table"
        )
        self.assertIn("硬體資源使用情況摘要", full_report)
        self.assertIn(f"`{csv_path}`", full_report)

if __name__ == '__main__':
    unittest.main()
