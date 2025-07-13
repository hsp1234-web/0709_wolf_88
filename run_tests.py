import os
import subprocess
import sys


def run_command(command, check=True):
    """
    執行一個命令，印出其實時輸出，並返回其成功狀態。
    """
    print(f"--- 執行中: {' '.join(command)} ---")
    try:
        # 使用 Popen 進行即時輸出
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding='utf-8',
            bufsize=1
        )

        # 讀取並印出每一行輸出
        for line in iter(process.stdout.readline, ''):
            print(line, end='')

        process.stdout.close()
        return_code = process.wait()

        if return_code != 0:
            print(f"--- 命令執行失敗，返回碼: {return_code} ---")
            return False

        print("--- 命令執行成功 ---")
        return True

    except FileNotFoundError:
        print(f"錯誤: 命令 '{command[0]}' 未找到。請確保 uv 已安裝並在 PATH 中。")
        return False
    except Exception as e:
        print(f"執行命令時發生未知錯誤: {e}")
        return False

def main():
    """
    執行完整的品質保證流程，並分別報告每個階段的結果。
    """
    print("🚀 開始執行自動化品質保證流程...")
    # 確保我們在專案根目錄下執行
    os.chdir(os.path.dirname(os.path.abspath(__file__)))

    checks = {
        "Ruff 靜態程式碼分析": ["ruff", "check", "."],
        "deptry 依賴檢查": ["deptry", "."],
        "pytest 測試": ["pytest", "-v"]
    }

    failed_checks = []

    for i, (check_name, command) in enumerate(checks.items()):
        print(f"\n[階段 {i+1}/{len(checks)}] 執行 {check_name}...")
        if not run_command(command, check=False):
            print(f"⚠️ {check_name} 未通過。")
            failed_checks.append(check_name)
        else:
            print(f"✅ {check_name} 通過。")

    # 最終總結
    print("\n🏁 品質保證流程執行完畢。")
    if not failed_checks:
        print("🎉 所有檢查和測試均已通過！代碼品質達標。")
        sys.exit(0)
    else:
        print(f"❌ 以下 {len(failed_checks)} 個檢查或測試未通過:")
        for check in failed_checks:
            print(f"  - {check}")
        sys.exit(1)

if __name__ == "__main__":
    main()
