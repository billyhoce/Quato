"""Backtesting Orchestrator for QuantRocket Strategies."""
import logging
import os
import time
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Tuple

from dotenv import load_dotenv

# Load .env BEFORE importing quantrocket (it needs HOUSTON_URL at import time)
load_dotenv(Path(__file__).parent.parent / ".env")

from quantrocket import zipline
from requests.exceptions import HTTPError

from models.backtest_models import BacktestConfig, BacktestResults
from backtesting_orchestrator.utils import (
    upload_file_to_github,
    pull_files_from_github_to_quantrocket,
    wait_for_ingestion,
)

if TYPE_CHECKING:
    from services.object_store import ObjectStoreService

# Constants
INGESTION_POLL_INTERVAL = 20  # seconds
US_FREE_STOCK_BUNDLE_MIN = "usstock-free-1min"
US_FREE_STOCK_BUNDLE_DAILY = "usstock-learn-1d"
FREE_DATA_BUNDLES = [US_FREE_STOCK_BUNDLE_MIN, US_FREE_STOCK_BUNDLE_DAILY]


class BacktestingOrchestrator:
    """Orchestrates the full strategy backtesting lifecycle with QuantRocket."""

    def __init__(self) -> None:
        if os.environ.get("HOUSTON_URL") is None:
            raise ValueError(
                "QuantRocket URL must be set in the environment as 'HOUSTON_URL'."
            )
        self.prepare_free_data()

    # -------------------------------------------------------------------------
    # Data bundle preparation
    # -------------------------------------------------------------------------

    def check_ingestion_status(self, bundle_code: str) -> bool:
        existing_bundles = zipline.list_bundles()
        if bundle_code not in existing_bundles:
            raise ValueError(f"Bundle {bundle_code} does not exist.")
        return existing_bundles[bundle_code]

    def _ingest_bundle_and_wait(self, bundle_code: str) -> None:
        existing_bundles = zipline.list_bundles()
        if not existing_bundles.get(bundle_code):
            zipline.ingest_bundle(bundle_code)
            logging.info("Ingesting %s data bundle.", bundle_code)
            wait_for_ingestion(
                self.check_ingestion_status,
                bundle_code,
                poll_interval=INGESTION_POLL_INTERVAL,
            )
            logging.info("Ingestion of %s completed.", bundle_code)
        else:
            logging.info("%s data bundle is already ingested.", bundle_code)

    def prepare_free_data(self) -> None:
        """Prepare free QuantRocket data bundles for backtesting."""
        existing_bundles = zipline.list_bundles()
        for bundle_code in FREE_DATA_BUNDLES:
            if existing_bundles.get(bundle_code):
                logging.info("%s data bundle already ingested.", bundle_code)
            else:
                if bundle_code == US_FREE_STOCK_BUNDLE_MIN:
                    zipline.create_usstock_bundle(code=bundle_code, free=True)
                elif bundle_code == US_FREE_STOCK_BUNDLE_DAILY:
                    zipline.create_usstock_bundle(code=bundle_code, learn=True)
                logging.info("Created %s data bundle.", bundle_code)
                self._ingest_bundle_and_wait(bundle_code)

    # -------------------------------------------------------------------------
    # Strategy loading
    # -------------------------------------------------------------------------

    def _load_strategy(self, strategy_path: str) -> None:
        """Upload strategy file to GitHub and pull it into QuantRocket."""
        strategy_name = os.path.basename(strategy_path)
        upload_file_to_github(
            file_path=strategy_path,
            commit_message=f"Uploading strategy {strategy_name}",
            upload_location="zipline",
        )
        pull_files_from_github_to_quantrocket(
            repo=os.getenv("REPO_PATH"),
            replace=True,
        )

    # -------------------------------------------------------------------------
    # Backtest execution
    # -------------------------------------------------------------------------

    def run_backtest(self, strategy_filename: str, run_config: BacktestConfig) -> None:
        """Upload the strategy and execute the backtest via QuantRocket.

        Args:
            strategy_filename: Absolute path to the strategy .py file.
            run_config:        BacktestConfig with filepath_or_buffer already set.

        Raises:
            HTTPError: If QuantRocket returns a 4xx/5xx error (includes detailed
                       error message in the response JSON when available).
        """
        self._load_strategy(strategy_filename)
        strategy = os.path.basename(strategy_filename).removesuffix(".py")
        # mode='json' serialises date → ISO string; exclude_none skips unset optionals.
        try:
            zipline.backtest(strategy, **run_config.model_dump(mode="json", exclude_none=True))
        except HTTPError as e:
            # QuantRocket returns detailed error messages in JSON format
            # Extract and re-raise with a cleaner message
            error_detail = str(e)
            if e.response is not None:
                try:
                    error_json = e.response.json()
                    # QuantRocket format: {'status': 'error', 'msg': '...'}
                    if isinstance(error_json, dict) and 'msg' in error_json:
                        error_detail = error_json['msg']
                except Exception:
                    # If JSON parsing fails, use the original error string
                    pass

            # Re-raise with the extracted detail
            raise HTTPError(
                f"QuantRocket backtest failed: {error_detail}",
                response=e.response
            ) from e

    def generate_tear_sheet(
        self,
        path_to_results: Path,
        output_path: Optional[Path] = None,
    ) -> Path:
        """Generate a pyfolio tearsheet via QuantRocket.

        Args:
            path_to_results: Local path to the backtest results CSV.
            output_path:     Where to write the PDF (defaults to same dir).

        Returns:
            Path to the generated tear sheet PDF.
        """
        with open(path_to_results, "r") as f:
            if not f.read():
                raise ValueError(
                    f"Backtest results file {path_to_results} is empty."
                )
        pdf_path = output_path or path_to_results.with_suffix(".pdf")
        zipline.create_tearsheet(
            str(path_to_results),
            str(pdf_path),
        )
        logging.info("Generated tear sheet at %s", pdf_path)
        return pdf_path

    # -------------------------------------------------------------------------
    # End-to-end workflow
    # -------------------------------------------------------------------------

    def backtest_strategy_from_code(
        self,
        strategy_code: str,
        config: BacktestConfig,
        base_dir: Path,
        object_store: "ObjectStoreService",
        task_id: Optional[str] = None,
    ) -> Tuple[BacktestResults, str, Optional[str]]:
        """Run a full backtest from raw strategy code.

        Steps:
          1. Write strategy to a timestamped temp file.
          2. Upload to GitHub → pull into QuantRocket.
          3. Run zipline.backtest(); results CSV saved locally.
          4. Extract summary metrics via BacktestResults.from_csv().
          5. Upload raw CSV to the object store.
          6. Delete all local intermediary files.

        Args:
            strategy_code: Python source of the trading strategy.
            config:        BacktestConfig (filepath_or_buffer left None here;
                           set internally via model_copy so the input is not mutated).
            base_dir:      Root directory for temp strategy / results files.
            object_store:  ObjectStoreService for CSV persistence.
            task_id:       Optional task ID used as the object store namespace.

        Returns:
            Tuple of (BacktestResults, csv_object_key, tearsheet_object_key).
            tearsheet_object_key is None if tear sheet generation fails.

        Raises:
            Exception: Propagated to the caller on any failure; local files are
                       always cleaned up via the finally block.
        """
        strategies_dir = base_dir / "strategies"
        strategies_dir.mkdir(exist_ok=True)
        results_dir = base_dir / "backtest_results"
        results_dir.mkdir(exist_ok=True)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        strategy_path = strategies_dir / f"strategy_{timestamp}.py"
        results_file = results_dir / f"backtest_{timestamp}.csv"
        tearsheet_file = results_dir / f"backtest_{timestamp}.pdf"

        strategy_path.write_text(strategy_code)
        logging.info("Saved strategy to %s", strategy_path)

        try:
            # Build a run config with the results path set — don't mutate input.
            run_config = config.model_copy(
                update={"filepath_or_buffer": str(results_file)}
            )

            logging.info("Starting backtest (%s)...", strategy_path.name)
            start_time = time.time()
            self.run_backtest(str(strategy_path), run_config)
            execution_time = time.time() - start_time
            logging.info("Backtest completed in %.1fs", execution_time)

            # Extract summary metrics from the results CSV.
            results = BacktestResults.from_csv(str(results_file), execution_time)
            logging.info(
                "Metrics: return=%.2f%%, sharpe=%.2f, max_dd=%.2f%%",
                results.total_return * 100,
                results.sharpe_ratio,
                results.max_drawdown * 100,
            )

            # Upload the raw CSV to the object store for later download.
            store_key = task_id or timestamp
            csv_object_key = object_store.upload_backtest_csv(store_key, str(results_file))

            # Generate and upload tear sheet (non-fatal if it fails).
            tearsheet_object_key: Optional[str] = None
            try:
                self.generate_tear_sheet(results_file, tearsheet_file)
                tearsheet_object_key = object_store.upload_tearsheet(
                    store_key, str(tearsheet_file)
                )
            except Exception as exc:
                logging.warning("Tear sheet generation failed: %s", exc)

            return results, csv_object_key, tearsheet_object_key

        finally:
            # Always clean up local files regardless of success or failure.
            for path in (strategy_path, results_file, tearsheet_file):
                try:
                    path.unlink(missing_ok=True)
                except Exception as exc:
                    logging.warning("Failed to delete %s: %s", path, exc)
