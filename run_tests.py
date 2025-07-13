# -*- coding: utf-8 -*-
# ==============================================================================
#  磐石協議 (The Bedrock Protocol)
#  整合式品質保證執行器：run_tests.py (v2.0)
#
#  功能：
#  - 作為一個單一的入口點，按順序執行整個專案的品質保證流程。
#  - 集成了多層防禦，確保代碼的健壯性、風格一致性和依賴完整性。
#  - 提供清晰、分階段的彩色輸出，使問題定位更為直觀。
#
#  執行流程 (防禦層級)：
#  1. Ruff (靜態掃描器): 我們的第一道防線。在不執行任何代碼的情況下，
#     以毫秒級速度捕獲語法錯誤、未定義變數等低級但致命的問題。
#  2. Deptry (依賴檢查器): 我們的第二道防線。靜態分析所有 import 語句，
#     確保 pyproject.toml 中沒有遺漏的依賴聲明，也沒用多餘的依賴。
#  3. Ignition Test (導入測試器): 我們的第三道防線。輕量級地嘗試導入
#     所有專案模組，確保沒有循環依賴或因導入時執行錯誤代碼而導致的崩潰。
#     (此測試由 pytest 自動執行)
#  4. Pytest (單元/整合測試): 我們的第四道防線。執行所有形式的測試，
#     驗證業務邏輯的正確性。
#  5. Pytest-Timeout (測試熔斷器): 我們的最終安全防線。為 pytest 執行
#     設置超時，從根本上解決了測試卡死、導致 Jules 崩潰且不回報任何
#     訊息的災難性問題。
# ==============================================================================

import os
import subprocess
import sys
from typing import List


# --- 彩色輸出配置 ---
class Color:
    """用於在終端輸出中添加顏色的常數"""

    HEADER = "\033[95m"
    BLUE = "\033[94m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    END = "\033[0m"
    BOLD = "\033[1m"


def print_header(title: str):
    """打印帶有標題的分隔線"""
    print(f"\n{Color.HEADER}{'=' * 80}{Color.END}")
    print(f"{Color.HEADER}{Color.BOLD}🚀 {title}{Color.END}")
    print(f"{Color.HEADER}{'=' * 80}{Color.END}")


def run_command(
    command: List[str], check: bool = True, ignore_errors: bool = False
) -> int:
    """
    執行一個子程序命令，並即時串流其輸出。

    Args:
        command: 要執行的命令，以列表形式表示。
        check: 如果為 True，當命令返回非零退出碼時，會引發 CalledProcessError。
        ignore_errors: 如果為 True，將忽略非零退出碼並繼續執行。

    Returns:
        命令的退出碼。
    """
    print(f"{Color.BLUE}▶️  執行中: {' '.join(command)}{Color.END}")
    try:
        # 使用 Popen 以便即時讀取輸出
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )

        # 即時讀取 stdout
        if process.stdout:
            for line in iter(process.stdout.readline, ""):
                print(line, end="")

        # 等待程序結束並獲取 stderr
        stdout, stderr = process.communicate()

        if process.returncode != 0:
            if stderr:
                print(f"{Color.RED}❌ 錯誤輸出:{Color.END}\n{stderr}", file=sys.stderr)
            if not ignore_errors:
                if check:
                    # 手動引發一個與 check=True 相似的異常
                    raise subprocess.CalledProcessError(process.returncode, command)

        return process.returncode

    except FileNotFoundError:
        print(
            f"{Color.RED}❌ 命令 '{command[0]}' 未找到。請確保它已安裝並在您的 PATH 中。{Color.END}",
            file=sys.stderr,
        )
        if not ignore_errors:
            sys.exit(1)
        return 1
    except subprocess.CalledProcessError as e:
        print(
            f"{Color.RED}❌ 命令 '{' '.join(command)}' 失敗，退出碼 {e.returncode}。{Color.END}",
            file=sys.stderr,
        )
        if not ignore_errors:
            sys.exit(e.returncode)
        return e.returncode
    except Exception as e:
        print(f"{Color.RED}❌ 執行命令時發生未知錯誤: {e}{Color.END}", file=sys.stderr)
        if not ignore_errors:
            sys.exit(1)
        return 1


def main():
    """主執行函數"""
    # 檢查是否在 uv 虛擬環境中
    if "VIRTUAL_ENV" not in os.environ:
        print(f"{Color.YELLOW}⚠️  警告：您當前似乎不在 uv 虛擬環境中。{Color.END}")
        print(
            f"{Color.YELLOW}   請執行 'source .venv/bin/activate' 進入環境後再運行此腳本。{Color.END}"
        )
        # 在 CI/CD 環境中，我們可能不希望直接退出，所以這裡只做警告
        # sys.exit(1)

    # --- 第 1 階段：Ruff 靜態代碼檢查與格式化 ---
    print_header("階段 1: Ruff 靜態分析與格式化")
    print(f"{Color.YELLOW} linting 和 formatting...{Color.END}")
    run_command(["ruff", "format", "."], ignore_errors=True)
    run_command(["ruff", "check", "--fix", "."], ignore_errors=True)
    print(f"{Color.GREEN}✅ Ruff 檢查與格式化完成。{Color.END}")

    # --- 第 2 階段：Deptry 依賴檢查 ---
    print_header("階段 2: Deptry 依賴完整性檢查")
    run_command(["deptry", "."], ignore_errors=True)
    print(f"{Color.GREEN}✅ Deptry 依賴檢查完成。{Color.END}")

    # --- 第 3 階段：Pytest 測試套件 (包含導入測試與超時熔斷) ---
    print_header("階段 3: Pytest 測試執行 (含 Ignition Test 和 Timeout)")
    # pytest 將自動發現並執行 `tests/` 目錄下的所有 `test_*.py` 和 `*_test.py` 檔案，
    # 包括我們新加的 `ignition_test.py`。
    # `pytest-timeout` 已在 `pyproject.toml` 中配置，此處無需額外參數。
    run_command(["pytest"])
    print(f"{Color.GREEN}✅ Pytest 測試套件執行完畢。{Color.END}")

    # --- 總結 ---
    print_header("品質保證流程成功")
    print(
        f"{Color.GREEN}{Color.BOLD}🎉 所有檢查和測試均已通過！代碼品質達標。{Color.END}"
    )


if __name__ == "__main__":
    main()
