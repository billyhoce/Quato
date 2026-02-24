"""Backtesting Orchestrator for QuantRocket Strategies.

This module orchestrates the execution and analysis of strategy backtests.
"""
import logging
import os

from pathlib import Path
from datetime import datetime
from quantrocket import zipline
from typing import Dict, Any, Optional, List
from models.backtest_models import BacktestConfig, BacktestResults, US_FREE_STOCK_BUNDLE
from backtesting_orchestrator.utils import (
    upload_file_to_github,
    pull_files_from_github_to_quantrocket,
    wait_for_ingestion,
    generate_markdown_report
)

# Constants
INGESTION_POLL_INTERVAL = 20  # seconds

class BacktestingOrchestrator:
    """Orchestrates strategy backtesting with QuantRocket.
    
    This class manages the full backtesting lifecycle including data preparation,
    execution, performance analysis, and result reporting.
    """
    
    def __init__(self) -> None:
        """Initialize the backtesting orchestrator.
        
        Args:
            quantrocket_url: URL of the QuantRocket instance (if None, uses default)
        """
        if os.environ.get("HOUSTON_URL") is None:
            raise ValueError("QuantRocket URL must be set in the environment as 'HOUSTON_URL'.")
        self.results_cache: Dict[str, BacktestResults] = {}

    def check_ingestion_status(self, bundle_code: str) -> bool:
        """Check if the specified data bundle is ingested and ready for backtesting.
        
        Args:
            bundle_code: The code of the data bundle to check
            
        Returns:
            True if bundle is ingested, False otherwise
        """
        existing_bundles = zipline.list_bundles()
        if bundle_code not in existing_bundles:
            raise ValueError(f"Bundle {bundle_code} does not exist.")
        return existing_bundles[bundle_code]

    def _create_bundle_if_needed(self, bundle_code: str) -> None:
        """Create a bundle if it doesn't exist.
        
        Args:
            bundle_code: The code of the data bundle to create
        """
        existing_bundles = zipline.list_bundles()
        if bundle_code not in existing_bundles:
            zipline.create_usstock_bundle(code=bundle_code, free=True)
            logging.info(f"Created {bundle_code} data bundle.")

    def _ingest_bundle_if_needed(self, bundle_code: str) -> None:
        """Ingest a bundle if it hasn't been ingested yet.
        
        Args:
            bundle_code: The code of the data bundle to ingest
        """
        existing_bundles = zipline.list_bundles()
        if not existing_bundles.get(bundle_code):
            zipline.ingest_bundle(bundle_code)
            logging.info(f"Ingesting {bundle_code} data bundle.")
            wait_for_ingestion(
                self.check_ingestion_status,
                bundle_code,
                poll_interval=INGESTION_POLL_INTERVAL
            )
            logging.info(f"Ingestion of {bundle_code} completed.")
    
    def prepare_free_data(self) -> None:
        """Prepare free quantrocket data bundles for backtesting."""
        existing_bundles = zipline.list_bundles()
        
        # Check if already ingested
        if US_FREE_STOCK_BUNDLE in existing_bundles and existing_bundles[US_FREE_STOCK_BUNDLE]:
            logging.info(f"{US_FREE_STOCK_BUNDLE} data bundle already ingested.")
            return
        
        # Create bundle if needed
        self._create_bundle_if_needed(US_FREE_STOCK_BUNDLE)
        
        # Ingest bundle if needed
        self._ingest_bundle_if_needed(US_FREE_STOCK_BUNDLE)


    # def move_strategy_file_into_zipline_dir(self, strategy_file_name: str) -> None:
    #     """Move a strategy file into the QuantRocket Zipline strategies directory.
    #     Uses quantrocket satelite api to run the script on the houston instance.
        
    #     Args:
    #         strategy_file_name: Name of the strategy file to move
    #     """
    #     script = f"mv {strategy_file_name} zipline/{strategy_file_name}"
    #     satellite.execute_command(script)


    def _load_strategy(self, strategy_path: str) -> None:
        """Load strategy code into quantrocket using commit-pull workflow
        
        Args:
            strategy_path: The file path to the strategy code
        """
        strategy_name = os.path.basename(strategy_path)
        upload_file_to_github(
            file_path=strategy_path,
            commit_message=f"Uploading strategy {strategy_name}",
            upload_location="zipline"
        )
        pull_files_from_github_to_quantrocket(
            repo=os.getenv("REPO_PATH"),
            skip_existing=True
        )
        # self.move_strategy_file_into_zipline_dir(strategy_name)



    def run_backtest(self, strategy_filename: str, config: BacktestConfig) -> None:
        """Execute a strategy backtest.
        
        Args:
            strategy_filename: The path to the strategy code to backtest
            config: Backtest configuration
            
        Returns:
            None
        """
        self._load_strategy(strategy_filename)
        strategy = os.path.basename(strategy_filename).strip(".py")

        zipline.backtest(strategy,
                         **config.model_dump(exclude_unset=True))

        
    def generate_tear_sheet(
        self,
        path_to_results: Path,
        output_path: Optional[str] = None
    ) -> None:
        """Uses pyfolio in Quantrocket to generate tear sheet.

        Args:
            path_to_results: Path to the backtest results file
            output_path: Optional path to save the tear sheet
        """
        with open(path_to_results, 'r') as f:
            data = f.read()
            if not data:
                raise ValueError(f"Backtest results file {path_to_results} is empty.")
        return zipline.create_tearsheet(
            path_to_results,
            output_path if output_path is not None else path_to_results.parent / "tearsheet.pdf"
        )
    
    def backtest_strategy_from_code(
        self,
        strategy_code: str,
        config: BacktestConfig,
        base_dir: Path,
        strategy_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Complete end-to-end backtesting workflow from strategy code.
        
        Handles:
        - Saving strategy to file
        - Directory management
        - Running backtest
        - Generating tearsheet
        - Logging all steps
        - Error handling
        
        Args:
            strategy_code: Python code for the strategy
            config: BacktestConfig object with backtest parameters
            base_dir: Base directory for saving files
            strategy_name: Optional name for the strategy (auto-generated if None)
            
        Returns:
            Dictionary with:
                - success: bool
                - strategy_path: str path to saved strategy file
                - results_file: str path to backtest results CSV
                - tearsheet_file: str path to tearsheet PDF
                - error_message: str error message if failed
        """
        
        result = {
            "success": False,
            "strategy_path": None,
            "results_file": None,
            "tearsheet_file": None,
            "error_message": None
        }
        
        try:
            # Create directories
            strategies_dir = base_dir / "strategies"
            strategies_dir.mkdir(exist_ok=True)
            results_dir = base_dir / "backtest_results"
            results_dir.mkdir(exist_ok=True)
            
            # Generate timestamp and filenames
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            if strategy_name:
                filename = f"{strategy_name}_{timestamp}.py"
            else:
                filename = f"strategy_{timestamp}.py"
            
            strategy_path = strategies_dir / filename
            results_file = results_dir / f"backtest_{timestamp}.csv"
            tearsheet_file = results_dir / f"tearsheet_{timestamp}.pdf"
            
            # Save strategy code
            logging.info(f"Saving strategy to: {strategy_path}")
            with open(strategy_path, 'w') as f:
                f.write(strategy_code)
            result["strategy_path"] = str(strategy_path)
            
            # Update config with results file path if not set
            if config.filepath_or_buffer is None:
                config.filepath_or_buffer = str(results_file)
            
            # Run backtest
            logging.info(f"Starting backtest for {filename}...")
            self.run_backtest(str(strategy_path), config)
            result["results_file"] = str(config.filepath_or_buffer)
            logging.info(f"Backtest completed. Results saved to: {config.filepath_or_buffer}")
            
            # Generate tearsheet
            logging.info("Generating tearsheet...")
            self.generate_tear_sheet(Path(config.filepath_or_buffer), str(tearsheet_file))
            result["tearsheet_file"] = str(tearsheet_file)
            logging.info(f"Tearsheet generated: {tearsheet_file}")
            
            result["success"] = True
            return result
            
        except Exception as e:
            error_msg = f"Backtest failed: {str(e)}"
            logging.error(error_msg, exc_info=True)
            result["error_message"] = error_msg
            return result
    
    def compare_strategies(
        self,
        strategy_ids: List[str]
    ) -> Dict[str, Any]:
        """Compare performance of multiple strategies.
        
        Args:
            strategy_ids: List of strategy IDs to compare
            
        Returns:
            Dictionary containing comparison results
        """
        # Placeholder implementation
        print(f"Comparing {len(strategy_ids)} strategies")
        return {}
