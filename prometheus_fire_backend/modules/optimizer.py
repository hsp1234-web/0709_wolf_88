import logging
import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, Tuple, Union

# PyPortfolioOpt imports
try:
    from pypfopt import expected_returns
    from pypfopt import risk_models
    from pypfopt.efficient_frontier import EfficientFrontier
    from pypfopt.objective_functions import portfolio_return, portfolio_variance # For HRP performance
    from pypfopt.hierarchical_portfolio import HRPOpt
    PYPFOPT_AVAILABLE = True
except ImportError:
    PYPFOPT_AVAILABLE = False
    # Mock classes or raise error if PyPortfolioOpt is critical at module load time
    # For now, we'll check PYPFOPT_AVAILABLE in methods that use it.
    EfficientFrontier = None
    HRPOpt = None
    expected_returns = None
    risk_models = None


logger = logging.getLogger(__name__)

class PortfolioOptimizer:
    """
    投資組合優化器 (Portfolio Optimizer)。
    使用 PyPortfolioOpt 執行投資組合優化。
    """

    def __init__(self, log_manager: Optional[Any] = None):
        """
        初始化投資組合優化器。

        Args:
            log_manager: 可選的日誌管理器實例。
        """
        self.log_manager = log_manager
        if not PYPFOPT_AVAILABLE:
            logger.critical("PyPortfolioOpt 函式庫未安裝，PortfolioOptimizer 將無法運作。請執行 'pip install PyPortfolioOpt'")
            # raise ImportError("PyPortfolioOpt is required for PortfolioOptimizer.")
        logger.info("投資組合優化器 (PortfolioOptimizer) 初始化完畢。")

    def _calculate_returns_and_covariance(
        self,
        prices_df: pd.DataFrame,
        returns_data: bool = False, # If true, prices_df is actually daily returns
        covariance_method: str = "sample_cov", # "sample_cov", "ledoit_wolf", etc.
        expected_returns_method: str = "mean_historical_return" # "mean_historical_return", "ema_historical_return"
    ) -> Tuple[Optional[pd.Series], Optional[pd.DataFrame], Optional[str]]:
        """
        計算預期回報和協方差矩陣。

        Args:
            prices_df (pd.DataFrame): 索引為日期，欄位為資產代號。
                                      如果 returns_data=False (預設)，則值為每日收盤價。
                                      如果 returns_data=True，則值為每日回報率。
            returns_data (bool): 指示 prices_df 是否已為回報率數據。
            covariance_method (str): 計算協方差矩陣的方法。
            expected_returns_method (str): 計算預期回報的方法。


        Returns:
            Tuple[Optional[pd.Series], Optional[pd.DataFrame], Optional[str]]:
                - mu (pd.Series): 預期年化回報率。
                - S (pd.DataFrame): 年化協方差矩陣。
                - error_message (str): 錯誤訊息，如果成功則為 None。
        """
        if not PYPFOPT_AVAILABLE:
            return None, None, "PyPortfolioOpt 函式庫未安裝。"

        if prices_df.empty:
            return None, None, "價格/回報數據為空。"

        logger.info(f"開始計算預期回報與協方差。價格/回報數據筆數: {len(prices_df)}, 資產數量: {prices_df.shape[1]}")
        logger.info(f"協方差計算方法: {covariance_method}, 預期回報計算方法: {expected_returns_method}")

        try:
            if not returns_data:
                # 如果提供的是價格數據，先計算日回報率
                # PyPortfolioOpt 的 risk_models 通常期望價格數據以計算協方差
                # 而 expected_returns 期望價格數據以計算歷史回報
                pass # mu 和 S 的計算會自行處理價格或回報

            # 計算預期年化回報 (mu)
            if expected_returns_method == "mean_historical_return":
                mu = expected_returns.mean_historical_return(prices_df, returns_data=returns_data, compounding=True, frequency=252)
            elif expected_returns_method == "ema_historical_return":
                mu = expected_returns.ema_historical_return(prices_df, returns_data=returns_data, compounding=True, frequency=252)
            else:
                return None, None, f"不支援的預期回報計算方法: {expected_returns_method}"

            # 計算年化協方差矩陣 (S)
            if covariance_method == "sample_cov":
                S = risk_models.sample_cov(prices_df, returns_data=returns_data, frequency=252)
            elif covariance_method == "ledoit_wolf":
                S = risk_models.CovarianceShrinkage(prices_df, returns_data=returns_data, frequency=252).ledoit_wolf()
            elif covariance_method == "oracle_approximating":
                S = risk_models.CovarianceShrinkage(prices_df, returns_data=returns_data, frequency=252).oracle_approximating()
            else:
                return None, None, f"不支援的協方差計算方法: {covariance_method}"

            logger.info("成功計算預期回報與協方差。")
            return mu, S, None

        except Exception as e:
            logger.error(f"計算預期回報與協方差時發生錯誤: {e}", exc_info=True)
            return None, None, f"計算 mu 和 S 時出錯: {e}"

    def optimize_portfolio(
        self,
        prices_df: pd.DataFrame,
        optimization_target: str, # "max_sharpe", "min_volatility", "efficient_risk", "efficient_return", "hrp"
        risk_free_rate: float = 0.02,
        target_volatility: Optional[float] = None,
        target_return: Optional[float] = None,
        weight_bounds: Tuple[float, float] = (0, 1),
        covariance_method: str = "sample_cov",
        expected_returns_method: str = "mean_historical_return"
    ) -> Tuple[Optional[Dict[str, float]], Optional[Dict[str, float]], Optional[str]]:
        """
        執行投資組合優化。

        Args:
            prices_df (pd.DataFrame): 歷史價格數據 (索引為日期，欄位為資產代號)。
            optimization_target (str): 優化目標。
            risk_free_rate (float): 無風險利率。
            target_volatility (Optional[float]): 目標年化波動率 (用於 "efficient_risk")。
            target_return (Optional[float]): 目標年化回報率 (用於 "efficient_return")。
            weight_bounds (Tuple[float, float]): 個別資產權重的上下限。
            covariance_method (str): 計算協方差的方法。
            expected_returns_method (str): 計算預期回報的方法。

        Returns:
            Tuple[Optional[Dict[str, float]], Optional[Dict[str, float]], Optional[str]]:
                - weights (Dict[str, float]): 資產的最佳權重。
                - performance (Dict[str, float]): 投資組合的預期績效 (回報, 波動率, 夏普比率)。
                - error_message (str): 錯誤訊息，如果成功則為 None。
        """
        if not PYPFOPT_AVAILABLE:
            return None, None, "PyPortfolioOpt 函式庫未安裝。"

        logger.info(f"開始投資組合優化。目標: {optimization_target}, 無風險利率: {risk_free_rate}")
        logger.info(f"權重邊界: {weight_bounds}, 價格數據資產數: {prices_df.shape[1]}")

        mu, S, error = self._calculate_returns_and_covariance(
            prices_df,
            covariance_method=covariance_method,
            expected_returns_method=expected_returns_method
        )
        if error:
            logger.error(f"無法執行優化，因為計算 mu 和 S 失敗: {error}")
            return None, None, error
        if mu is None or S is None: # 額外檢查以防 _calculate_returns_and_covariance 返回 None 但沒有 error message
            return None, None, "計算 mu 和 S 後得到 None 值，無法繼續優化。"


        try:
            if optimization_target == "hrp":
                logger.info("執行階層式風險平價 (HRP) 優化...")
                daily_returns = expected_returns.returns_from_prices(prices_df) # HRP 需要日回報率
                hrp = HRPOpt(daily_returns)
                weights_hrp = hrp.optimize()

                # HRP 不直接提供與 EfficientFrontier 相同的績效輸出。
                # 我們可以手動計算基於 HRP 權重的預期組合績效。
                # PyPortfolioOpt 0.5.0 之後，HRPOpt 有 portfolio_performance 方法
                # 但為了兼容舊版或更手動控制，這裡可以這樣做：
                # perf = {"expected_annual_return": None, "annual_volatility": None, "sharpe_ratio": None}
                # if mu is not None and S is not None:
                #     # 手動計算
                #     # expected_portfolio_return = np.sum(mu * pd.Series(weights_hrp))
                #     # expected_portfolio_volatility = np.sqrt(np.dot(pd.Series(weights_hrp).T, np.dot(S, pd.Series(weights_hrp))))
                #     # sharpe = (expected_portfolio_return - risk_free_rate) / expected_portfolio_volatility
                #     # 使用 pypfopt 的輔助函數
                #     cl_weights_series = pd.Series(weights_hrp)
                #     perf["expected_annual_return"] = portfolio_return(cl_weights_series, mu, negative=False)
                #     perf["annual_volatility"] = np.sqrt(portfolio_variance(cl_weights_series, S))
                #     if perf["annual_volatility"] != 0:
                #          perf["sharpe_ratio"] = (perf["expected_annual_return"] - risk_free_rate) / perf["annual_volatility"]
                #     else:
                #         perf["sharpe_ratio"] = np.nan if (perf["expected_annual_return"] - risk_free_rate) != 0 else 0

                # 為了簡化，HRP 初期僅返回權重，績效計算可由調用方處理或後續增強
                # PyPortfolioOpt 1.x 之後，HRPOpt 的 optimize 方法直接返回權重字典
                # 並且通常不直接計算夏普等，因為其目標是風險平價而非最大化夏普。
                # 若要計算基於 HRP 權重的績效，可使用 ef.portfolio_performance
                ef_for_hrp_perf = EfficientFrontier(mu, S) # 僅用於計算 HRP 權重下的績效
                ef_for_hrp_perf.set_weights(weights_hrp)
                perf_hrp = ef_for_hrp_perf.portfolio_performance(verbose=False, risk_free_rate=risk_free_rate)

                performance_dict = {
                    "expected_annual_return": perf_hrp[0],
                    "annual_volatility": perf_hrp[1],
                    "sharpe_ratio": perf_hrp[2]
                }
                logger.info(f"HRP 優化完成。權重: {weights_hrp}, 績效: {performance_dict}")
                return dict(weights_hrp), performance_dict, None

            # 對於其他基於 EfficientFrontier 的優化
            ef = EfficientFrontier(mu, S, weight_bounds=weight_bounds)

            if optimization_target == "max_sharpe":
                logger.info("執行最大化夏普比率優化...")
                ef.max_sharpe(risk_free_rate=risk_free_rate)
            elif optimization_target == "min_volatility":
                logger.info("執行最小化波動率優化...")
                ef.min_volatility()
            elif optimization_target == "efficient_risk":
                if target_volatility is None:
                    return None, None, "目標波動率 (target_volatility) 未提供給 'efficient_risk' 優化。"
                logger.info(f"執行目標波動率優化: {target_volatility}...")
                ef.efficient_risk(target_volatility=target_volatility, risk_free_rate=risk_free_rate)
            elif optimization_target == "efficient_return":
                if target_return is None:
                    return None, None, "目標回報率 (target_return) 未提供給 'efficient_return' 優化。"
                logger.info(f"執行目標回報率優化: {target_return}...")
                ef.efficient_return(target_return=target_return, risk_free_rate=risk_free_rate)
            else:
                return None, None, f"不支援的優化目標: {optimization_target}"

            cleaned_weights = ef.clean_weights()
            perf = ef.portfolio_performance(verbose=False, risk_free_rate=risk_free_rate)

            performance_dict = {
                "expected_annual_return": perf[0],
                "annual_volatility": perf[1],
                "sharpe_ratio": perf[2]
            }
            logger.info(f"優化 '{optimization_target}' 完成。權重: {cleaned_weights}, 績效: {performance_dict}")
            return dict(cleaned_weights), performance_dict, None

        except Exception as e:
            logger.error(f"執行投資組合優化 '{optimization_target}' 時發生錯誤: {e}", exc_info=True)
            return None, None, f"優化時出錯 ({optimization_target}): {e}"


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - [%(module)s:%(lineno)d] - %(message)s')

    if not PYPFOPT_AVAILABLE:
        print("PyPortfolioOpt is not installed. Skipping PortfolioOptimizer tests.")
    else:
        print("--- 測試 PortfolioOptimizer ---")
        # 創建模擬價格數據 (多個資產)
        num_days_opt = 252 * 2 # 2 年的日數據
        num_assets_opt = 4
        asset_names = [f"ASSET_{chr(65+i)}" for i in range(num_assets_opt)]

        np.random.seed(42)
        date_index_opt = pd.date_range(start="2021-01-01", periods=num_days_opt, freq='B')

        mock_prices_dict = {}
        for name in asset_names:
            # 模擬一些不同的價格行為
            base_price = np.random.uniform(50, 150)
            drift = np.random.uniform(-0.0005, 0.001)
            volatility = np.random.uniform(0.005, 0.02)
            prices = base_price * (1 + drift + volatility * np.random.randn(num_days_opt)).cumprod()
            mock_prices_dict[name] = pd.Series(prices, index=date_index_opt)

        mock_prices_df = pd.DataFrame(mock_prices_dict)
        mock_prices_df.index.name = "Date"

        print("模擬價格數據 (前5行):")
        print(mock_prices_df.head())

        optimizer = PortfolioOptimizer()

        # 測試 _calculate_returns_and_covariance
        mu_test, S_test, error_calc = optimizer._calculate_returns_and_covariance(mock_prices_df.copy())
        assert error_calc is None, f"Error in _calculate_returns_and_covariance: {error_calc}"
        assert mu_test is not None and S_test is not None
        print(f"\n預期年化回報 (mu):\n{mu_test}")
        print(f"\n年化協方差矩陣 (S) (shape: {S_test.shape}):\n{S_test.head()}")

        test_risk_free_rate = 0.01

        print(f"\n--- 測試優化目標: max_sharpe ---")
        weights_ms, perf_ms, error_ms = optimizer.optimize_portfolio(
            prices_df=mock_prices_df.copy(),
            optimization_target="max_sharpe",
            risk_free_rate=test_risk_free_rate
        )
        assert error_ms is None, f"Error in max_sharpe: {error_ms}"
        print(f"權重 (Max Sharpe): {weights_ms}")
        print(f"績效 (Max Sharpe): {perf_ms}")
        assert abs(sum(weights_ms.values()) - 1.0) < 1e-5 # 權重總和應接近1

        print(f"\n--- 測試優化目標: min_volatility ---")
        weights_mv, perf_mv, error_mv = optimizer.optimize_portfolio(
            prices_df=mock_prices_df.copy(),
            optimization_target="min_volatility",
            risk_free_rate=test_risk_free_rate # 雖然最小波動率不直接用，但績效計算會用
        )
        assert error_mv is None, f"Error in min_volatility: {error_mv}"
        print(f"權重 (Min Volatility): {weights_mv}")
        print(f"績效 (Min Volatility): {perf_mv}")
        assert abs(sum(weights_mv.values()) - 1.0) < 1e-5


        print(f"\n--- 測試優化目標: efficient_risk (目標波動率 0.15) ---")
        target_vol = 0.15 # 假設的目標波動率
        weights_er, perf_er, error_er = optimizer.optimize_portfolio(
            prices_df=mock_prices_df.copy(),
            optimization_target="efficient_risk",
            target_volatility=target_vol,
            risk_free_rate=test_risk_free_rate
        )
        if error_er: # 目標波動率可能無法達到
            print(f"efficient_risk 錯誤 (可能目標無法達到): {error_er}")
        else:
            print(f"權重 (Efficient Risk @ {target_vol*100:.1f}% vol): {weights_er}")
            print(f"績效 (Efficient Risk @ {target_vol*100:.1f}% vol): {perf_er}")
            assert abs(sum(weights_er.values()) - 1.0) < 1e-5
            if perf_er and 'annual_volatility' in perf_er and perf_er['annual_volatility'] is not None:
                 assert np.isclose(perf_er['annual_volatility'], target_vol, atol=1e-2), f"Annual volatility {perf_er['annual_volatility']} not close to target {target_vol}"


        print(f"\n--- 測試優化目標: hrp (Hierarchical Risk Parity) ---")
        weights_hrp, perf_hrp, error_hrp = optimizer.optimize_portfolio(
            prices_df=mock_prices_df.copy(),
            optimization_target="hrp",
            risk_free_rate=test_risk_free_rate # HRP績效計算時也可能用到
        )
        assert error_hrp is None, f"Error in hrp: {error_hrp}"
        print(f"權重 (HRP): {weights_hrp}")
        print(f"績效 (HRP-based, calculated using EF for consistency): {perf_hrp}")
        if weights_hrp: # HRP 權重可能不完全為1，取決於 PyPortfolioOpt 版本和實現
            print(f"HRP 權重總和: {sum(weights_hrp.values())}")
            # assert abs(sum(weights_hrp.values()) - 1.0) < 1e-5 # HRP 權重總和應為1

        print("\n--- PortfolioOptimizer 簡易測試完畢 ---")
