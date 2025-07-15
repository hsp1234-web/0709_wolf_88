import xml.etree.ElementTree as ET
from datetime import datetime

from prometheus.core.logger import LogManager


class AIReportGenerator:
    """
    模擬 AI 讀取機器可讀的 XML 報告，並將其翻譯、總結為人類可讀的 Markdown 戰報。
    """

    def __init__(self, log_manager: LogManager):
        self.log = log_manager

    def generate_from_xml(self, xml_path: str, md_path: str):
        """
        從 JUnit XML 檔案產生 Markdown 報告。
        """
        self.log.log("INFO", f"AI 報告生成器啟動，正在讀取原始數據: {xml_path}")
        try:
            tree = ET.parse(xml_path)
            root = tree.getroot()
            suite = root.find("testsuite")

            # 提取核心數據
            total = int(suite.get("tests", 0))
            failures = int(suite.get("failures", 0))
            errors = int(suite.get("errors", 0))
            skipped = int(suite.get("skipped", 0))
            exec_time = float(suite.get("time", 0))
            passed = total - failures - errors - skipped

            # 開始構建 Markdown 報告
            report_content = []
            report_content.append("# **【普羅米修斯之火】系統測試作戰報告**")
            report_content.append(
                f"> 報告生成時間：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            )

            # 總結區塊
            report_content.append("## **一、 戰況總覽**")
            if failures == 0 and errors == 0:
                report_content.append(
                    "> **結論：<font color='green'>任務成功 (SUCCESS)</font>** - 所有品質閘門均已通過。系統戰備狀態良好。"
                )
            else:
                report_content.append(
                    "> **結論：<font color='red'>任務失敗 (FAILURE)</font>** - 發現關鍵性錯誤。系統存在風險，需立即審查。"
                )

            summary_table = [
                "| 指標 (Metric) | 數量 (Count) |",
                "|:---|:---:|",
                f"| ✅ **測試通過 (Passed)** | {passed} |",
                f"| ❌ **測試失敗 (Failed)** | {failures} |",
                f"| 🔥 **執行錯誤 (Errors)** | {errors} |",
                f"| 🚧 **測試跳過 (Skipped)** | {skipped} |",
                f"| ⏱️ **總執行時間 (Time)** | {exec_time:.2f} 秒 |",
                f"| 🧮 **總執行數量 (Total)** | {total} |",
            ]
            report_content.append("\n".join(summary_table))

            # 失敗與錯誤詳情
            if failures > 0 or errors > 0:
                report_content.append("\n## **二、 失敗與錯誤詳情**")
                count = 1
                for testcase in suite.findall("testcase"):
                    failure = testcase.find("failure")
                    error = testcase.find("error")

                    detail = failure if failure is not None else error

                    if detail is not None:
                        test_name = testcase.get("name", "未知測試")
                        class_name = testcase.get("classname", "未知類別")
                        error_type = detail.tag.capitalize()  # "failure" -> "Failure"
                        message = detail.get("message", "無訊息").splitlines()[0]

                        report_content.append(f"\n### {count}. {error_type}: {message}")
                        report_content.append(
                            f"- **測試位置:** `{class_name}.{test_name}`"
                        )
                        report_content.append("- **詳細堆疊追蹤:**")
                        # 檢查 detail.text 是否為 None
                        stack_trace = (
                            detail.text.strip() if detail.text else "無堆疊追蹤資訊。"
                        )
                        report_content.append(f"```\n{stack_trace}\n```")
                        count += 1

            # 寫入檔案
            with open(md_path, "w", encoding="utf-8") as f:
                f.write("\n".join(report_content))

            self.log.log("SUCCESS", f"作戰報告已成功生成至: {md_path}")

        except FileNotFoundError:
            self.log.log("ERROR", f"找不到原始數據檔案: {xml_path}")
        except ET.ParseError:
            self.log.log("ERROR", f"原始數據檔案格式錯誤: {xml_path}")
        except Exception as e:
            self.log.log("ERROR", f"生成報告時發生未知錯誤: {e}")
