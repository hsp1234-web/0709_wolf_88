# **【普羅米修斯之火】金融數據與分析框架 - 開發者手冊 v0.2.0**

## **一、 專案概覽與目的**

【普羅米修斯之火】是一個專為進階量化研究與金融市場分析而設計的 Python 框架。本專案旨在提供一個從多樣化數據源獲取金融數據、進行複雜指標計算、並將結果視覺化的完整解決方案。其核心設計強調模組化、可擴展性以及數據處理的穩健性。

**目前已實現的核心功能包括：**

1.  **多源數據客戶端 (Multi-Source Data Clients):**
    *   支援從 FRED (Federal Reserve Economic Data)、紐約聯儲 (NYFed) 等來源獲取經濟與金融數據。
    *   客戶端設計基於統一的 `BaseAPIClient`，內建了強大的永久性 HTTP 請求快取機制 (`requests-cache`)，並支援手動強制刷新數據。
2.  **安全的金鑰管理 (Secure API Key Management):**
    *   透過 `config.yml` 檔案集中管理 API 金鑰，避免將敏感資訊硬編碼於程式碼中。
    *   `core/config.py` 中的 `ConfigManager` 負責載入與提供設定。
3.  **金融壓力指數引擎 (Financial Stress Index Engine):**
    *   位於 `core/analysis/stress_index.py`，是本專案的核心分析模組。
    *   能夠整合來自 FRED 和 NYFed 的多項指標 (如 VIX, 公債殖利率、聯邦準備金餘額、SOFR、一級交易商持倉數據)。
    *   自動執行數據對齊 (每日頻率)、預處理 (如計算殖利率曲線利差)、使用滾動 Z-Score 標準化各指標，並最終合成為一個綜合的每日金融壓力指數。
4.  **互動式視覺化 (Interactive Visualization):**
    *   使用 `Plotly` 將計算出的金融壓力指數繪製成互動式圖表，方便使用者分析與解讀。

本專案致力於為量化分析師和研究人員提供一個可靠、高效的工具，以應對複雜的金融數據分析挑戰。

## **二、 技術棧 (Technology Stack)**

*   **核心程式語言:** Python 3.12+
*   **依賴管理:** Poetry (v1.8.2 或相容版本)
*   **數據處理:**
    *   Pandas (`^2.2.2`): 主要的數據結構與分析工具。
    *   NumPy (`^1.26.4`): 基礎數值計算。
*   **API 客戶端與網路請求:**
    *   Requests (`^2.31.0`): HTTP 請求。
    *   Requests-Cache (`^1.2.0`): HTTP 請求的持久性快取。
    *   FredAPI (`^0.5.2`): 官方 FRED API 的 Python 封裝。
*   **設定檔管理:**
    *   PyYAML (`^6.0.1`): 解析 YAML 設定檔。
*   **視覺化:**
    *   Plotly (`^5.22.0`): 產生互動式圖表。
*   **Excel 檔案處理:**
    *   Openpyxl (`^3.1.2`): 讀取 `.xlsx` 格式的 Excel 檔案 (NYFedClient 使用)。
*   **其他:** (由 Poetry 自動管理的間接依賴)

## **三、 檔案目錄結構**

```
.
├── .gitignore
├── README.md
├── config.yml                 # 專案設定檔，包含 API 金鑰
├── poetry.lock                # Poetry 鎖定檔案
├── pyproject.toml             # Poetry 專案定義與依賴管理
├── core/
│   ├── __init__.py
│   ├── analysis/              # 分析引擎與腳本
│   │   ├── __init__.py
│   │   └── stress_index.py    # 金融壓力指數計算器
│   ├── clients/               # API 數據客戶端模組
│   │   ├── __init__.py
│   │   ├── base.py            # 基礎 API 客戶端 (含快取)
│   │   ├── fred.py            # FRED 數據客戶端
│   │   └── nyfed.py           # 紐約聯儲數據客戶端
│   ├── config.py              # 設定檔管理器
│   └── utils/                 # 通用工具模組 (目前主要是快取)
│       ├── __init__.py
│       └── caching.py         # 快取相關工具函數
└── financial_data_cache.sqlite  # 由 requests-cache 生成的快取資料庫
```
*(註：隨著專案發展，可能會加入 `tests/`、`data/`、`notebooks/` 等目錄。)*

## **四、 環境設定與啟動**

