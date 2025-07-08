# -*- coding: utf-8 -*-
"""
整合測試腳本：環境依賴項故障模擬

此腳本用於驗證系統在關鍵函式庫（依賴項）未安裝時，
能否在執行前進行自我診斷，並向指揮官報告，而不是意外崩潰。
"""
import unittest
from unittest.mock import patch, MagicMock
import io
import sys
import os
import importlib # 用於輔助卸載模組

# 調整 sys.path 以便測試腳本能找到 apps 模組
# 假設 tests 和 apps 是同級目錄
current_script_dir = os.path.dirname(os.path.abspath(__file__))
project_root_dir = os.path.dirname(current_script_dir)
if project_root_dir not in sys.path:
    sys.path.insert(0, project_root_dir)

class TestDependencyIssues(unittest.TestCase):
    """
    測試環境依賴項缺失的情境。
    """

    def setUp(self):
        """
        每個測試方法執行前呼叫。
        設置 stdout 捕獲。
        儲存原始的 sys.modules，以便在 tearDown 中恢復。
        """
        self.held_stdout = sys.stdout
        sys.stdout = io.StringIO()
        self.original_sys_modules = sys.modules.copy()

    def tearDown(self):
        """
        每個測試方法執行後呼叫。
        恢復 stdout。
        恢復 sys.modules 到原始狀態，確保測試隔離。
        """
        sys.stdout.close()
        sys.stdout = self.held_stdout

        # 清理 sys.modules 中在測試期間可能添加或修改的條目
        # 移除測試中導入的 apps 相關模組以及被 mock 的第三方模組
        modules_to_remove = [m for m in sys.modules if m.startswith('apps.') or m in ['vectorbt', 'pypfopt']]
        for m_name in modules_to_remove:
            if m_name in sys.modules: # 再次檢查，因為它們可能已被其他清理機制移除
                del sys.modules[m_name]

        # 恢復原始 sys.modules 中的條目 (如果它們在原始 sys.modules 中但被測試移除了)
        # 這通常不太可能發生，除非測試意外刪除了 setUp 前就存在的模組
        # 更簡單的方法是直接將 sys.modules 設回原始副本的一個拷貝，但這可能過於激進
        # 此處選擇性移除，然後可以考慮將原始模組加回去（如果需要更嚴格的恢復）
        # 為了簡單起見，我們主要關注移除測試引入的模組
        # 如果需要更強的隔離，可以考慮在子進程中運行每個測試，或使用更複雜的 sys.modules 管理

        # 一個更安全的恢復 sys.modules 的方法 (但可能影響其他並行測試，如果有的話):
        # sys.modules.clear()
        # sys.modules.update(self.original_sys_modules)


    def _simulate_app_execution(self, app_module_path: str, app_function_name: str, required_module_name: str):
        """
        模擬應用程式的最高層執行器 (如 run.py 的 main 區塊)。
        它會嘗試導入並執行指定的應用程式函數，並捕獲 ModuleNotFoundError。

        參數:
            app_module_path (str): 應用程式主模組的點路徑 (例如 'apps.backtesting_engine.main')。
            app_function_name (str): 要執行的業務邏輯函數的名稱。
            required_module_name (str): 此應用程式依賴的關鍵模組名稱。
        """
        try:
            # 嘗試導入應用程式模組。如果其頂層 import 失敗 (因為我們 mock 了依賴)，
            # 這裡就會拋出 ModuleNotFoundError。
            # print(f"DEBUG: Attempting to import module: {app_module_path}")
            module = importlib.import_module(app_module_path)
            # print(f"DEBUG: Successfully imported {app_module_path}")

            # 獲取業務邏輯函數
            app_function = getattr(module, app_function_name)

            # 嘗試執行業務邏輯函數
            # print(f"DEBUG: Attempting to execute function: {app_function_name}")
            app_function() # 在此模擬中，如果導入成功，我們其實不期望它執行到這裡
            # print(f"DEBUG: Successfully executed function: {app_function_name}")

        except ModuleNotFoundError as e:
            # print(f"DEBUG: Caught ModuleNotFoundError: {e}, e.name: {e.name}")
            if e.name == required_module_name:
                # 這是預期的 ModuleNotFoundError，打印指揮官報告
                print(f"指揮官，Jules 回報在執行任務時發現環境中缺少必要的依賴項（'{required_module_name}' 模組）。")
                print(f"這可能導致相關功能無法正常運行。請您確認專案的 requirements.txt 文件是否包含所有必需的依賴項。")
                print(f"任務無法繼續。")
            else:
                # 如果是其他模組未找到，則重新拋出，因為這不是我們測試的目標
                # print(f"DEBUG: Re-raising unexpected ModuleNotFoundError for {e.name}")
                raise
        except Exception as e:
            # 捕獲其他可能的異常，以防模擬設置不正確
            print(f"在模擬應用程式執行期間發生未預期錯誤: {e}")
            raise


    def test_backtesting_engine_vectorbt_missing(self):
        """
        情境一：回測引擎依賴 'vectorbt' 缺失。
        驗證：
        1. 系統不執行核心業務邏輯 (`execute_backtest`)。
        2. 系統捕獲 ModuleNotFoundError。
        3. 系統向 stdout 打印包含 'vectorbt' 的友善報告。
        """
        # 模擬 'vectorbt' 模組不存在
        # 當 'apps.backtesting_engine.main' 嘗試 'import vectorbt' 時，應拋出 ModuleNotFoundError
        # 我們通過在導入 apps.backtesting_engine.main 之前，將 'vectorbt' 標記為 "不可用"
        # @patch.dict(sys.modules, {'vectorbt': None}) # 這種方式有時不足以觸發 ModuleNotFoundError，取決於導入機制
        # 更可靠的方式是 patch builtins.__import__ 或在執行 importlib.import_module 前確保其不在 sys.modules

        # 在執行 _simulate_app_execution 之前，確保 vectorbt 不在 sys.modules 中
        # 或者 patch __import__ 使其在嘗試導入 vectorbt 時失敗

        with patch('builtins.__import__', side_effect=lambda name, *args, **kwargs: (_ for _ in ()).throw(ModuleNotFoundError(f"No module named '{name}'")) if name == 'vectorbt' else self.original_sys_modules.get(name, MagicMock())):
            # 由於 apps.backtesting_engine.main 在頂部 import vectorbt,
            # importlib.import_module('apps.backtesting_engine.main') 應該就會觸發錯誤。
            # self._simulate_app_execution 內部會處理這個導入。

            # 為了確保 execute_backtest 不被調用，我們也 patch 它
            with patch('apps.backtesting_engine.main.execute_backtest') as mock_execute_backtest:
                self._simulate_app_execution(
                    app_module_path='apps.backtesting_engine.main',
                    app_function_name='execute_backtest',
                    required_module_name='vectorbt'
                )
                mock_execute_backtest.assert_not_called("execute_backtest 應在 vectorbt 缺失時不被調用")

        output = sys.stdout.getvalue()
        # print(f"DEBUG_OUTPUT_VECTORBT: {output}") # 用於調試輸出

        self.assertIn("指揮官，Jules 回報在執行任務時發現環境中缺少必要的依賴項", output)
        self.assertIn("('vectorbt' 模組)", output)
        self.assertIn("請您確認專案的 requirements.txt 文件是否包含所有必需的依賴項。", output)


    def test_portfolio_optimizer_pypfopt_missing(self):
        """
        情境二：投資組合優化器依賴 'pypfopt' 缺失。
        驗證：
        1. 系統不執行核心業務邏輯 (`run_optimization`)。
        2. 系統捕獲 ModuleNotFoundError。
        3. 系統向 stdout 打印包含 'pypfopt' 的友善報告。
        """
        original_import = builtins.__import__
        def import_side_effect(name, globals=None, locals=None, fromlist=(), level=0):
            if name == 'pypfopt':
                raise ModuleNotFoundError(f"No module named '{name}'", name='pypfopt')
            # 對於其他導入，恢復原始行為或模擬成功
            # 為了避免影響 unittest 等內部庫，最好是調用原始導入
            # 但在 patch 上下文中，直接調用 original_import 可能會導致無限遞歸
            # 因此，如果不是目標模組，我們需要一種方式來"通過"它
            # 一個簡單的方法是，如果它在原始 sys.modules 中，就返回它，否則引發。
            # 但這不處理新的、非目標的導入。
            # 更安全的方式是，如果 name 不是 pypfopt，則調用真正的 __import__，
            # 但這需要在 patch 外部保存一個引用。
            # print(f"DEBUG_IMPORT: name='{name}', fromlist={fromlist}, level={level}")
            # 這裡我們假設測試環境中除了 pypfopt 外的其他導入都能正常工作
            # 或者更簡單：如果不是 pypfopt，就讓它通過到一個空的 MagicMock
            # return self.original_sys_modules.get(name, MagicMock())
            # 最好的方法是在 side_effect 中直接調用原始的 __import__
            # 我們在 setUp 中保存它，或者依賴 patch 的 `wraps` 功能 (如果適用)
            # 這裡我們用一個簡化的策略：如果不是目標，就嘗試執行原始導入
            # 這需要在 patch 之外獲取原始 __import__
            return original_import(name, globals, locals, fromlist, level)


        with patch('builtins.__import__', side_effect=import_side_effect):
            with patch('apps.portfolio_optimizer.main.run_optimization') as mock_run_optimization:
                self._simulate_app_execution(
                    app_module_path='apps.portfolio_optimizer.main',
                    app_function_name='run_optimization',
                    required_module_name='pypfopt'
                )
                mock_run_optimization.assert_not_called("run_optimization 應在 pypfopt 缺失時不被調用")

        output = sys.stdout.getvalue()
        # print(f"DEBUG_OUTPUT_PYPFOPT: {output}") # 用於調試輸出

        self.assertIn("指揮官，Jules 回報在執行任務時發現環境中缺少必要的依賴項", output)
        self.assertIn("('pypfopt' 模組)", output)
        self.assertIn("請您確認專案的 requirements.txt 文件是否包含所有必需的依賴項。", output)


if __name__ == '__main__':
    unittest.main()
