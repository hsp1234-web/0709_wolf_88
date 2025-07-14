# 專案檔案詞彙表

本文件詳細說明專案中每個檔案的功能與用途。

## 檔案結構樹

```
.:
PROJECT_FILES_GLOSSARY.md
README.md
TEST_REPORT.md
_test_run.py
apps
archive_test.py
check_qsize.py
config.yml
core
latest_structure.txt
mypy.ini
output
pipeline_test_loader.duckdb
pipelines
poetry.lock
prometheus_fire.duckdb
pyproject.toml
pytest.ini
read_logs.py
run.py
run_pipeline.sh
run_show_results.py
run_tests.py
tests

archive_test.cpython-312-pytest-8.4.1.pyc

./apps:
__init__.py
analysis_pipeline
backtest_worker_app.py
backtesting_engine
dashboard
db_manager
evolution_app.py
factor_engine
optimizer_app.py
pipeline_metadata_manager
portfolio_optimizer
py.typed
query_gateway.py
report_generator
run_finmind_test.py
run_fmp_test.py
run_gold_layer.py
run_stress_index.py
run_taifex_prototype_test.py
tools
visualization

__init__.cpython-312.pyc
backtest_worker_app.cpython-312.pyc
evolution_app.cpython-312.pyc
optimizer_app.cpython-312.pyc
query_gateway.cpython-312.pyc
run_finmind_test.cpython-312-pytest-8.4.1.pyc
run_fmp_test.cpython-312.pyc
run_gold_layer.cpython-312.pyc
run_stress_index.cpython-312.pyc
run_taifex_prototype_test.cpython-312-pytest-8.4.1.pyc

./apps/analysis_pipeline:
run.py

run.cpython-312.pyc

./apps/backtesting_engine:
__init__.py
engine.py
run.py

__init__.cpython-312.pyc
engine.cpython-312.pyc
run.cpython-312.pyc

./apps/dashboard:
dashboard.html

./apps/db_manager:
setup_database.py

setup_database.cpython-312.pyc

./apps/factor_engine:
engine.py
run_factor_etl.py
sma_crossover_factor.py

engine.cpython-312.pyc
run_factor_etl.cpython-312.pyc
sma_crossover_factor.cpython-312.pyc

./apps/pipeline_metadata_manager:
__init__.py
manager.py

__init__.cpython-312.pyc
manager.cpython-312.pyc

./apps/portfolio_optimizer:
__init__.py
main.py

__init__.cpython-312.pyc
main.cpython-312.pyc

./apps/report_generator:
__init__.py
generator.py
run.py

__init__.cpython-312.pyc
generator.cpython-312.pyc
run.cpython-312.pyc

./apps/tools:
clear_results.py
report_generator_app.py
show_results.py
task_adder_app.py

clear_results.cpython-312.pyc
report_generator_app.cpython-312.pyc
show_results.cpython-312.pyc
task_adder_app.cpython-312.pyc

./apps/visualization:
plot_sma_crossover.py

plot_sma_crossover.cpython-312.pyc

./core:
__init__.py
analysis
analyzers
clients
config.py
constants.py
db
engines
logger.py
pipelines
py.typed
queue
services
utils

__init__.cpython-312.pyc
config.cpython-312.pyc
constants.cpython-312.pyc
logger.cpython-312.pyc

./core/analysis:
data_engine.py
stress_index.py

data_engine.cpython-312.pyc
stress_index.cpython-312.pyc

./core/analyzers:
__init__.py
base_analyzer.py

__init__.cpython-312.pyc
base_analyzer.cpython-312.pyc

./core/clients:
__init__.py
base.py
finmind.py
fmp.py
fred.py
nyfed.py
taifex_db.py
yfinance.py

__init__.cpython-312.pyc
base.cpython-312.pyc
finmind.cpython-312.pyc
fmp.cpython-312.pyc
fred.cpython-312.pyc
nyfed.cpython-312.pyc
taifex_db.cpython-312.pyc
yfinance.cpython-312.pyc

./core/db:
__init__.py
db_manager.py
results_saver.py

__init__.cpython-312.pyc
db_manager.cpython-312.pyc
results_saver.cpython-312.pyc

./core/engines:
__init__.py
robust_acquisition_engine.py

__init__.cpython-312.pyc
robust_acquisition_engine.cpython-312.pyc

./core/pipelines:
__init__.py
base_step.py
pipeline.py
steps

__init__.cpython-312.pyc
base_step.cpython-312.pyc
pipeline.cpython-312.pyc

./core/pipelines/steps:
__init__.py
aggregators.py
financial_steps.py
loaders.py

__init__.cpython-312.pyc
aggregators.cpython-312.pyc
financial_steps.cpython-312.pyc
loaders.cpython-312.pyc

./core/queue:
__init__.py
base.py
sqlite_queue.py

__init__.cpython-312.pyc
base.cpython-312.pyc
sqlite_queue.cpython-312.pyc

./core/services:
__init__.py
backtesting_service.py
evolution_chamber.py
optimizer_service.py

__init__.cpython-312.pyc
backtesting_service.cpython-312.pyc
evolution_chamber.cpython-312.pyc
optimizer_service.cpython-312.pyc

./core/utils:
__init__.py
caching.py
path_utils.py

__init__.cpython-312.pyc
caching.cpython-312.pyc
path_utils.cpython-312.pyc

./output:
logs
reports
test_integration_log.db
test_log_archive

./output/logs:
archive
session.sqlite
standalone_test.sqlite
test_evolution_pipeline.sqlite

./output/logs/archive:
battle_report_20250714_082411.txt
battle_report_20250714_082414.txt
battle_report_20250714_082423.txt
battle_report_20250714_082445.txt
battle_report_20250714_082513.txt
battle_report_20250714_082515.txt
battle_report_20250714_082521.txt
battle_report_20250714_082542.txt
battle_report_20250714_082558.txt
battle_report_20250714_082559.txt
battle_report_20250714_082605.txt
battle_report_20250714_082627.txt
battle_report_20250714_082653.txt
battle_report_20250714_082655.txt
battle_report_20250714_082701.txt
battle_report_20250714_082723.txt
battle_report_20250714_082805.txt
battle_report_20250714_082806.txt
battle_report_20250714_082813.txt
battle_report_20250714_082834.txt

./output/reports:
report.xml

./output/test_log_archive:

./pipelines:
__init__.py
p0_downloader
p1_explorer
p2_elt_pipeline
p3_backfill_hourly_data

__init__.cpython-312.pyc

./pipelines/p0_downloader:
run.py

run.cpython-312.pyc

./pipelines/p1_explorer:
__init__.py
run.py

__init__.cpython-312.pyc
run.cpython-312.pyc

./pipelines/p2_elt_pipeline:
run_elt.py

run_elt.cpython-312.pyc

./pipelines/p3_backfill_hourly_data:
run.py

./tests:
conftest.py
fixtures
ignition_test.py
integration
test_p0_downloader.py
test_p1_explorer.py
test_p2_elt_pipeline.py
unit

conftest.cpython-312-pytest-8.4.1.pyc
ignition_test.cpython-312-pytest-8.4.1.pyc
test_p0_downloader.cpython-312-pytest-8.4.1.pyc
test_p1_explorer.cpython-312-pytest-8.4.1.pyc
test_p2_elt_pipeline.cpython-312-pytest-8.4.1.pyc

./tests/fixtures:
corrupted.zip
no_data_response.html
sample_daily_ohlc_20250711.zip

./tests/integration:
analysis
apps
pipelines
test_evolution_pipeline.py
test_full_pipeline.py

test_evolution_pipeline.cpython-312-pytest-8.4.1.pyc
test_full_pipeline.cpython-312-pytest-8.4.1.pyc

./tests/integration/analysis:
test_data_engine_cache.py

test_data_engine_cache.cpython-312-pytest-8.4.1.pyc

./tests/integration/apps:
test_analysis_pipeline.py
test_refactored_apps.py

test_analysis_pipeline.cpython-312-pytest-8.4.1.pyc
test_refactored_apps.cpython-312-pytest-8.4.1.pyc

./tests/integration/pipelines:
test_data_pipeline.py
test_example_flow.py

test_data_pipeline.cpython-312-pytest-8.4.1.pyc
test_example_flow.cpython-312-pytest-8.4.1.pyc

./tests/unit:
analysis
core
test_feature_analyzer.py

test_feature_analyzer.cpython-312-pytest-8.4.1.pyc

./tests/unit/analysis:
test_data_engine.py

test_data_engine.cpython-312-pytest-8.4.1.pyc

./tests/unit/core:
analyzers
clients
test_queue.py

test_queue.cpython-312-pytest-8.4.1.pyc

./tests/unit/core/analyzers:
test_base_analyzer.py

test_base_analyzer.cpython-312-pytest-8.4.1.pyc

./tests/unit/core/clients:
test_finmind.py
test_fmp.py
test_fred.py
test_nyfed.py
test_yfinance.py

test_finmind.cpython-312-pytest-8.4.1.pyc
test_fmp.cpython-312-pytest-8.4.1.pyc
test_fred.cpython-312-pytest-8.4.1.pyc
test_nyfed.cpython-312-pytest-8.4.1.pyc
test_yfinance.cpython-312-pytest-8.4.1.pyc
```

---
## v0.8.0 新增/修改檔案 (演化引擎)

### `core/services` - 核心服務

-   `evolution_chamber.py`: **[新增]** 策略演化室。整合了 `DEAP` 遺傳演算法函式庫，負責管理策略族群的初始化、評估、選擇、交叉與突變，是整個系統自我進化的核心。
-   `optimizer_service.py`: **[歷史]** 單次優化器。作為演化室的前身，用於概念驗證，現已被功能更全面的 `EvolutionChamber` 取代。

### `apps` - 應用程式

-   `evolution_app.py`: **[新增]** `evolve` 命令的應用程式入口，負責初始化並啟動 `EvolutionChamber`。
-   `optimizer_app.py`: **[歷史]** `optimize` 命令的應用程式入口，現已被 `evolution_app.py` 取代。

### `tests/integration` - 整合測試

-   `test_evolution_pipeline.py`: **[新增]** 演化管線的輕量化邏輯驗證測試。透過模擬 (Mocking) 回測過程，專門驗證 `EvolutionChamber` 的核心演算法邏輯，確保其在任何環境下都能快速、穩定地通過驗證。
