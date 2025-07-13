# tasks.py
import subprocess
import sys
import typer

app = typer.Typer(help="【普羅米修斯之火】專案的統一任務指揮中心。")

def _run_uv_command(command: list[str]):
    """使用 'uv run' 執行一個指令。"""
    try:
        subprocess.run(["uv", "run"] + command, check=True)
    except subprocess.CalledProcessError as e:
        print(f"錯誤：指令執行失敗，返回碼 {e.returncode}")
        sys.exit(e.returncode)
    except FileNotFoundError:
        print("錯誤：找不到 'uv' 指令。")
        sys.exit(1)

@app.command(name="test", help="運行所有單元測試 (pytest)。")
def run_tests():
    """執行 'tests/' 目錄下的所有自動化單元測試。"""
    print("--- 正在執行單元測試... ---")
    _run_uv_command(["pytest", "-v"])
    print("--- ✅ 單元測試完成 ---")

if __name__ == "__main__":
    app()
