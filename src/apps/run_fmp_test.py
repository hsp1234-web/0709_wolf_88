# apps/run_fmp_test.py
# FMPClient 端到端實戰驗證執行腳本

import sys
from pathlib import Path

# --- 標準路徑自我校正樣板 ---
# 確保無論從何處執行，都能正確找到 core 模組
# 這是從作戰計畫 031 的修復經驗中學到的標準實踐
#
try:
    # 尋找專案根目錄 (包含 pyproject.toml 的地方)
    current_path = Path(__file__).resolve()
    project_root = current_path.parent.parent
    while (
        not (project_root / "pyproject.toml").exists()
        and project_root != project_root.parent
    ):
        project_root = project_root.parent
    if (project_root / "pyproject.toml").exists():
        if str(project_root) not in sys.path:
            sys.path.insert(0, str(project_root))
            print(f"資訊：已將專案根目錄 '{project_root}' 添加到 sys.path")
    else:
        raise FileNotFoundError("無法定位專案根目錄。")

    from core.clients.fmp import FMPClient
    from core.config import config
except ImportError as e:
    print(
        f"錯誤：模組導入失敗，請確認路徑校正邏輯或依賴是否安裝。錯誤訊息：{e}",
        file=sys.stderr,
    )
    sys.exit(1)
# --- 樣板結束 ---


def main():
    """
    主執行函數，用於驗證 FMPClient。
    """
    print("--- [開始] FMPClient 端到端實戰驗證 ---")

    try:
        # 1. 載入設定檔 (現在是透過導入 config 物件自動載入)
        # 2. 檢查 API 金鑰是否存在
        fmp_api_key = config.get("api_keys.fmp")

        if not fmp_api_key or fmp_api_key == "YOUR_REAL_FMP_API_KEY_HERE":
            print("錯誤：在 config.yml 中找不到 'fmp' 的 API 金鑰。", file=sys.stderr)
            print(
                "請確認 config.yml 檔案中的 api_keys -> fmp 是否已正確設定。",
                file=sys.stderr,
            )
            return

        print("資訊：成功從 config.yml 讀取 FMP API 金鑰。")

        # 3. 初始化 FMPClient
        client = FMPClient(api_key=fmp_api_key)

        # 4. 執行測試數據獲取 (以獲取蘋果公司最近5筆歷史日線價格為例)
        symbol_to_test = "AAPL"
        print(
            f"\n>>> 正在嘗試獲取股票代碼 '{symbol_to_test}' 的歷史價格數據 (最近5筆)..."
        )

        # 根據 fmp.py 的介面，使用 fetch_data 方法
        price_data = client.fetch_data(
            symbol=symbol_to_test, data_type="historical_price", limit=5
        )

        # 5. 驗證並呈現結果
        if price_data is not None and not price_data.empty:
            print(f"\n✅ [成功] 成功獲取 '{symbol_to_test}' 的數據！")
            print("最新 5 筆歷史價格數據預覽：")
            print(price_data)
        else:
            print(f"\n❌ [失敗] 未能獲取 '{symbol_to_test}' 的數據，或返回為空。")
            print("請檢查您的 FMP API 金鑰權限以及網路連線。")

    except Exception as e:
        print(f"\n❌ [災難性失敗] 執行過程中發生未預期的錯誤：{e}", file=sys.stderr)
    finally:
        print("\n--- [結束] FMPClient 端到端實戰驗證 ---")


if __name__ == "__main__":
    main()
