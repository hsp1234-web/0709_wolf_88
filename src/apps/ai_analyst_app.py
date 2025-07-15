# 檔案: src/apps/ai_analyst_app.py
import json
from pathlib import Path
# 假設我們有一個 Gemini 客戶端
# from src.core.clients.gemini_client import GeminiClient

# --- 模擬 Gemini 客戶端 ---
class MockGeminiClient:
    def generate_report(self, prompt: str) -> str:
        print("\n[AI-Analyst] 正在調用模擬的 Gemini API...")
        # 在真實場景中，這裡會是 API 呼叫
        # 為了演示，我們返回一個基於提示的簡單模板化回應
        return f"""
# 【普羅米修斯之火】策略分析報告

**1. 策略核心解讀 (Strategy Deconstruction)**
   - **策略類型:** 短期趨勢跟隨。
   - **行為模式:** 它試圖在短期均線向上穿越長期均線時進場，並在 RSI 指標顯示超買時出場。其背後的交易哲學可能是捕捉由短期動能引發的小波段上漲。

**2. 績效綜合評估 (Performance Assessment)**
   - **樣本內表現:** 在學習區表現出色。
   - **【嚴峻考驗】樣本外表現:** 在未知區表現尚可。
   - **一致性分析:** 樣本內外夏普比率存在一定衰退，但未超過30%，暫無明顯的過擬合警示。

**3. 戰術推演與風險分析 (Tactical Simulation & Risk Analysis)**
   - **適應的市場環境:** 最可能在溫和上漲的趨勢市中獲利。
   - **潛在弱點 (Achilles' Heel):** 害怕劇烈的假突破和長期盤整行情，可能導致頻繁止損。

**4. 最終結論與建議 (Final Verdict & Recommendations)**
   - **策略總評:** 這是一個在特定歷史時期有效的“幸運兒”，但其穩健性仍需進一步驗證。
   - **下一步行動建議:** 建議投入小資金進行實盤測試，並密切關注其在真實市場中的表現，特別是在盤整市中的回撤情況。
"""

# --- 檔案路徑 ---
HALL_OF_FAME_PATH = Path("data/hall_of_fame.json")
# 假設驗證報告會被儲存到這裡
VALIDATION_REPORT_PATH = Path("data/validation_report.json")
FINAL_REPORT_PATH = Path("strategy_intelligence_report.md")

def generate_analysis_prompt(strategy_data: dict, validation_data: dict) -> str:
    # 這部分將實現「洞察力提示」的格式化
    prompt = f"""
# --- AI 首席量化分析師指令 ---

**角色:**
你是一位經驗豐富的首席量化策略分析師。你的任務不是簡單地複述數據，而是要以清晰、專業、且富有洞察力的方式，為一位資深決策者（指揮官）解讀一份由 AI 演化引擎發現並驗證過的交易策略。

**輸入資料:**
你將收到一份包含以下結構的 JSON 資料：
1.  `strategy_params`: 策略的具體參數。
2.  `in_sample_performance`: 策略在學習區（樣本內）的回測績效。
3.  `out_of_sample_performance`: 策略在未知區（樣本外）的最終考驗績效。

**任務要求:**
請根據輸入資料，生成一份結構完整的 Markdown 格式分析報告，必須包含以下所有章節：

---
### **【普羅米修斯之火】策略分析報告**

**1. 策略核心解讀 (Strategy Deconstruction)**
   - **策略類型:** 根據參數（例如，短均線 vs 長均線，RSI 出場點位），判斷這是一個什麼類型的策略？（例如：短期趨勢跟隨、長線動能捕捉、逆勢反轉等）。
   - **行為模式:** 用白話文描述這個策略的交易行為。「它試圖在什麼時候進場？又在什麼時候出場？它背後的交易哲學可能是什麼？」

**2. 績效綜合評估 (Performance Assessment)**
   - **樣本內表現:** 總結它在學習區的表現。是否出色？
   - **【嚴峻考驗】樣本外表現:** 總結它在未知區的表現。
   - **一致性分析:** 對比樣本內與樣本外的關鍵指標（特別是夏普比率和最大回撤）。兩者表現是否一致？如果存在顯著衰退（例如夏普比率下降超過 30%），請明確指出，並將其標記為一個「**過擬合警示**」。

**3. 戰術推演與風險分析 (Tactical Simulation & Risk Analysis)**
   - **適應的市場環境:** 根據策略的行為模式和績效表現，推斷它最可能在哪種市場環境下獲利？（例如：高波動的趨勢市、低波動的盤整市、溫和上漲的牛市等）。
   - **潛在弱點 (Achilles' Heel):** 這個策略最害怕遇到什麼樣的行情？它的潛在風險是什麼？（例如：害怕劇烈的假突破、在長期盤整中可能被頻繁止損等）。

**4. 最終結論與建議 (Final Verdict & Recommendations)**
   - **策略總評:** 給予這個策略一個總體評價。它是一個值得信賴的穩健策略，還是一個僅在特定歷史時期有效的「幸運兒」？
   - **下一步行動建議:** 基於以上所有分析，你建議指揮官下一步應該做什麼？（例如：直接投入小資金實盤測試、需要針對其弱點進行進一步優化、或因過擬合風險而應直接放棄）。
---

---
**【輸入資料】**
```json
{{
    "strategy_params": {json.dumps(strategy_data.get("params"), indent=4)},
    "in_sample_performance": {json.dumps(strategy_data.get("fitness"), indent=4)},
    "out_of_sample_performance": {json.dumps(validation_data.get("report"), indent=4)}
}}
```
"""
    return prompt.strip()

def analyst_job():
    """AI 分析師的主工作流程。它是一個單次執行的任務。"""
    print("[AI-Analyst] AI 首席分析師已啟動。")
    # 1. 讀取必要的數據
    if not HALL_OF_FAME_PATH.exists() or not VALIDATION_REPORT_PATH.exists():
        print(f"[AI-Analyst] 錯誤：缺少名人堂或驗證報告。無法生成分析。")
        return

    try:
        with open(HALL_OF_FAME_PATH, 'r') as f:
            strategy_data = json.load(f)
        with open(VALIDATION_REPORT_PATH, 'r') as f:
            validation_data = json.load(f)
    except Exception as e:
        print(f"!!!!!! [AI-Analyst] 讀取數據檔案失敗: {e} !!!!!!")
        return

    # 2. 生成提示
    prompt = generate_analysis_prompt(strategy_data, validation_data)

    # 3. 調用 AI 模型
    # client = GeminiClient() # 真實場景
    client = MockGeminiClient() # 演示場景
    report_content = client.generate_report(prompt)

    # 4. 儲存最終報告
    try:
        with open(FINAL_REPORT_PATH, 'w', encoding='utf-8') as f:
            f.write(report_content)
        print("\n" + "="*20 + " 任務完成 " + "="*20)
        print(f"🎉 最終智慧報告已成功生成！")
        print(f"請查看檔案: {FINAL_REPORT_PATH}")
        print("="*52)
    except Exception as e:
        print(f"!!!!!! [AI-Analyst] 儲存最終報告失敗: {e} !!!!!!")

    print("[AI-Analyst] 工作完成，即將關閉。")
