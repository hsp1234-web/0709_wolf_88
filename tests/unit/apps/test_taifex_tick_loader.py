import unittest

class TestTaifexTickLoader(unittest.TestCase):
    def test_import_run_module(self):
        """
        測試 apps.taifex_tick_loader.run 模組是否可以被成功導入。
        """
        try:
            from apps.taifex_tick_loader import run
            self.assertIsNotNone(run)  # 驗證 run 模組確實被導入了
        except ImportError as e:
            self.fail(f"無法導入 apps.taifex_tick_loader.run 模組: {e}")

if __name__ == '__main__':
    unittest.main()
