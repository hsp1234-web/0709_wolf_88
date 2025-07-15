import argparse
import hashlib
import os

from prometheus.core.db.schema_registry import SchemaRegistry
from prometheus.core.utils.helpers import (
    prospect_file_content,
    read_file_content,
)


def get_header_fingerprint(header_line: str) -> str:
    """對標準化後的標頭計算指紋。"""
    normalized_header = "".join(header_line.lower().split()).replace('"', "")
    return hashlib.sha256(normalized_header.encode("utf-8")).hexdigest()


def run_explorer(input_dir: str, db_path: str):
    registry = SchemaRegistry(db_path)
    print(f"--- 開始掃描目錄: {input_dir} ---")
    new_formats = 0
    updated_formats = 0

    for filename in os.listdir(input_dir):
        file_path = os.path.join(input_dir, filename)
        if not os.path.isfile(file_path):
            continue

        try:
            file_bytes_content = read_file_content(file_path)
            if file_bytes_content is None:
                continue

            result = prospect_file_content(file_bytes_content)

            if result["status"] == "success":
                fingerprint = get_header_fingerprint(result["header"])
                status = registry.add_or_update_schema(fingerprint, result["header"], result["encoding"], filename)
                if status == "new":
                    new_formats += 1
                else:
                    updated_formats += 1

        except Exception as e:
            print(f"[ERROR] 處理檔案 {filename} 失敗: {e}")

    registry.close()
    print("\n--- 格式探勘總結 ---")
    print(f"  發現新格式: {new_formats} 種")
    print(f"  更新現有格式計數: {updated_formats} 次")


def main():
    parser = argparse.ArgumentParser(description="TAIFEX 格式探勘與註冊器 v1.0")
    parser.add_argument(
        "--input-dir", default="data/downloads", help="掃描的原始檔案目錄"
    )
    parser.add_argument(
        "--db-path",
        default="data/metadata/schema_registry.db",
        help="格式註冊表資料庫路徑",
    )
    args = parser.parse_args()
    run_explorer(args.input_dir, args.db_path)


if __name__ == "__main__":
    main()
