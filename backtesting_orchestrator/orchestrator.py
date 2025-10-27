"""Backtesting Orchestrator for QuantRocket Strategies.

This module orchestrates the execution and analysis of strategy backtests.
"""
import logging
import os
import base64
import requests

from quantrocket import zipline
from typing import Dict, Any, Optional, List
from datetime import time
from models.backtest_models import BacktestConfig, BacktestResults, US_FREE_STOCK_BUNDLE

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
        """
        existing_bundles = zipline.list_bundles()
        if bundle_code not in existing_bundles:
            raise ValueError(f"Bundle {bundle_code} does not exist.")
        return existing_bundles[bundle_code]
    

    def prepare_free_data(self):
        """Prepare free quantrocket data bundles for backtesting."""
        existing_bundles = zipline.list_bundles()
        if US_FREE_STOCK_BUNDLE in existing_bundles and existing_bundles[US_FREE_STOCK_BUNDLE]:
            logging.info(f"{US_FREE_STOCK_BUNDLE} data bundle already ingested.")
            return
        if US_FREE_STOCK_BUNDLE not in existing_bundles:
            zipline.create_usstock_bundle(code=US_FREE_STOCK_BUNDLE, free=True)
            logging.info(f"Created {US_FREE_STOCK_BUNDLE} data bundle.")
        if not existing_bundles[US_FREE_STOCK_BUNDLE]:
            zipline.ingest_bundle(US_FREE_STOCK_BUNDLE)
            logging.info(f"Ingesting {US_FREE_STOCK_BUNDLE} data bundle.")
            while not self.check_ingestion_status(US_FREE_STOCK_BUNDLE):
                logging.info("Waiting for ingestion to complete...")
                time.sleep(20)
            logging.info(f"Ingestion of {US_FREE_STOCK_BUNDLE} completed.")


    def upload_file_to_github(self, file_path: str, commit_message: str) -> None:
        """Upload a file to a GitHub repository using the GitHub API.
        
        Args:
            file_path: The path to the file to upload
            commit_message: The commit message for the upload
        """
        with open(file_path, "rb") as f:
            content_b64 = base64.b64encode(f.read()).decode("utf-8")

        response = requests.put(
            f"https://api.github.com/repos/{os.getenv('REPO_PATH')}/contents/{os.path.basename(file_path)}",
            headers={
                "Authorization": f"BEARER {os.getenv('GITHUB_TOKEN')}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28"
            },
            json={
                "message": commit_message,
                "content": content_b64
            }
        )

        if response.status_code not in [200, 201]:
            raise Exception(f"Failed to upload file to GitHub: {response.status_code} - {response.text}")    


    def pull_files_from_github_to_quantrocket(
        repo: str,
        branch: Optional[str] = None,
        replace: Optional[bool] = None,
        skip_existing: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Clone files from a Git repository by calling QuantRocket's /codeload/repo endpoint.
        Args:
            repo: The repository name or URL
            branch: Optional branch to clone
            replace: Whether to replace existing files (mutually exclusive with skip_existing)
            skip_existing: Whether to skip existing files (mutually exclusive with replace)
        """
        houston_url = os.getenv("HOUSTON_URL")
        username = os.getenv("HOUSTON_USERNAME")
        password = os.getenv("HOUSTON_PASSWORD")

        if not houston_url:
            raise ValueError("HOUSTON_URL environment variable is not set.")

        url = houston_url.rstrip('/') + '/codeload/repo'

        params = {"repo": repo}
        if branch is not None:
            params["branch"] = branch
        if replace is not None:
            params["replace"] = str(replace)
        if skip_existing is not None:
            params["skip_existing"] = str(skip_existing)

        headers = {
            "Content-Type": "application/json"
        }

        auth = (username, password) if username and password else None

        response = requests.post(url, params=params, headers=headers, auth=auth)

        try:
            response.raise_for_status()
        except requests.HTTPError:
            raise requests.HTTPError(f"{response.status_code} {response.reason}: {response.text[:2000]}")


    def load_strategy(self, strategy_path: str) -> None:
        """Load strategy code into quantrocket using commit-pull workflow
        
        Args:
            strategy_path: The file path to the strategy code
        """
        self.upload_file_to_github(
            file_path=strategy_path,
            commit_message=f"Uploading strategy {os.path.basename(strategy_path)}"
        )
        self.pull_files_from_github_to_quantrocket(
            repo=os.getenv("REPO_PATH"),
            skip_existing=True
        )


    def run_backtest(self, strategy_filename: str, config: BacktestConfig) -> None:
        """Execute a strategy backtest.
        
        Args:
            strategy_filename: The path to the strategy code to backtest
            config: Backtest configuration
            
        Returns:
            None
        """
        self.load_strategy(strategy_filename)
        zipline.backtest(strategy_filename, config.model_dump(exclude_unset=True))

    
    def analyze_results(self, results: BacktestResults) -> Dict[str, Any]:
        """Analyze backtest results for insights.
        
        Args:
            results: BacktestResults object to analyze
            
        Returns:
            Dictionary containing analysis insights
        """
        # Placeholder implementation
        print(f"Analyzing results for strategy {results.strategy_id}")
        return {
            "performance": "moderate",
            "risk_adjusted": "acceptable",
            "suggestions": []
        }
    
    def generate_report(
        self,
        results: BacktestResults,
        output_path: Optional[str] = None
    ) -> str:
        """Generate a comprehensive backtest report.
        
        Args:
            results: BacktestResults object
            output_path: Optional path to save the report
            
        Returns:
            Report as a string (markdown format)
        """
        # Placeholder implementation
        report = f"# Backtest Report: {results.strategy_id}\n\n"
        report += f"Total Return: {results.total_return:.2%}\n"
        report += f"Sharpe Ratio: {results.sharpe_ratio:.2f}\n"
        report += f"Max Drawdown: {results.max_drawdown:.2%}\n"
        
        if output_path:
            with open(output_path, 'w') as f:
                f.write(report)
        
        return report
    
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
