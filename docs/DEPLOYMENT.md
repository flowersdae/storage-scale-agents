# Deployment Guide

## Deployment Options

### Option 1: AgentStack UI (Container Image)

1. **Build and push the container image:**

```bash
cd scale-agents

# Build
docker build -t your-registry/scale-agents:latest .

# Push to registry
docker push your-registry/scale-agents:latest
```

2. **Add to AgentStack UI:**
   - Click "Add new agent"
   - Select "Container image URL"
   - Enter: `your-registry/scale-agents:latest`
   - Click "Add new agent"

### Option 2: AgentStack UI (GitHub Repository)

1. **Push to GitHub:**

```bash
cd scale-agents
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/your-org/scale-agents.git
git push -u origin main
```

2. **Add to AgentStack UI:**
   - Click "Add new agent"
   - Select "Github repository URL"
   - Enter: `https://github.com/your-org/scale-agents`
   - Click "Add new agent"

### Option 3: Local Development

```bash
cd scale-agents

# Create virtual environment
uv venv
source .venv/bin/activate

# Install dependencies
uv pip install -e ".[all]"

# Configure
cp config.yaml.template config.yaml
# Edit config.yaml with your settings

# Run
uv run server
```

### Option 4: Docker Compose

```bash
cd scale-agents

# Configure
cp config.yaml.template config.yaml
# Edit config.yaml

# Start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

## Configuration

### Required Configuration

Edit `config.yaml` or set environment variables:

```yaml
mcp:
  server_url: "http://163.66.86.14:8000/mcp"  # Your MCP server
```

### LLM Configuration (Optional)

```yaml
llm:
  enabled: true
  provider: "ollama"
  model: "qwen3:30b-a3b"
  base_url: "http://localhost:11434"
```

## Verification

### Check Server Status

```bash
# Health check
curl http://localhost:8080/health

# List agents
curl http://localhost:8080/agents
```

### Test via AgentStack CLI

```bash
# If using AgentStack CLI
agentstack run scale_orchestrator "What is the cluster health status?"
```

## Production Deployment

### Kubernetes

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: scale-agents
spec:
  replicas: 2
  selector:
    matchLabels:
      app: scale-agents
  template:
    metadata:
      labels:
        app: scale-agents
    spec:
      containers:
      - name: scale-agents
        image: your-registry/scale-agents:latest
        ports:
        - containerPort: 8080
        env:
        - name: SCALE_AGENTS_MCP_SERVER_URL
          value: "http://scale-mcp-server:8000/mcp"
        - name: SCALE_AGENTS_LLM_ENABLED
          value: "true"
        - name: SCALE_AGENTS_LLM_PROVIDER
          value: "ollama"
        - name: SCALE_AGENTS_LLM_MODEL
          value: "qwen3:30b-a3b"
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
        readinessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
        resources:
          requests:
            cpu: 500m
            memory: 512Mi
          limits:
            cpu: 2000m
            memory: 2Gi
---
apiVersion: v1
kind: Service
metadata:
  name: scale-agents
spec:
  selector:
    app: scale-agents
  ports:
  - port: 8080
    targetPort: 8080
```

### Environment Variables Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `SCALE_AGENTS_MCP_SERVER_URL` | MCP server endpoint | `http://127.0.0.1:8000/mcp` |
| `SCALE_AGENTS_HOST` | Server bind host | `0.0.0.0` |
| `SCALE_AGENTS_PORT` | Server bind port | `8080` |
| `SCALE_AGENTS_LLM_ENABLED` | Enable LLM reasoning | `false` |
| `SCALE_AGENTS_LLM_PROVIDER` | LLM provider | `ollama` |
| `SCALE_AGENTS_LLM_MODEL` | LLM model name | |
| `SCALE_AGENTS_LLM_BASE_URL` | Ollama base URL | `http://localhost:11434` |
| `SCALE_AGENTS_REQUIRE_CONFIRMATION` | Confirm destructive ops | `true` |
| `SCALE_AGENTS_LOG_LEVEL` | Log level | `INFO` |
