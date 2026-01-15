# Hermes

> **Bravo Zero Prompt Engineering Platform**

Hermes is the centralized prompt engineering platform for the Bravo Zero ecosystem. It provides version-controlled storage, automated benchmarking, and continuous improvement capabilities for all prompt types.

---

## Features

- **Prompt Management**: CRUD operations for all prompt types (agent, template, tool, MCP)
- **Version Control**: Semantic versioning with full history, diff engine, and rollback
- **Benchmarking**: Automated quality assessment via ATE integration with dimensional scoring
- **Quality Gates**: Automated quality checks before deployment (score thresholds, regression detection)
- **A/B Testing**: Statistical experimentation framework for prompt optimization
- **Self-Critique**: AI-powered improvement suggestions via ASRBS
- **Autonomous Agent**: Continuous improvement via aria.hermes autonomous agent
- **Access Control**: Multi-level RBAC integrated with PERSONA, API key management
- **Search**: Full-text search with Elasticsearch/OpenSearch
- **Real-time Sync**: WebSocket-based live updates
- **Nursery Sync**: Bidirectional sync with ARIA agent prompts repository
- **IDE Integration**: Logos VS Code extension for in-editor prompt management
- **Hydra SDK**: TypeScript SDK with React hooks for UI integration
- **Audit Logging**: Complete audit trail for all operations
- **Import/Export**: Bulk import/export of prompts (JSON, CSV, Markdown, ZIP)

---

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 20+
- Docker & Docker Compose
- PostgreSQL 15+
- Redis 7+
- Elasticsearch 8+

### Development Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/DeepCreative/Hermes.git
   cd Hermes
   ```

2. **Start infrastructure with Docker Compose**
   ```bash
   docker compose up -d postgres redis elasticsearch
   ```

3. **Install Python dependencies**
   ```bash
   pip install -e ".[dev]"
   ```

4. **Run database migrations**
   ```bash
   alembic upgrade head
   ```

5. **Start the API server**
   ```bash
   uvicorn hermes.main:app --reload --port 8080
   ```

6. **Start the web UI** (in another terminal)
   ```bash
   cd web
   npm install
   npm run dev
   ```

7. **Open the application**
   - API: http://localhost:8080
   - Web UI: http://localhost:3000
   - API Docs: http://localhost:8080/docs

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                       HERMES PLATFORM                         │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                    WEB APPLICATION                     │ │
│  │  React + TypeScript + Sunset Design System             │ │
│  └────────────────────────────────────────────────────────┘ │
│                              │                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                    API GATEWAY                         │ │
│  │  FastAPI (REST) + gRPC + WebSocket                     │ │
│  └────────────────────────────────────────────────────────┘ │
│                              │                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                   CORE SERVICES                        │ │
│  │  Prompt Store │ Version Control │ RBAC │ Benchmark     │ │
│  └────────────────────────────────────────────────────────┘ │
│                              │                               │
│  ┌────────────────────────────────────────────────────────┐ │
│  │                    DATA LAYER                          │ │
│  │  PostgreSQL │ Redis │ Elasticsearch                    │ │
│  └────────────────────────────────────────────────────────┘ │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## API Reference

Full API documentation: [cognitive-architecture-docs/systems/hermes/api-reference.md](../cognitive-architecture-docs/systems/hermes/api-reference.md)

### Core APIs

| Category | Endpoints |
|----------|-----------|
| **Prompts** | CRUD, search, import/export |
| **Versions** | History, diff, rollback |
| **Benchmarks** | Run, results, trends |
| **Quality Gates** | Evaluate, status |
| **Experiments** | A/B testing |
| **Agent** | Autonomous improvement |
| **Audit** | Logs, history |
| **API Keys** | Create, revoke, rotate |

### gRPC API

Available on port 50051 with services for:
- `PromptService` - Prompt CRUD operations
- `VersionService` - Version control
- `BenchmarkService` - Benchmark execution
- `DeploymentService` - Multi-app deployment
- `NurseryService` - Sync with ARIA Nursery

---

## Configuration

Environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection URL | Required |
| `REDIS_URL` | Redis connection URL | Required |
| `ELASTICSEARCH_URL` | Elasticsearch URL | Required |
| `PERSONA_URL` | PERSONA auth service URL | Required |
| `ATE_GRPC_URL` | ATE benchmark service URL | Optional |
| `ASRBS_GRPC_URL` | ASRBS critique service URL | Optional |
| `BEEPER_URL` | Beeper notification URL | Optional |
| `LOG_LEVEL` | Logging level | INFO |

---

## Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=hermes --cov-report=html

# Run specific test file
pytest tests/unit/test_prompt_store.py
```

---

## Deployment

### Kubernetes

```bash
# Apply manifests
kubectl apply -f k8s/

# Check status
kubectl get pods -n hermes
```

### Helm

```bash
helm install hermes ./helm/hermes -n hermes
```

---

## Related Documentation

### In cognitive-architecture-docs/systems/hermes/

- [Quick Start Guide](../cognitive-architecture-docs/systems/hermes/quick-start.md) - Get up and running in 5 minutes
- [Architecture](../cognitive-architecture-docs/systems/hermes/architecture.md) - System design and components
- [API Reference](../cognitive-architecture-docs/systems/hermes/api-reference.md) - Complete REST and gRPC API docs
- [Integration Guide](../cognitive-architecture-docs/systems/hermes/integration-guide.md) - Connecting with other services
- [Deployment](../cognitive-architecture-docs/systems/hermes/deployment.md) - AWS ECS deployment guide

### Platform Docs

- [Platform Architecture](https://github.com/DeepCreative/CognitiveArchitecture/blob/main/architecture/hermes-platform.md)
- [Product Roadmap](https://github.com/DeepCreative/CognitiveArchitecture/blob/main/research/hermes-product-roadmap-2026.md)
- [Vision Document](https://github.com/DeepCreative/CognitiveArchitecture/blob/main/vision/hermes-vision.md)

---

## License

**Proprietary - Bravo Zero Inc.**

This software is proprietary and confidential. Unauthorized use, reproduction, or distribution is prohibited.

---

*Built with care by the Bravo Zero Platform Team*
