# Automatic Agent Retry Implementation

## Overview

The system now automatically retries failed backtests when the agent generates syntactically or semantically incorrect strategy code. The worker detects code errors, sends feedback to the agent, and retries with the corrected code — all without manual intervention.

## How It Works

### 1. Error Detection
When `zipline.backtest()` fails, the orchestrator extracts detailed error messages from QuantRocket's HTTPError response:

**Before:**
```python
zipline.backtest(strategy, **run_config)
# HTTPError raised with generic message
```

**After:**
```python
try:
    zipline.backtest(strategy, **run_config)
except HTTPError as e:
    # Extract QuantRocket's detailed error from JSON response
    error_json = e.response.json()
    error_detail = error_json.get('msg', str(e))
    raise HTTPError(f"QuantRocket backtest failed: {error_detail}", response=e.response)
```

### 2. Automatic Retry Loop
The worker now implements a retry loop with agent feedback:

```python
retry_count = 0
strategy_code = original_code
while retry_count <= MAX_AGENT_RETRIES:
    try:
        # Run backtest
        results = orchestrator.backtest_strategy_from_code(strategy_code, ...)
        # Success! Mark complete and exit
        return
    except Exception as error:
        if is_retryable_code_error(error) and retry_count < MAX_AGENT_RETRIES:
            # Ask agent to fix the code
            strategy_code = get_agent_correction(session_id, strategy_code, error)
            retry_count += 1
            continue
        else:
            # Not retryable or max retries reached
            break
```

### 3. Agent Feedback
When a code error is detected, the worker sends a detailed message to the agent:

```
The trading strategy you generated failed during backtesting with this error:

```
cannot set context.spy to an Asset object in initialize() because doing so
will cause the Asset to become stale in live trading. Please set this context
variable in before_trading_start() instead.
```

Please fix the strategy code to resolve this error. Remember to follow
QuantRocket's Zipline API constraints and best practices.
```

The agent then:
1. Analyzes the error message
2. Identifies the issue in the code
3. Generates corrected strategy code
4. Returns it via the normal chat flow

### 4. Retry Criteria
Errors are only retried if they match common code error patterns:

- **Syntax errors**: `SyntaxError`, `IndentationError`
- **Runtime errors**: `NameError`, `AttributeError`, `TypeError`
- **API misuse**: "cannot set context.", "in initialize()", "is not defined", "has no attribute"
- **Function signature issues**: "takes N positional arguments", "unexpected keyword argument"

Other errors (network issues, data problems, system failures) are not retried automatically.

## Configuration

Set the maximum number of retry attempts in [config.py](../config.py):

```python
MAX_AGENT_RETRIES: int = 5  # Default: 5 retries (6 total attempts)
```

## Example Flow

### Scenario: Agent sets Asset in initialize()

1. **User request**: "Create a strategy that trades SPY"

2. **Agent generates code** (with bug):
```python
def initialize(context):
    context.spy = symbol('SPY')  # ❌ Wrong: Assets become stale
```

3. **Backtest fails** with error:
```
cannot set context.spy to an Asset object in initialize() because doing so
will cause the Asset to become stale in live trading. Please set this context
variable in before_trading_start() instead.
```

4. **Worker sends error to agent** (attempt 1 of 5)

5. **Agent generates corrected code**:
```python
def initialize(context):
    pass  # ✅ Correct: No Asset objects stored in initialize

def before_trading_start(context, data):
    context.spy = symbol('SPY')  # ✅ Correct: Set in before_trading_start
```

6. **Worker retries backtest** with corrected code

7. **Backtest succeeds** → task marked complete

The entire process is transparent to the user — they simply poll `/api/backtest/{task_id}` and eventually receive a successful result.

## Benefits

1. **Automatic error correction**: No manual retry needed
2. **Faster iterations**: Agent learns from mistakes immediately
3. **Better user experience**: Users get working strategies without intervention
4. **Scalable**: Handles up to 5 retries (configurable)
5. **Intelligent**: Only retries on fixable code errors, not infrastructure issues

## Monitoring

Check logs to see retry behavior:

```
2026-03-09 23:57:05 - services.backtest_worker - INFO - Processing task dfc37817
2026-03-09 23:57:07 - services.backtest_worker - INFO - Backtest failed with code error (attempt 1/6), requesting agent fix...
2026-03-09 23:57:10 - services.backtest_worker - INFO - Agent provided corrected strategy, retrying...
2026-03-09 23:57:25 - services.backtest_worker - INFO - Task dfc37817 complete after 2 attempt(s)
```

## Limitations

- **Token cost**: Each retry consumes LLM tokens
- **Time**: Retries add ~5-10 seconds per attempt (agent response time)
- **Not guaranteed**: Agent might not fix the issue even after 5 retries
- **Lock holding**: Lock is held during all retries (other tasks wait)

## Future Enhancements

- [ ] Add retry metrics to task record (attempts, retry history)
- [ ] Implement exponential backoff between retries
- [ ] Save intermediate failed strategies for debugging
- [ ] Add cost tracking for retry token usage
- [ ] Implement smarter retry logic (e.g., semantic analysis of errors)
