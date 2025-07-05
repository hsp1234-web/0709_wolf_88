import os

# 主執行腳本
# 作戰摘要產生器

def get_project_root() -> str:
    """取得專案根目錄的路徑。"""
    # 假設此腳本位於 apps/dossier_generator/run.py
    # 因此，根目錄是此腳本路徑往上三層
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

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
    project_root = get_project_root()
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
    markdown_content += "## 三、共享模組 (src/utils)\n\n"
    utils_dir = os.path.join(project_root, "src", "utils")
    if os.path.exists(utils_dir) and os.path.isdir(utils_dir):
        for filename in os.listdir(utils_dir):
            if filename.endswith(".py"): # 假設共享模組都是 .py 檔案
                file_path = os.path.join(utils_dir, filename)
                markdown_content += f"### 模組：{filename}\n\n"
                markdown_content += f"**檔案路徑：** `src/utils/{filename}`\n\n"
                markdown_content += "```python\n"
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        markdown_content += f.read()
                    markdown_content += "\n```\n\n"
                except Exception as e:
                    markdown_content += f"無法讀取檔案：{e}\n```\n\n"
    else:
        markdown_content += "未找到 `src/utils` 目錄。\n\n"


    print("\n產生的 Markdown 內容預覽（包含微服務與共享模組）：")
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