本專案使用 [Poetry](https://python-poetry.org/) 進行依賴管理和虛擬環境控制。

1.  **安裝 Poetry：**
    *   如果您尚未安裝 Poetry，請參考 [Poetry 官方文檔](https://python-poetry.org/docs/#installation) 進行安裝。建議版本為 1.8.2 或更新。

2.  **克隆專案 (Clone the Project)：**
    ```bash
    git clone <your-repository-url>
    cd <project-directory>
    ```

3.  **配置 Poetry 虛擬環境 (推薦)：**
    *   建議將虛擬環境創建在專案目錄內，方便管理：
        ```bash
        poetry config virtualenvs.in-project true
        ```

4.  **安裝專案依賴：**
    *   在專案根目錄下執行：
        ```bash
        poetry install
        ```
    *   此命令會讀取 `pyproject.toml` 檔案，解析並安裝所有必要的運行時和開發依賴項至 Poetry 創建的虛擬環境中。 主要依賴版本請參考第二節「技術棧」。

5.  **激活虛擬環境：**
    *   要在此專案的環境中工作，請激活 Poetry shell：
        ```bash
        poetry shell
        ```
    *   或者，您可以透過 `poetry run <command>` 在虛擬環境中執行單個指令，而無需手動激活 shell。

6.  **設定 API 金鑰：**
    *   將專案根目錄下的 `config.yml` 檔案中的 `YOUR_FRED_API_KEY_HERE` (或其他 API 金鑰的預留位置) 替換成您真實、有效的 API 金鑰。
        ```yaml
        # config.yml 範例片段
        api_keys:
          fred: "c85a224a0e0d72a7bccb471c0021eb7b" # <- 將此處替換為您的金鑰
        ```
    *   **重要：** `config.yml` 預設應被加入 `.gitignore` 中，以避免將您的私密金鑰提交到版本控制系統。如果 `.gitignore` 中沒有，請手動添加。

## **五、 主要功能執行與驗證**

### **5.1 計算並視覺化金融壓力指數**

這是目前專案的核心功能展示。

*   **腳本位置：** `core/analysis/stress_index.py`
*   **執行指令 (在已激活 `poetry shell` 的環境中，或使用 `poetry run`)：**
    ```bash
    python core/analysis/stress_index.py
    ```
    或者
    ```bash
    poetry run python core/analysis/stress_index.py
    ```

*   **預期行為：**
    1.  腳本將初始化 `StressIndexCalculator`。
    2.  數據客戶端 (`FredClient`, `NYFedClient`) 會被調用以獲取所需的原始金融數據。
        *   首次執行時，數據會從遠端 API 下載。
        *   後續執行時，若數據未過期且未強制刷新，則會從本地快取 (`financial_data_cache.sqlite`) 中讀取，顯著加快執行速度。
    3.  控制台會輸出詳細的執行日誌，包括數據獲取、預處理、標準化和指數合成的各個階段。
    4.  計算完成後，腳本會打印出最新的壓力指數數據點和統計摘要。
    5.  最後，一個互動式的 Plotly 圖表將嘗試在您的預設瀏覽器中打開，展示每日綜合金融壓力指數的時間序列圖。若無法自動打開瀏覽器 (例如在無 GUI 的伺服器環境)，腳本中包含如何將圖表保存為 HTML 檔案的提示。

### **5.2 測試個別數據客戶端 (開發與調試時使用)**

每個客戶端模組 (`core/clients/fred.py`, `core/clients/nyfed.py`, `core/clients/base.py`) 的 `if __name__ == '__main__':` 區塊內都包含了用於測試該客戶端基本功能的範例程式碼。

*   **執行範例 (以 `FredClient` 為例)：**
    ```bash
    poetry run python core/clients/fred.py
    ```
*   **預期行為：**
    *   腳本會初始化對應的客戶端。
    *   執行範例中定義的數據獲取操作 (例如，獲取特定 FRED 指標)。
    *   測試快取機制 (首次下載，第二次從快取讀取，第三次強制刷新)。
    *   在控制台打印相關的日誌和獲取的數據摘要。

## **六、 開發者指引**

1.  **程式碼風格：**
    *   請遵循 PEP 8 Python 風格指南。
    *   鼓勵撰寫清晰、可讀性高的程式碼和註解 (尤其是公開 API 和複雜邏輯部分)。
    *   所有程式碼、註解、日誌輸出和使用者介面訊息，在不影響程式運作的前提下，應使用**繁體中文**。

2.  **版本控制：**
    *   使用 Git 進行版本控制。
    *   分支策略：建議使用 `feat/` (新功能)、`fix/` (錯誤修復)、`docs/` (文件)、`refactor/` (重構) 等前綴來命名分支。
    *   提交訊息 (Commit Messages)：請撰寫清晰、描述性的提交訊息。建議遵循 Conventional Commits 規範，例如：
        *   `feat: 新增壓力指數計算中的 VIX 指標`
        *   `fix: 修正 FRED Client 金鑰讀取錯誤`
        *   `docs: 更新 README 環境設定指南`

3.  **依賴管理：**
    *   所有新的 Python 套件依賴都應透過 Poetry 添加：
        ```bash
        poetry add <package-name>
        poetry add --group dev <dev-package-name> # 開發依賴
        ```
    *   添加後，`pyproject.toml` 和 `poetry.lock` 檔案會自動更新。請務必將這兩個檔案提交到版本控制。

4.  **測試：** (未來擴展)
    *   當加入測試框架 (如 Pytest) 後，所有新功能和錯誤修復都應伴隨相應的單元測試或整合測試。
    *   測試檔案應放置在 `tests/` 目錄下，並遵循相應的結構。

5.  **金鑰與敏感資訊：**
    *   **嚴禁**將任何 API 金鑰、密碼或其他敏感資訊直接硬編碼到 Python 程式碼中。
    *   所有這類資訊必須透過 `config.yml` 管理，並確保 `config.yml` 被正確地加入到 `.gitignore` 中。

## **七、 目前狀況、已知限制與未來展望**

### **7.1 目前狀況 (v0.2.0)**

*   已建立穩健的 API 客戶端基礎 (`BaseAPIClient`)，具備可配置的永久快取與強制刷新功能。
*   已實現 `FredClient` 和 `NYFedClient`，能夠獲取計算壓力指數所需的特定數據系列。
*   已建立安全的 API 金鑰管理機制，透過 `config.yml` 和 `ConfigManager` 實現。
*   核心的 `StressIndexCalculator` 已能成功計算並視覺化一個包含五項指標 (VIX, 殖利率曲線利差, 聯邦準備金, SOFR, 一級交易商持倉) 的綜合金融壓力指數。
*   初步的日誌記錄已整合到各模組中，提供執行過程的追蹤。

### **7.2 已知限制與待改進**

*   **錯誤處理與日誌記錄：** 雖然已有初步日誌，但可以進一步完善錯誤處理機制，提供更細緻的錯誤分類和更豐富的日誌上下文。
*   **`fredapi` 快取：** `StressIndexCalculator` 中對 `FredClient` 的 `force_refresh` 主要是概念上的一致性和日誌標記。由於 `fredapi` 函式庫自身不直接使用我們注入的 `requests-cache` 會話，其快取行為獨立。若要精確控制 `fredapi` 的快取或實現更細緻的快取策略，可能需要更深入的研究或對 `fredapi` 的請求進行更底層的攔截。
*   **測試覆蓋：** 目前專案缺乏自動化的單元測試和整合測試。這是後續版本需要優先補強的部分。
*   **數據回填與完整性檢查：** 尚未實現對歷史數據缺口的主動回填和數據完整性驗證機制。
*   **Plotly 在無 GUI 環境：** `fig.show()` 在沒有圖形介面的環境中可能無法直接顯示圖表。雖然腳本中有提示可以保存為 HTML，但可以考慮加入自動保存 HTML 的選項或更優雅的處理方式。

### **7.3 未來展望**

*   **擴展數據源：** 加入更多金融數據 API (如 FMP, FinMind, 自建數據庫等) 的客戶端。
*   **豐富指標庫：** 在 `StressIndexCalculator` 或新增的分析模組中加入更多種類的金融指標計算。
*   **因子工程引擎：** 開發一個獨立的因子計算引擎，用於從原始數據中挖掘有效的 Alpha 因子。
*   **回測框架整合：** 整合或開發一個事件驅動或向量化的回測框架。
*   **投資組合優化：** 加入現代投資組合理論 (MPT)、風險平價等優化算法模組。
*   **任務調度與自動化：** 考慮使用如 Airflow, Prefect 或簡單的 cron jobs 來自動化數據更新和分析流程。
*   **資料庫強化：** 考慮引入更專業的時序資料庫 (如 InfluxDB, TimescaleDB) 或對 DuckDB 的使用進行更深入的優化。
*   **使用者介面/API 層：** 長遠來看，可以開發一個簡單的 Web UI (使用 Streamlit 或 Flask/Django) 或 REST API 來方便與框架互動。

歡迎開發者們一同參與【普羅米修斯之火】的建設，共同打造強大的量化分析工具！
```
