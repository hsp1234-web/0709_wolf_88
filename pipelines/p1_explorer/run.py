import os
import hashlib
import sqlite3
import argparse
import zipfile

def get_header_fingerprint(header_line: str) -> str:
    """對標準化後的標頭計算指紋。"""
    normalized_header = ''.join(header_line.lower().split())
    return hashlib.sha256(normalized_header.encode('utf-8')).hexdigest()

def prospect_file_content(file_bytes: bytes):
    """嘗試解碼並讀取第一行(標頭)。"""
    for encoding in ['ms950', 'big5', 'utf-8', 'utf-8-sig']:
        try:
            content = file_bytes.decode(encoding)
            header = content.splitlines()[0].strip()
            return {'status': 'success', 'encoding': encoding, 'header': header}
        except (UnicodeDecodeError, IndexError):
            continue
    return {'status': 'failure', 'error': '無法解碼或檔案為空'}

def main():
    parser = argparse.ArgumentParser(description="TAIFEX 格式探勘與註冊器 v1.0")
    parser.add_argument('--input-dir', default='data/downloads', help="掃描的原始檔案目錄")
    parser.add_argument('--db-path', default='data/metadata/schema_registry.db', help="格式註冊表資料庫路徑")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.db_path), exist_ok=True)
    conn = sqlite3.connect(args.db_path)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS schema_registry (
        format_fingerprint TEXT PRIMARY KEY,
        header TEXT,
        encoding TEXT,
        file_count INTEGER DEFAULT 1,
        first_seen_file TEXT
    )""")
    conn.commit()

    print(f"--- 開始掃描目錄: {args.input_dir} ---")
    new_formats = 0
    updated_formats = 0

    for filename in os.listdir(args.input_dir):
        file_path = os.path.join(args.input_dir, filename)
        if not os.path.isfile(file_path):
            continue

        try:
            file_bytes_content = None # Initialize to ensure it's defined
            if zipfile.is_zipfile(file_path):
                try:
                    with zipfile.ZipFile(file_path, 'r') as zf:
                        for member_name in zf.namelist():
                            if member_name.lower().endswith(('.csv', '.txt')):
                                file_bytes_content = zf.read(member_name)
                                break # 只處理第一個符合條件的成員
                        if file_bytes_content is None:
                            print(f"[INFO] 在 ZIP 檔案 {filename} 中未找到 .csv 或 .txt 成員。跳過。")
                            continue
                except zipfile.BadZipFile:
                    print(f"[WARN] 檔案 {filename} 不是一個有效的 ZIP 檔案或已損毀。跳過。")
                    continue
            elif filename.lower().endswith(('.csv', '.txt')):
                with open(file_path, 'rb') as f:
                    file_bytes_content = f.read()
            else:
                print(f"[INFO] 檔案 {filename} 不是支援的 .csv, .txt, 或 .zip 檔案。跳過。")
                continue

            # 確保 file_bytes_content 確實被賦值 (例如，空的 zip 檔案可能導致它為 None)
            if file_bytes_content is None:
                continue

            result = prospect_file_content(file_bytes_content)

            if result['status'] == 'success':
                fingerprint = get_header_fingerprint(result['header'])
                cursor.execute("SELECT file_count FROM schema_registry WHERE format_fingerprint = ?", (fingerprint,))
                existing = cursor.fetchone()

                if existing:
                    new_count = existing[0] + 1
                    cursor.execute("UPDATE schema_registry SET file_count = ? WHERE format_fingerprint = ?", (new_count, fingerprint))
                    updated_formats += 1
                else:
                    cursor.execute("INSERT INTO schema_registry VALUES (?, ?, ?, 1, ?)",
                                   (fingerprint, result['header'], result['encoding'], filename))
                    new_formats += 1
                conn.commit()

        except Exception as e:
            print(f"[ERROR] 處理檔案 {filename} 失敗: {e}")

    conn.close()
    print("\n--- 格式探勘總結 ---")
    print(f"  發現新格式: {new_formats} 種")
    print(f"  更新現有格式計數: {updated_formats} 次")

if __name__ == "__main__":
    main()
