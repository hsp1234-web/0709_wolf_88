import logging
import json
import sqlite3
from typing import Optional, Dict, Any
from pathlib import Path
from datetime import datetime

from core.config import PROJECT_ROOT

logger = logging.getLogger(__name__)

class FactorMetadataManager:
    """
    因子元數據管理器 (Factor Metadata Manager)。
    負責管理因子定義的元數據，並將其從設定檔同步到 SQLite 資料庫。
    """
    DEFAULT_DB_PATH = PROJECT_ROOT / "data_warehouse" / "factor_details.db"
    DEFAULT_RECIPES_CONFIG_PATH = PROJECT_ROOT / "prometheus_fire_backend" / "config" / "factor_recipes.json"
    TABLE_NAME = "factor_details"

    def __init__(self,
                 db_path: Optional[Path] = None,
                 recipes_config_path: Optional[Path] = None):
        """
        初始化因子元數據管理器。

        Args:
            db_path (Optional[Path]): 因子元數據資料庫的路徑。
                                     如果為 None，則使用預設路徑。
            recipes_config_path (Optional[Path]): 因子配方設定檔的路徑。
                                                 如果為 None，則使用預設路徑。
        """
        self.db_path = db_path if db_path is not None else self.DEFAULT_DB_PATH
        self.recipes_config_path = recipes_config_path if recipes_config_path is not None else self.DEFAULT_RECIPES_CONFIG_PATH

        self.db_path.parent.mkdir(parents=True, exist_ok=True) # 確保資料庫目錄存在
        self._create_table_if_not_exists()
        logger.info(f"因子元數據管理器 (FactorMetadataManager) 初始化完畢。資料庫路徑: {self.db_path}")

    def _create_table_if_not_exists(self):
        """如果因子元數據表格不存在，則在資料庫中建立它。"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.TABLE_NAME} (
                    factor_id TEXT PRIMARY KEY,
                    name TEXT,
                    type TEXT,
                    description TEXT,
                    calculator_type TEXT,
                    calculator_function TEXT,
                    params_json TEXT,
                    output_column_name TEXT,
                    last_synced_at TIMESTAMP
                )
                """)
                conn.commit()
                logger.info(f"表格 '{self.TABLE_NAME}' 已確認/建立於資料庫 '{self.db_path}'。")
        except sqlite3.Error as e:
            logger.error(f"在資料庫 '{self.db_path}' 中建立/確認表格 '{self.TABLE_NAME}' 時發生 SQLite 錯誤: {e}", exc_info=True)
            raise # 重新拋出錯誤，因為這是一個關鍵的初始化步驟

    def sync_recipes_to_db(self) -> bool:
        """
        從因子配方設定檔 (factor_recipes.json) 讀取因子定義，
        並將它們同步到因子元數據資料庫的 factor_details 表格中。

        Returns:
            bool: 如果同步成功則返回 True，否則返回 False。
        """
        logger.info(f"開始從 '{self.recipes_config_path}' 同步因子配方到資料庫 '{self.db_path}'...")

        if not self.recipes_config_path.exists() or not self.recipes_config_path.is_file():
            logger.error(f"因子配方設定檔不存在或不是一個檔案: {self.recipes_config_path}")
            return False

        try:
            with open(self.recipes_config_path, 'r', encoding='utf-8') as f:
                recipes: Dict[str, Any] = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"解析因子配方設定檔 {self.recipes_config_path} 時發生 JSON 錯誤: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"讀取因子配方設定檔 {self.recipes_config_path} 時發生未知錯誤: {e}", exc_info=True)
            return False

        if not recipes:
            logger.warning(f"因子配方設定檔 {self.recipes_config_path} 為空或無效，沒有元數據可同步。")
            return True # 技術上沒有失敗，只是沒有數據

        sync_timestamp = datetime.now()
        records_to_upsert = []

        for factor_id, recipe_details in recipes.items():
            if not isinstance(recipe_details, dict):
                logger.warning(f"配方中的條目 '{factor_id}' 不是一個有效的字典，跳過。")
                continue

            record = (
                factor_id,
                recipe_details.get("name"),
                recipe_details.get("type"),
                recipe_details.get("description"),
                recipe_details.get("calculator_type"),
                recipe_details.get("calculator_function"),
                json.dumps(recipe_details.get("params", {})), # 將 params 字典轉為 JSON 字串
                recipe_details.get("output_column_name"),
                sync_timestamp
            )
            records_to_upsert.append(record)

        if not records_to_upsert:
            logger.info("沒有有效的因子記錄可供同步。")
            return True

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                # 使用 INSERT OR REPLACE (UPSERT) 語法
                cursor.executemany(f"""
                INSERT OR REPLACE INTO {self.TABLE_NAME} (
                    factor_id, name, type, description, calculator_type,
                    calculator_function, params_json, output_column_name, last_synced_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, records_to_upsert)
                conn.commit()
                logger.info(f"成功同步 {len(records_to_upsert)} 個因子元數據到資料庫 '{self.db_path}'。")
                return True
        except sqlite3.Error as e:
            logger.error(f"同步因子元數據到資料庫 '{self.db_path}' 時發生 SQLite 錯誤: {e}", exc_info=True)
            return False
        except Exception as e: # 捕捉其他可能的錯誤
            logger.error(f"同步因子元數據到資料庫時發生非預期錯誤: {e}", exc_info=True)
            return False

if __name__ == '__main__':
    # 配置基本的日誌記錄器，以便在直接運行此檔案時能看到日誌輸出
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    logger.info("--- 測試 FactorMetadataManager ---")

    # 為了測試，我們可以創建一個臨時的 recipes 檔案和 db 檔案
    test_recipes_content = {
        "SMA_5_Test": {
            "name": "SMA_5_Test",
            "type": "trend_test",
            "description": "5日測試移動平均。",
            "calculator_type": "test_pandas_ta",
            "calculator_function": "sma_test",
            "params": {"length": 5, "source_column": "TestClose"},
            "output_column_name": "SMA_5_T"
        },
        "RSI_7_Test": {
            "name": "RSI_7_Test",
            "type": "momentum_test",
            "description": "7日測試相對強弱。",
            "calculator_type": "test_pandas_ta",
            "calculator_function": "rsi_test",
            "params": {"length": 7}, # 測試 params 中 source_column 可選的情況
            "output_column_name": "RSI_7_T"
        }
    }
    temp_config_dir = PROJECT_ROOT / "temp_test_config"
    temp_config_dir.mkdir(parents=True, exist_ok=True)
    test_recipes_path = temp_config_dir / "test_factor_recipes.json"
    with open(test_recipes_path, 'w', encoding='utf-8') as f:
        json.dump(test_recipes_content, f, indent=2)

    temp_db_dir = PROJECT_ROOT / "temp_test_data_warehouse"
    temp_db_dir.mkdir(parents=True, exist_ok=True)
    test_db_path = temp_db_dir / "test_factor_details.db"
    if test_db_path.exists():
        test_db_path.unlink() # 確保每次測試都從乾淨的資料庫開始

    manager = FactorMetadataManager(db_path=test_db_path, recipes_config_path=test_recipes_path)

    print(f"\n測試 sync_recipes_to_db...")
    sync_success = manager.sync_recipes_to_db()
    assert sync_success, "sync_recipes_to_db 應該成功"
    print("sync_recipes_to_db 執行完畢。")

    print("\n驗證資料庫內容...")
    try:
        with sqlite3.connect(test_db_path) as conn:
            conn.row_factory = sqlite3.Row # 允許按欄位名訪問
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {manager.TABLE_NAME}")
            rows = cursor.fetchall()

            assert len(rows) == 2, f"資料庫中應有 2 筆記錄，實際為 {len(rows)}"
            print(f"資料庫中找到 {len(rows)} 筆記錄。")

            for row in rows:
                print(f"  記錄: factor_id={row['factor_id']}, name={row['name']}, description={row['description']}")
                assert row['factor_id'] in test_recipes_content
                original_recipe = test_recipes_content[row['factor_id']]
                assert row['name'] == original_recipe['name']
                assert row['description'] == original_recipe['description']
                assert row['calculator_function'] == original_recipe['calculator_function']
                assert json.loads(row['params_json']) == original_recipe.get('params', {}) # 比較解析後的 params
                assert row['output_column_name'] == original_recipe['output_column_name']
                assert row['last_synced_at'] is not None
            print("資料庫內容驗證通過。")

    except sqlite3.Error as e:
        print(f"驗證資料庫時發生 SQLite 錯誤: {e}")
        assert False, "資料庫驗證失敗"
    finally:
        # 清理臨時檔案和目錄
        if test_recipes_path.exists():
            test_recipes_path.unlink()
        if temp_config_dir.exists():
            temp_config_dir.rmdir() # 只能移除空目錄，如果裡面還有其他檔案會失敗
        if test_db_path.exists():
            test_db_path.unlink()
        if temp_db_dir.exists():
            # 確保目錄是空的才移除
            try:
                temp_db_dir.rmdir()
            except OSError:
                logger.warning(f"無法移除臨時資料庫目錄 {temp_db_dir}，可能非空。")

    logger.info("--- FactorMetadataManager 測試完畢 ---")

    # 測試預設路徑 (如果 factor_recipes.json 存在)
    # default_manager = FactorMetadataManager()
    # default_manager.sync_recipes_to_db() # 這會嘗試讀取真實的設定檔並寫入真實的資料庫
    # print("預設路徑的 FactorMetadataManager 初始化並嘗試同步完畢。")
    # (請注意，這可能會修改您的開發資料庫，如果需要隔離，請註解掉此部分)

    print("\nFactorMetadataManager 類已成功建立和基本測試。")
