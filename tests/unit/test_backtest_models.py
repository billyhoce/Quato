"""Unit tests for models/backtest_models.py.

These tests run entirely offline — no Redis, no QuantRocket, no LLM required.
"""
import json
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from models.backtest_models import (
    BacktestConfig,
    BacktestResults,
    TaskRecord,
    TaskStatus,
)

# Absolute path to the checked-in sample CSV used to validate the parser.
SAMPLE_CSV = (
    Path(__file__).parent.parent.parent
    / "backtesting_orchestrator"
    / "sample_backtest.csv"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _minimal_record(**overrides) -> TaskRecord:
    defaults = dict(
        task_id="abc-123",
        session_id="sess-456",
        status=TaskStatus.QUEUED,
        strategy_code="def initialize(context): pass",
        config_json=json.dumps({
            "bundle": "usstock-learn-1d",
            "start_date": "2023-01-01",
            "end_date": "2023-12-31",
        }),
        created_at=datetime(2024, 1, 15, 10, 30, 0, tzinfo=timezone.utc),
    )
    return TaskRecord(**{**defaults, **overrides})


def _minimal_csv(tmp_path, *, include_sharpe: bool = True, flat_returns: bool = False) -> Path:
    """Write a tiny two-row perf CSV and return its path."""
    returns = ["0.005", "0.005"] if flat_returns else ["0.01", "0.009"]
    rows = [
        "dataframe,index,date,column,value",
        f"perf,0,2023-01-01,algorithm_period_return,0.05",
        f"perf,0,2023-01-01,max_drawdown,-0.02",
        f"perf,0,2023-01-01,returns,{returns[0]}",
        f"perf,1,2023-01-02,algorithm_period_return,0.06",
        f"perf,1,2023-01-02,max_drawdown,-0.02",
        f"perf,1,2023-01-02,returns,{returns[1]}",
    ]
    if include_sharpe:
        rows += [
            "perf,0,2023-01-01,sharpe,1.5",
            "perf,1,2023-01-02,sharpe,1.6",
        ]
    p = tmp_path / "test.csv"
    p.write_text("\n".join(rows))
    return p


# ---------------------------------------------------------------------------
# BacktestResults.from_csv — sample CSV (real QuantRocket output)
# ---------------------------------------------------------------------------

class TestFromCsvSampleFile:
    def test_returns_valid_model(self):
        results = BacktestResults.from_csv(str(SAMPLE_CSV), execution_time=42.0)
        assert isinstance(results, BacktestResults)

    def test_execution_time_preserved(self):
        results = BacktestResults.from_csv(str(SAMPLE_CSV), execution_time=42.0)
        assert results.execution_time == 42.0

    def test_total_return_matches_expected(self):
        results = BacktestResults.from_csv(str(SAMPLE_CSV), execution_time=0.0)
        assert results.total_return == pytest.approx(0.9299, abs=0.001)

    def test_max_drawdown_matches_expected(self):
        results = BacktestResults.from_csv(str(SAMPLE_CSV), execution_time=0.0)
        assert results.max_drawdown == pytest.approx(-0.3009, abs=0.001)

    def test_sharpe_ratio_matches_expected(self):
        results = BacktestResults.from_csv(str(SAMPLE_CSV), execution_time=0.0)
        assert results.sharpe_ratio == pytest.approx(0.7712, abs=0.001)

    def test_max_drawdown_is_non_positive(self):
        results = BacktestResults.from_csv(str(SAMPLE_CSV), execution_time=0.0)
        assert results.max_drawdown <= 0


# ---------------------------------------------------------------------------
# BacktestResults.from_csv — error cases
# ---------------------------------------------------------------------------

class TestFromCsvErrors:
    def test_missing_columns_raises(self, tmp_path):
        bad = tmp_path / "bad.csv"
        bad.write_text("col1,col2\n1,2\n")
        with pytest.raises(ValueError, match="Unexpected CSV format"):
            BacktestResults.from_csv(str(bad), execution_time=0.0)

    def test_no_perf_rows_raises(self, tmp_path):
        p = tmp_path / "no_perf.csv"
        p.write_text("dataframe,index,date,column,value\nother,0,2023-01-01,returns,0.01\n")
        with pytest.raises(ValueError, match="No 'perf' rows"):
            BacktestResults.from_csv(str(p), execution_time=0.0)


# ---------------------------------------------------------------------------
# BacktestResults.from_csv — sharpe fallback
# ---------------------------------------------------------------------------

class TestFromCsvSharpeFallback:
    def test_sharpe_computed_from_returns_when_column_absent(self, tmp_path):
        p = _minimal_csv(tmp_path, include_sharpe=False)
        results = BacktestResults.from_csv(str(p), execution_time=0.0)
        assert isinstance(results.sharpe_ratio, float)

    def test_sharpe_zero_when_returns_have_no_variance(self, tmp_path):
        p = _minimal_csv(tmp_path, include_sharpe=False, flat_returns=True)
        results = BacktestResults.from_csv(str(p), execution_time=0.0)
        assert results.sharpe_ratio == 0.0

    def test_sharpe_precomputed_column_takes_priority(self, tmp_path):
        p = _minimal_csv(tmp_path, include_sharpe=True)
        results = BacktestResults.from_csv(str(p), execution_time=0.0)
        # Last sharpe row is 1.6
        assert results.sharpe_ratio == pytest.approx(1.6, abs=0.001)


# ---------------------------------------------------------------------------
# TaskRecord — Redis serialisation round-trips
# ---------------------------------------------------------------------------

class TestTaskRecordRoundTrip:
    def test_minimal_queued_record(self):
        record = _minimal_record()
        assert TaskRecord.from_redis_hash(record.to_redis_hash()) == record

    def test_complete_record_with_all_fields(self):
        record = _minimal_record(
            status=TaskStatus.COMPLETE,
            success=True,
            started_at=datetime(2024, 1, 15, 10, 31, 0, tzinfo=timezone.utc),
            completed_at=datetime(2024, 1, 15, 10, 35, 0, tzinfo=timezone.utc),
            csv_object_key="backtests/abc-123/results.csv",
            total_return=0.142,
            sharpe_ratio=1.23,
            max_drawdown=-0.08,
            execution_time=42.1,
        )
        assert TaskRecord.from_redis_hash(record.to_redis_hash()) == record

    def test_failed_record_with_error_message(self):
        record = _minimal_record(
            status=TaskStatus.FAILED,
            success=False,
            error_message="QuantRocket connection refused",
            completed_at=datetime(2024, 1, 15, 10, 32, 0, tzinfo=timezone.utc),
        )
        assert TaskRecord.from_redis_hash(record.to_redis_hash()) == record

    def test_all_status_values_round_trip(self):
        for status in TaskStatus:
            record = _minimal_record(status=status)
            assert TaskRecord.from_redis_hash(record.to_redis_hash()).status == status


# ---------------------------------------------------------------------------
# TaskRecord — success bool serialisation
# ---------------------------------------------------------------------------

class TestTaskRecordSuccessBool:
    def test_true_serialises_to_string_True(self):
        h = _minimal_record(success=True).to_redis_hash()
        assert h["success"] == "True"

    def test_false_serialises_to_string_False(self):
        h = _minimal_record(success=False).to_redis_hash()
        assert h["success"] == "False"

    def test_none_serialises_to_empty_string(self):
        h = _minimal_record(success=None).to_redis_hash()
        assert h["success"] == ""

    def test_true_deserialises_to_bool(self):
        assert TaskRecord.from_redis_hash(_minimal_record(success=True).to_redis_hash()).success is True

    def test_false_deserialises_to_bool(self):
        assert TaskRecord.from_redis_hash(_minimal_record(success=False).to_redis_hash()).success is False

    def test_none_deserialises_to_none(self):
        assert TaskRecord.from_redis_hash(_minimal_record(success=None).to_redis_hash()).success is None


# ---------------------------------------------------------------------------
# TaskRecord — float metric serialisation
# ---------------------------------------------------------------------------

class TestTaskRecordFloatMetrics:
    def test_absent_metrics_serialise_as_empty_strings(self):
        h = _minimal_record().to_redis_hash()
        for field in ("total_return", "sharpe_ratio", "max_drawdown", "execution_time"):
            assert h[field] == "", f"{field} should be empty string when None"

    def test_float_metrics_round_trip(self):
        record = _minimal_record(
            total_return=0.5,
            sharpe_ratio=-0.1,
            max_drawdown=-0.25,
            execution_time=100.0,
        )
        restored = TaskRecord.from_redis_hash(record.to_redis_hash())
        assert restored.total_return == pytest.approx(0.5)
        assert restored.sharpe_ratio == pytest.approx(-0.1)
        assert restored.max_drawdown == pytest.approx(-0.25)
        assert restored.execution_time == pytest.approx(100.0)

    def test_negative_float_round_trips(self):
        record = _minimal_record(max_drawdown=-0.9999)
        assert TaskRecord.from_redis_hash(record.to_redis_hash()).max_drawdown == pytest.approx(-0.9999)


# ---------------------------------------------------------------------------
# BacktestConfig.validate_config
# ---------------------------------------------------------------------------

class TestBacktestConfigValidation:
    def _cfg(self, **overrides) -> BacktestConfig:
        defaults = dict(
            bundle="usstock-learn-1d",
            start_date=date(2023, 1, 1),
            end_date=date(2023, 12, 31),
        )
        return BacktestConfig(**{**defaults, **overrides})

    def test_valid_config_does_not_raise(self):
        self._cfg().validate_config()

    def test_valid_config_with_capital_base(self):
        self._cfg(capital_base=50000).validate_config()

    def test_negative_capital_base_raises(self):
        with pytest.raises(ValueError, match="capital_base must be positive"):
            self._cfg(capital_base=-1000).validate_config()

    def test_zero_capital_base_raises(self):
        with pytest.raises(ValueError, match="capital_base must be positive"):
            self._cfg(capital_base=0).validate_config()

    def test_end_before_start_raises(self):
        with pytest.raises(ValueError, match="end_date.*must be after start_date"):
            self._cfg(start_date=date(2023, 6, 1), end_date=date(2023, 1, 1)).validate_config()

    def test_same_start_and_end_raises(self):
        with pytest.raises(ValueError, match="end_date.*must be after start_date"):
            self._cfg(start_date=date(2023, 1, 1), end_date=date(2023, 1, 1)).validate_config()

    def test_future_start_date_raises(self):
        with pytest.raises(ValueError, match="start_date.*cannot be in the future"):
            self._cfg(start_date=date(2099, 1, 1), end_date=date(2099, 12, 31)).validate_config()

    def test_future_end_date_raises(self):
        with pytest.raises(ValueError, match="end_date.*cannot be in the future"):
            self._cfg(start_date=date(2020, 1, 1), end_date=date(2099, 1, 1)).validate_config()

    def test_excessive_date_range_raises(self):
        with pytest.raises(ValueError, match="Date range is too large"):
            self._cfg(start_date=date(1900, 1, 1), end_date=date(2023, 12, 31)).validate_config()
