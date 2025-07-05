# src/utils/data_validator.py

def is_valid_data(data: dict) -> bool:
    """
    檢查資料是否有效。
    此為範例函數，具體邏輯需根據實際需求填寫。
    """
    if not isinstance(data, dict):
        return False
    if not data: # 檢查是否為空字典
        return False
    # 添加更多驗證邏輯...
    return True

def format_data(data: dict) -> dict:
    """
    格式化資料。
    此為範例函數。
    """
    # 範例：將所有字串值轉換為小寫
    formatted = {}
    for key, value in data.items():
        if isinstance(value, str):
            formatted[key] = value.lower()
        else:
            formatted[key] = value
    return formatted
