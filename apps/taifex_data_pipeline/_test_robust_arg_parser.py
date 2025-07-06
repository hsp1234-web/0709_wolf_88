# 檔名: apps/taifex_data_pipeline/_test_robust_arg_parser.py
import subprocess
import sys
import os

def print_test_header(title):
    print("\n" + "="*80)
    print(f"🧪  開始測試: {title}")
    print("="*80)

def run_test(command, description):
    print(f"\n- 執行指令: {' '.join(command)}")
    print(f"- 預期結果: {description}")
    result = subprocess.run(command, capture_output=True, text=True)
    print(f"- 返回碼 (Return Code): {result.returncode}")
    print(f"- 標準輸出 (stdout):\n{result.stdout.strip()}")
    print(f"- 標準錯誤 (stderr):\n{result.stderr.strip()}")
    return result.returncode

def main():
    print("--- 沙箱環境：通訊協定穩健性驗收測試 ---")
    run_py_path = os.path.join(os.path.dirname(__file__), 'run.py')

    # 測試案例 1: 模擬前端指揮中心的失敗調用
    print_test_header("測試案例 1: 帶有未知參數的調用")
    cmd_with_unknown_args = [
        sys.executable,
        run_py_path,
        '--input-files', 'dummy_file.zip', # 即使檔案不存在，腳本也不應因參數解析而崩潰
        '--db-output-dir', '/tmp/db',      # 同上
        '--unrecognized-arg-1', # 未知參數 1
        '--max-workers', '10'   # 未知參數 2
    ]
    return_code = run_test(cmd_with_unknown_args, "腳本應優雅地忽略未知參數並繼續執行（返回碼 0 或 1，因找不到檔案或無法建立目錄而退出，但絕不能是 2）")

    if return_code == 2:
        print("\n❌ 測試失敗: 腳本因『unrecognized arguments』而崩潰。")
        sys.exit(1)
    elif return_code != 2: # 任何非2的返回碼都視為參數解析成功
        print("\n✅ 測試成功: 腳本已成功忽略未知參數，未因參數解析錯誤而崩潰。")
    else: # 理論上不會到這裡，但以防萬一
        print(f"\n⚠️ 測試警告: 腳本返回非預期錯誤碼 {return_code}，需人工檢查。")

    # 測試案例 2: 驗證原始功能未受影響
    print_test_header("測試案例 2: 不帶未知參數的正常調用 (回歸測試)")
    cmd_normal = [
        sys.executable,
        run_py_path,
        '--help' # 使用 --help 進行快速啟動驗證
    ]
    return_code_normal = run_test(cmd_normal, "腳本應正常顯示幫助訊息並退出（返回碼 0）")

    if return_code_normal == 0:
        print("\n✅ 測試成功: 腳本在無未知參數情況下功能正常。")
    else:
        print("\n❌ 測試失敗: 腳本在正常調用下未能成功執行。")
        sys.exit(1)

    print("\n\n🎉🎉🎉 通訊協定穩健性驗收測試全部通過！ 🎉🎉🎉")

if __name__ == "__main__":
    main()
