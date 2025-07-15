import zipfile
from typing import Dict, Optional


def prospect_file_content(file_bytes: bytes) -> Dict[str, str]:
    """嘗試解碼並讀取第一行(標頭)。"""
    for encoding in ["ms950", "big5", "utf-8", "utf-8-sig"]:
        try:
            content = file_bytes.decode(encoding)
            header = content.splitlines()[0].strip()
            return {"status": "success", "encoding": encoding, "header": header}
        except (UnicodeDecodeError, IndexError):
            continue
    return {"status": "failure", "error": "無法解碼或檔案為空"}


def read_file_content(file_path: str) -> Optional[bytes]:
    """讀取檔案內容，支援 ZIP 檔案。"""
    if zipfile.is_zipfile(file_path):
        try:
            with zipfile.ZipFile(file_path, "r") as zf:
                for member_name in zf.namelist():
                    if member_name.lower().endswith((".csv", ".txt")):
                        return zf.read(member_name)
        except zipfile.BadZipFile:
            return None
    elif file_path.lower().endswith((".csv", ".txt")):
        with open(file_path, "rb") as f:
            return f.read()
    return None
