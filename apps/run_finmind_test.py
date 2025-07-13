# apps/run_finmind_test.py
# FinMindClient 端到端實戰驗證執行腳本

import sys
from datetime import datetime, timedelta
from pathlib import Path

# --- 標準路徑自我校正樣板 ---
# 確保無論從何處執行，都能正確找到 core 模組
#
try:
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

    from core.clients.finmind import FinMindClient
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
    主執行函數，用於驗證 FinMindClient。
    """
    print("--- [開始] FinMindClient 端到端實戰驗證 ---")

    try:
        # 1. 載入設定檔 (現在是透過導入 config 物件自動載入)
        # 2. 檢查 API Token 是否存在
        finmind_api_token = config.get("api_keys.finmind")

        if (
            not finmind_api_token
            or finmind_api_token == "YOUR_REAL_FINMIND_API_TOKEN_HERE"
        ):
            print(
                "錯誤：在 config.yml 中找不到 'finmind' 的 API Token。", file=sys.stderr
            )
            print(
                "請確認 config.yml 檔案中的 api_keys -> finmind 是否已正確設定。",
                file=sys.stderr,
            )
            return

        print("資訊：成功從 config.yml 讀取 FinMind API Token。")

        # 3. 初始化 FinMindClient
        client = FinMindClient(api_token=finmind_api_token)

        # 4. 執行測試數據獲取 (以獲取台積電最近5個交易日的三大法人買賣超為例)
        symbol_to_test = "2330"  # 台積電
        end_date = datetime.now()
        start_date = end_date - timedelta(days=14)  # 往前抓14天以確保能覆蓋5個交易日

        print(f"\n>>> 正在嘗試獲取股票代碼 '{symbol_to_test}' 的三大法人買賣超數據...")
        print(
            f"    日期範圍：{start_date.strftime('%Y-%m-%d')} 至 {end_date.strftime('%Y-%m-%d')}"
        )

        # 根據 finmind.py 的介面，使用 get_taiwan_stock_institutional_investors_buy_sell 方法
        investor_data = client.get_taiwan_stock_institutional_investors_buy_sell(
            stock_id=symbol_to_test,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d"),
        )

        # 5. 驗證並呈現結果
        if investor_data is not None and not investor_data.empty:
            print(f"\n✅ [成功] 成功獲取 '{symbol_to_test}' 的數據！")
            print("最新數據預覽：")
            # FinMind數據可能較多，顯示最新的5筆
            print(investor_data.head())
        else:
            print(f"\n❌ [失敗] 未能獲取 '{symbol_to_test}' 的數據，或返回為空。")
            print(
                "請檢查您的 FinMind API Token 權限、網路連線或確認該日期範圍內有數據。"
            )

    except Exception as e:
        print(f"\n❌ [災難性失敗] 執行過程中發生未預期的錯誤：{e}", file=sys.stderr)
    finally:
        print("\n--- [結束] FinMindClient 端到端實戰驗證 ---")


if __name__ == "__main__":
    main()
