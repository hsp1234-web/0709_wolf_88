import sys
import os

# --- 標準化「路徑自我校正」樣板碼 START ---
# 取得目前腳本檔案的目錄
current_script_dir = os.path.dirname(os.path.abspath(__file__))
# 自動偵測專案根目錄 (假設 .git 在根目錄，或存在 README.md)
project_root_path = current_script_dir # 使用 project_root_path 避免與後續的 project_root 變數衝突
max_levels_up = 5 # 防止無限迴圈，可根據專案深度調整
for _ in range(max_levels_up):
    # 檢查是否存在 .git 目錄或 AGENTS.md (或 README.md) 作為根目錄標記
    if os.path.isdir(os.path.join(project_root_path, '.git')) or \
       os.path.isfile(os.path.join(project_root_path, 'AGENTS.md')) or \
       os.path.isfile(os.path.join(project_root_path, 'README.md')):
        break
    parent_dir = os.path.dirname(project_root_path)
    if parent_dir == project_root_path: # 已達檔案系統頂層
        project_root_path = os.path.abspath(os.path.join(current_script_dir, '..', '..'))
        print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑: {project_root_path}")
        break
    project_root_path = parent_dir
else: # 如果迴圈正常結束 (未 break)
    project_root_path = os.path.abspath(os.path.join(current_script_dir, '..', '..')) # 後備方案
    print(f"警告: 未能自動偵測到專案根目錄 (基於 .git, AGENTS.md 或 README.md)。使用預設回退路徑: {project_root_path}")

if project_root_path not in sys.path:
    sys.path.insert(0, project_root_path)
# print(f"DEBUG: 專案根目錄 {project_root_path} 已添加到 sys.path")
# --- 標準化「路徑自我校正」樣板碼 END ---

# 主執行腳本
# 作戰摘要產生器

# get_project_root() 函數不再需要，project_root_path 由上面的樣板碼提供

def generate_directory_tree(root_dir: str, exclude_dirs: list[str] = None) -> str:
    """
    生成專案的目錄樹 (Markdown 格式)。

    Args:
        root_dir: 專案根目錄的路徑。
        exclude_dirs: 要排除的目錄名稱列表。

    Returns:
        Markdown 格式的目錄樹字串。
    """
    if exclude_dirs is None:
        exclude_dirs = [".git", "__pycache__"]

    tree_output = ["```"]
    for root, dirs, files in os.walk(root_dir):
        # 排除指定的目錄
        dirs[:] = [d for d in dirs if d not in exclude_dirs]

        level = root.replace(root_dir, "").count(os.sep)
        indent = " " * 4 * (level)
        tree_output.append(f"{indent}├── {os.path.basename(root)}/")

        sub_indent = " " * 4 * (level + 1)
        for f in files:
            # 排除指定的檔案類型或隱藏檔案 (可根據需求擴展)
            if f.startswith('.'):
                continue
            tree_output.append(f"{sub_indent}├── {f}")
    tree_output.append("```")
    return "\n".join(tree_output)

if __name__ == "__main__":
    # project_root 由頂部的路徑校正樣板碼提供，變數名為 project_root_path
    # 為保持後續代碼一致性，這裡可以賦值給 project_root，或者直接修改後續代碼使用 project_root_path
    project_root = project_root_path
    print(f"專案根目錄：{project_root}")

    markdown_content = "# 專案作戰摘要\n\n"

    markdown_content += "## 一、專案目錄樹\n\n"
    dir_tree = generate_directory_tree(project_root)
    markdown_content += dir_tree + "\n\n"

    # --- 遍歷微服務並彙編摘要 ---
    markdown_content += "## 二、微服務摘要\n\n"
    apps_dir = os.path.join(project_root, "apps")
    if os.path.exists(apps_dir) and os.path.isdir(apps_dir):
        for service_name in os.listdir(apps_dir):
            service_path = os.path.join(apps_dir, service_name)
            if os.path.isdir(service_path) and service_name != "dossier_generator": # 排除自身
                run_py_path = os.path.join(service_path, "run.py")
                if os.path.exists(run_py_path):
                    markdown_content += f"### 微服務：{service_name}\n\n"
                    markdown_content += f"**檔案路徑：** `apps/{service_name}/run.py`\n\n"
                    markdown_content += "```python\n"
                    try:
                        with open(run_py_path, "r", encoding="utf-8") as f:
                            markdown_content += f.read()
                        markdown_content += "\n```\n\n"
                    except Exception as e:
                        markdown_content += f"無法讀取檔案：{e}\n```\n\n"
                else:
                    markdown_content += f"### 微服務：{service_name}\n\n"
                    markdown_content += f"未找到 `run.py` 檔案。\n\n"
    else:
        markdown_content += "未找到 `apps` 目錄。\n\n"

    # --- 彙編共享模組 ---
    markdown_content += "## 三、核心共享模組 (core)\n\n"
    core_dir = os.path.join(project_root, "core")
    if os.path.exists(core_dir) and os.path.isdir(core_dir):
        for filename in os.listdir(core_dir):
            if filename.endswith(".py"): # 假設共享模組都是 .py 檔案
                file_path = os.path.join(core_dir, filename)
                markdown_content += f"### 模組：{filename}\n\n"
                markdown_content += f"**檔案路徑：** `core/{filename}`\n\n"
                markdown_content += "```python\n"
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        markdown_content += f.read()
                    markdown_content += "\n```\n\n"
                except Exception as e:
                    markdown_content += f"無法讀取檔案：{e}\n```\n\n"
    else:
        markdown_content += "未找到 `core` 目錄。\n\n"


    print("\n產生的 Markdown 內容預覽（包含微服務與核心共享模組）：")
    # print(markdown_content) # 在最終寫入前，可以選擇性註解掉詳細預覽以保持終端輸出簡潔

    # --- 最終輸出指令：覆寫 README.md ---
    readme_path = os.path.join(project_root, "README.md")
    try:
        with open(readme_path, "w", encoding="utf-8") as f:
            f.write(markdown_content)
        print(f"\n成功將作戰摘要寫入到：{readme_path}")
    except Exception as e:
        print(f"\n錯誤：無法寫入 README.md 檔案：{e}")

if __name__ == "__main__":
    project_root = get_project_root()
    print(f"專案根目錄：{project_root}")

    markdown_content = "# 專案作戰摘要\n\n"
    markdown_content += "由 `apps/dossier_generator/run.py` 自動產生。\n\n" # 新增提示訊息

    markdown_content += "## 一、專案目錄樹\n\n"
    dir_tree = generate_directory_tree(project_root)
