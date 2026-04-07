from datetime import date, datetime
from enum import StrEnum
from typing import Any, Dict, Optional

import pandas as pd
from pydantic import BaseModel

US_FREE_STOCK_BUNDLE_MIN = "usstock-free-1min"
US_FREE_STOCK_BUNDLE_DAILY = "usstock-learn-1d"


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"


class BacktestConfig(BaseModel):
    """Configuration passed directly to QuantRocket's zipline.backtest().

    Required fields (must always be provided):
        bundle:              Data bundle to use (e.g. "usstock-learn-1d").
        start_date:          Start date of the simulation.
        end_date:            End date of the simulation.

    Optional fields (omit to use QuantRocket / bundle defaults):
        data_frequency:      "daily" or "minute" (alias "d"/"m").
                             Only needed to request daily data from a minute bundle.
        capital_base:        Starting capital (QuantRocket default: 1,000,000).
        progress:            pandas offset alias for progress logging, e.g. "M", "W", "D".
        params:              Dict of module-level algo attributes to override before run.
        filepath_or_buffer:  Path to write the results CSV.
                             Left None when stored in Redis; set by the orchestrator
                             immediately before calling zipline.backtest().
    """

    bundle: str
    start_date: date
    end_date: date
    data_frequency: Optional[str] = None
    capital_base: Optional[float] = None
    progress: Optional[str] = None
    params: Optional[Dict[str, Any]] = None
    filepath_or_buffer: Optional[str] = None

    def validate_config(self) -> None:
        """Validate backtest configuration parameters.

        Raises:
            ValueError: If configuration is invalid.
        """
        today = date.today()

        if self.capital_base is not None and self.capital_base <= 0:
            raise ValueError(f"capital_base must be positive, got {self.capital_base}")

        if self.end_date <= self.start_date:
            raise ValueError(
                f"end_date ({self.end_date}) must be after start_date ({self.start_date})"
            )

        if self.start_date > today:
            raise ValueError(f"start_date ({self.start_date}) cannot be in the future")

        if self.end_date > today:
            raise ValueError(f"end_date ({self.end_date}) cannot be in the future")

        date_range = (self.end_date - self.start_date).days
        max_days = 50 * 365
        if date_range > max_days:
            raise ValueError(
                f"Date range is too large ({date_range} days). Maximum is {max_days} days (50 years)"
            )


class BacktestResults(BaseModel):
    """Performance metrics extracted from a completed backtest."""

    total_return: float
    sharpe_ratio: float
    max_drawdown: float
    execution_time: float  # seconds

    @classmethod
    def from_csv(cls, csv_path: str, execution_time: float) -> "BacktestResults":
        """Extract performance metrics from a QuantRocket Zipline backtest CSV.

        The CSV uses a long (melted) format with columns:
            dataframe, index, date, column, value

        This method pivots the 'perf' dataframe rows to wide format, then reads
        Zipline's pre-computed columns (algorithm_period_return, max_drawdown,
        sharpe) directly. The sharpe ratio is computed from daily returns only
        when Zipline has not pre-computed it.

        Args:
            csv_path:        Path to the backtest results CSV file.
            execution_time:  Wall-clock seconds the backtest took to run.

        Raises:
            ValueError: If the CSV cannot be parsed into the expected format.
        """
        df = pd.read_csv(csv_path)

        required_cols = {"dataframe", "date", "column", "value"}
        if not required_cols.issubset(df.columns):
            raise ValueError(
                f"Unexpected CSV format at '{csv_path}'. "
                f"Expected columns {required_cols}, got {set(df.columns)}."
            )

        # Pivot the perf rows to wide format: one row per trading day
        perf_wide = (
            df[df["dataframe"] == "perf"]
            .pivot_table(index="date", columns="column", values="value", aggfunc="first")
        )

        if perf_wide.empty:
            raise ValueError(f"No 'perf' rows found in backtest CSV at '{csv_path}'.")

        # Convert relevant columns to numeric (some cols like positions are JSON strings)
        for col in ("algorithm_period_return", "returns", "max_drawdown", "sharpe"):
            if col in perf_wide.columns:
                perf_wide[col] = pd.to_numeric(perf_wide[col], errors="coerce")

        # Total return: Zipline's cumulative algorithm_period_return, last row
        total_return = float(perf_wide["algorithm_period_return"].dropna().iloc[-1])

        # Max drawdown: Zipline's running max_drawdown, last row (most negative)
        max_drawdown = float(perf_wide["max_drawdown"].dropna().iloc[-1])

        # Sharpe: use Zipline's pre-computed value; fall back to annualised calculation
        if "sharpe" in perf_wide.columns and perf_wide["sharpe"].notna().any():
            sharpe_ratio = float(perf_wide["sharpe"].dropna().iloc[-1])
        else:
            returns = perf_wide["returns"].dropna()
            std = returns.std()
            sharpe_ratio = float(returns.mean() / std * (252 ** 0.5)) if std != 0 else 0.0

        return cls(
            total_return=total_return,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            execution_time=execution_time,
        )


class TaskRecord(BaseModel):
    """A backtest task as stored in the Redis hash.

    All fields that can be absent (e.g. metrics set only on completion) are
    Optional so that partial updates from the worker round-trip cleanly.
    """

    task_id: str
    session_id: str
    status: TaskStatus
    strategy_code: str
    config_json: str  # JSON-encoded BacktestConfig dict
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    success: Optional[bool] = None
    csv_object_key: Optional[str] = None  # object store key for the results CSV
    tearsheet_object_key: Optional[str] = None  # object store key for the tear sheet PDF
    # Performance metrics — populated on successful completion
    total_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    execution_time: Optional[float] = None

    @classmethod
    def from_redis_hash(cls, data: Dict[str, str]) -> "TaskRecord":
        """Deserialize a TaskRecord from a Redis HGETALL result.

        Redis stores all values as strings; this method converts them back to
        their proper Python types before constructing the model.
        """
        parsed: Dict[str, Any] = dict(data)

        # Empty string → None for optional string/datetime fields
        for field in ("started_at", "completed_at", "error_message", "csv_object_key", "tearsheet_object_key"):
            if field in parsed and parsed[field] == "":
                parsed[field] = None

        # "True"/"False" string → bool (or None if missing/empty)
        if "success" in parsed:
            val = parsed["success"]
            parsed["success"] = (val.lower() == "true") if val else None

        # Numeric metrics: non-empty string → float, empty → None
        for field in ("total_return", "sharpe_ratio", "max_drawdown", "execution_time"):
            val = parsed.get(field, "")
            parsed[field] = float(val) if val else None

        # Pydantic v2 handles ISO datetime strings and TaskStatus coercion natively.
        return cls(**parsed)

    def to_redis_hash(self) -> Dict[str, str]:
        """Serialize a TaskRecord to a Redis-compatible mapping (all string values)."""
        result: Dict[str, str] = {}
        for field, value in self.model_dump().items():
            if value is None:
                result[field] = ""
            elif isinstance(value, bool):
                result[field] = str(value)
            elif isinstance(value, datetime):
                result[field] = value.isoformat()
            else:
                result[field] = str(value)
        return result
