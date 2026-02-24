# Quato Strategy Coder API Documentation

## Overview

REST API for AI-powered trading strategy generation and backtesting using LangGraph agents and QuantRocket.

**Base URL:** `http://localhost:8000`

## Architecture

```
Frontend → API (FastAPI) → Services Layer → Infrastructure
                            ├─ AgentService (LLM interactions)
                            ├─ StrategyManager (state management)
                            └─ BacktestOrchestrator (backtesting)
```

## Authentication

Session-based authentication using HTTP headers:
- Header: `X-Session-ID`
- Value: UUID string (auto-generated if not provided)

## Endpoints

### 1. Chat with Agent

Send a message to the AI agent to generate or modify trading strategies.

**Endpoint:** `POST /api/chat`

**Headers:**
```
X-Session-ID: <your-session-id>
Content-Type: application/json
```

**Request Body:**
```json
{
  "message": "Create a momentum strategy for tech stocks"
}
```

**Response:**
```json
{
  "message": "I've created a momentum strategy...",
  "strategy_updated": true,
  "strategy_code": "import zipline.api as algo\n...",
  "error": null
}
```

**Status Codes:**
- `200` - Success
- `500` - Server error

---

### 2. Get Current Strategy

Retrieve the current strategy code for your session.

**Endpoint:** `GET /api/strategy/current`

**Headers:**
```
X-Session-ID: <your-session-id>
```

**Response:**
```json
{
  "code": "import zipline.api as algo\n...",
  "has_strategy": true
}
```

**Status Codes:**
- `200` - Success

---

### 3. Run Backtest

Execute a backtest on the current strategy.

**Endpoint:** `POST /api/backtest`

**Headers:**
```
X-Session-ID: <your-session-id>
Content-Type: application/json
```

**Request Body:**
```json
{
  "start_date": "2023-01-01",
  "end_date": "2023-12-31",
  "capital_base": 100000
}
```

**Response:**
```json
{
  "task_id": "abc-123-def-456",
  "status": "complete",
  "message": "Backtest completed"
}
```

**Status Codes:**
- `200` - Success
- `400` - No strategy found or invalid request
- `500` - Backtest execution error

---

### 4. Get Backtest Result

Poll for backtest status and results.

**Endpoint:** `GET /api/backtest/{task_id}`

**Response:**
```json
{
  "task_id": "abc-123-def-456",
  "status": "complete",
  "success": true,
  "strategy_path": "/path/to/strategy_20230101_120000.py",
  "results_file": "/path/to/backtest_20230101_120000.csv",
  "tearsheet_file": "/path/to/tearsheet_20230101_120000.pdf",
  "error_message": null
}
```

**Status Values:**
- `running` - Backtest in progress
- `complete` - Backtest finished successfully
- `failed` - Backtest encountered an error

**Status Codes:**
- `200` - Success
- `404` - Task ID not found

---

### 5. Get Backtest History

Retrieve all past backtests for your session.

**Endpoint:** `GET /api/backtest/history`

**Headers:**
```
X-Session-ID: <your-session-id>
```

**Response:**
```json
{
  "backtests": [
    {
      "task_id": "abc-123",
      "status": "complete",
      "success": true,
      "strategy_path": "/path/to/strategy.py",
      "results_file": "/path/to/results.csv",
      "tearsheet_file": "/path/to/tearsheet.pdf"
    }
  ]
}
```

**Status Codes:**
- `200` - Success

---

### 6. Health Check

Verify API is running.

**Endpoint:** `GET /health`

**Response:**
```json
{
  "status": "healthy",
  "service": "Quato Strategy Coder API"
}
```

---

## Running the API

### Development Mode

```bash
# Navigate to project root
cd d:/repositories/Quato

# Install dependencies
pip install -r requirements.txt

# Run the API
python -m api.main
```

The API will be available at `http://localhost:8000`

### Interactive API Documentation

Once running, visit:
- **Swagger UI:** `http://localhost:8000/docs`
- **ReDoc:** `http://localhost:8000/redoc`

---

## Usage Examples

### Python Client Example

```python
import requests
import uuid

# Generate session ID
session_id = str(uuid.uuid4())
headers = {"X-Session-ID": session_id}

# 1. Chat with agent to create strategy
response = requests.post(
    "http://localhost:8000/api/chat",
    json={"message": "Create a simple moving average crossover strategy"},
    headers=headers
)
result = response.json()
print(f"Strategy updated: {result['strategy_updated']}")

# 2. Get current strategy
response = requests.get(
    "http://localhost:8000/api/strategy/current",
    headers=headers
)
strategy = response.json()
print(f"Has strategy: {strategy['has_strategy']}")

# 3. Run backtest
response = requests.post(
    "http://localhost:8000/api/backtest",
    json={
        "start_date": "2023-01-01",
        "end_date": "2023-12-31",
        "capital_base": 100000
    },
    headers=headers
)
backtest = response.json()
task_id = backtest['task_id']
print(f"Backtest status: {backtest['status']}")

# 4. Get results
response = requests.get(
    f"http://localhost:8000/api/backtest/{task_id}"
)
results = response.json()
print(f"Results file: {results['results_file']}")
```

### JavaScript/Fetch Example

```javascript
const sessionId = crypto.randomUUID();
const headers = {
  'X-Session-ID': sessionId,
  'Content-Type': 'application/json'
};

// Chat with agent
const chatResponse = await fetch('http://localhost:8000/api/chat', {
  method: 'POST',
  headers,
  body: JSON.stringify({
    message: 'Create a momentum strategy'
  })
});
const chatData = await chatResponse.json();

// Run backtest
if (chatData.strategy_updated) {
  const backtestResponse = await fetch('http://localhost:8000/api/backtest', {
    method: 'POST',
    headers,
    body: JSON.stringify({
      start_date: '2023-01-01',
      end_date: '2023-12-31',
      capital_base: 100000
    })
  });
  const backtest = await backtestResponse.json();
  
  // Poll for results
  const checkStatus = async (taskId) => {
    const response = await fetch(`http://localhost:8000/api/backtest/${taskId}`);
    return response.json();
  };
  
  const results = await checkStatus(backtest.task_id);
  console.log('Backtest complete:', results);
}
```

---

## Error Handling

All endpoints return consistent error responses:

```json
{
  "detail": "Error message describing what went wrong"
}
```

Common error scenarios:
- **400 Bad Request:** Missing session ID, no strategy found
- **404 Not Found:** Backtest task ID doesn't exist
- **500 Internal Server Error:** Agent failure, backtest execution error

---

## Session Management

Sessions are managed via the `X-Session-ID` header:

1. **Client generates UUID** on first use
2. **Stores UUID** in browser localStorage or application state
3. **Includes header** in all API requests
4. **Session persists** in API memory (lost on restart)

For production, implement:
- Redis for session persistence
- Database for long-term storage
- Session expiration policies

---

## Rate Limiting

Currently no rate limiting. For production, implement:
- Rate limiting middleware
- Per-session request limits
- Cost tracking for LLM usage

---

## Next Steps

1. **Frontend Integration:** Build React UI that calls these endpoints
2. **Real-time Updates:** Add polling for backtest status
3. **File Downloads:** Endpoints to download results CSV and tearsheet PDF
4. **Strategy History:** Version control for strategy iterations