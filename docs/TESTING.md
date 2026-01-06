# Testing Guide

## Prerequisites

1. **MCP Server**: Running instance of scale-mcp-server at `http://163.66.86.14:8000/mcp`
2. **Ollama** (optional): Running locally with `qwen3:30b-a3b` model

## Quick Test

### 1. Start the Agent Server

```bash
cd scale-agents

# Install
uv venv && source .venv/bin/activate
uv pip install -e .

# Run
uv run server
```

### 2. Test Health Check

```bash
curl http://localhost:8080/health
```

Expected: `{"status": "healthy"}`

### 3. Test Agent Endpoint

```bash
# Test orchestrator
curl -X POST http://localhost:8080/agents/scale_orchestrator/run \
  -H "Content-Type: application/json" \
  -d '{"message": "What is the cluster health status?"}'
```

## Unit Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=scale_agents --cov-report=html

# Specific test file
pytest tests/test_orchestrator.py -v

# Specific test
pytest tests/test_orchestrator.py::test_health_intent_classification -v
```

## Integration Tests

### Test Against Live MCP Server

```bash
# Set MCP server URL
export SCALE_AGENTS_MCP_SERVER_URL=http://163.66.86.14:8000/mcp

# Run integration tests
pytest tests/integration/ -v
```

### Manual Testing Script

Create `test_agents.py`:

```python
#!/usr/bin/env python3
"""Manual agent testing script."""

import asyncio
import httpx

BASE_URL = "http://localhost:8080"

async def test_agent(agent: str, message: str) -> None:
    """Test an agent with a message."""
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/agents/{agent}/run",
            json={"message": message},
            timeout=60.0,
        )
        print(f"\n{'='*60}")
        print(f"Agent: {agent}")
        print(f"Query: {message}")
        print(f"Status: {response.status_code}")
        print(f"Response:\n{response.json()}")

async def main() -> None:
    """Run test queries."""
    tests = [
        # Orchestrator routing
        ("scale_orchestrator", "help"),
        ("scale_orchestrator", "What is the cluster health?"),
        ("scale_orchestrator", "List all filesystems"),
        ("scale_orchestrator", "Show quota usage"),
        
        # Direct agent access
        ("health_agent", "Show node health status"),
        ("storage_agent", "List filesets in gpfs01"),
        ("quota_agent", "What is the usage of fileset data?"),
        ("admin_agent", "List snapshots"),
    ]
    
    for agent, message in tests:
        try:
            await test_agent(agent, message)
        except Exception as e:
            print(f"Error testing {agent}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
```

Run:
```bash
python test_agents.py
```

## Test Categories

### 1. Intent Classification

```python
# tests/test_intent.py
import pytest
from scale_agents.agents.orchestrator import Orchestrator, Intent

@pytest.fixture
def orchestrator():
    return Orchestrator()

@pytest.mark.parametrize("query,expected", [
    ("Are there unhealthy nodes?", Intent.HEALTH),
    ("List filesystems", Intent.STORAGE),
    ("Set quota to 10TB", Intent.QUOTA),
    ("Why is it slow?", Intent.PERFORMANCE),
    ("Create snapshot", Intent.ADMIN),
])
def test_intent_classification(orchestrator, query, expected):
    result = orchestrator._classify_intent(query)
    assert result.intent == expected
```

### 2. Tool Whitelisting

```python
# tests/test_security.py
import pytest
from scale_agents.config.tool_mappings import (
    HEALTH_TOOLS,
    DESTRUCTIVE_TOOLS,
    is_tool_allowed,
)

def test_health_agent_no_destructive():
    """Health agent should not have destructive tools."""
    overlap = HEALTH_TOOLS & DESTRUCTIVE_TOOLS
    assert len(overlap) == 0

def test_tool_whitelist_enforcement():
    """Verify tool whitelist enforcement."""
    assert is_tool_allowed("get_nodes_status", "health")
    assert not is_tool_allowed("delete_fileset", "health")
```

### 3. Confirmation Gates

```python
# tests/test_confirmation.py
import pytest
from scale_agents.tools.confirmable import requires_confirmation

def test_destructive_ops_need_confirmation():
    """Destructive operations require confirmation."""
    assert requires_confirmation("delete_fileset")
    assert requires_confirmation("delete_snapshot")
    assert not requires_confirmation("list_filesystems")
```

### 4. Response Formatting

```python
# tests/test_formatting.py
from scale_agents.tools.response_formatter import format_response

def test_health_response_format():
    """Health responses should be formatted correctly."""
    data = {
        "nodes": [
            {"name": "node1", "status": "HEALTHY"},
            {"name": "node2", "status": "DEGRADED"},
        ]
    }
    result = format_response(data, "health")
    assert "node1" in result
    assert "HEALTHY" in result
```

## Load Testing

```bash
# Install hey
brew install hey  # macOS
# or
go install github.com/rakyll/hey@latest

# Run load test
hey -n 1000 -c 50 -m POST \
    -H "Content-Type: application/json" \
    -d '{"message": "cluster health"}' \
    http://localhost:8080/agents/scale_orchestrator/run
```

## CI/CD Testing

```yaml
# .github/workflows/test.yml
name: Test

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          
      - name: Install uv
        run: pip install uv
        
      - name: Install dependencies
        run: uv pip install --system -e ".[dev]"
        
      - name: Run linting
        run: |
          ruff check src/
          ruff format --check src/
          
      - name: Run type checking
        run: mypy src/
        
      - name: Run tests
        run: pytest --cov=scale_agents --cov-report=xml
        
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          file: coverage.xml
```

## Debugging

### Enable Debug Logging

```bash
SCALE_AGENTS_LOG_LEVEL=DEBUG uv run server
```

### Check MCP Connection

```python
import asyncio
from scale_agents.tools.mcp_client import MCPClient

async def test_mcp():
    client = MCPClient("http://163.66.86.14:8000/mcp")
    async with client:
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {len(tools)}")
        for tool in tools[:10]:
            print(f"  - {tool['name']}")

asyncio.run(test_mcp())
```

### Check LLM Connection

```python
import asyncio
from scale_agents.core.reasoning import get_reasoner

async def test_llm():
    reasoner = get_reasoner()
    print(f"LLM enabled: {reasoner.enabled}")
    
    if reasoner.enabled:
        result = await reasoner.classify_intent("show cluster health")
        print(f"Intent: {result.intent}")
        print(f"Confidence: {result.confidence}")

asyncio.run(test_llm())
```
