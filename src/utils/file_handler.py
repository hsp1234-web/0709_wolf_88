# src/utils/file_handler.py
import json

def save_to_json(data: dict, filepath: str) -> bool:
    """
    將字典儲存為 JSON 檔案。

    Args:
        data: 要儲存的字典。
        filepath: JSON 檔案的路徑。

    Returns:
        如果儲存成功則返回 True，否則 False。
    """
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except IOError as e:
        print(f"儲存檔案錯誤 {filepath}: {e}")
        return False
    except Exception as e:
        print(f"儲存 JSON 時發生未知錯誤: {e}")
        return False

def load_from_json(filepath: str) -> dict | None:
    """
    從 JSON 檔案載入字典。

    Args:
        filepath: JSON 檔案的路徑。

    Returns:
        載入的字典，如果失敗則返回 None。
    """
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except FileNotFoundError:
        print(f"錯誤：找不到檔案 {filepath}")
        return None
    except json.JSONDecodeError as e:
        print(f"解碼 JSON 錯誤 {filepath}: {e}")
        return None
    except Exception as e:
        print(f"載入 JSON 時發生未知錯誤: {e}")
        return None
