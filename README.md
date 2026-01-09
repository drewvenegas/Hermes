# Hermes

> **Bravo Zero Prompt Engineering Platform**

Hermes is the centralized prompt engineering platform for the Bravo Zero ecosystem. It provides version-controlled storage, automated benchmarking, and continuous improvement capabilities for all prompt types.

---

## Features

- **Prompt Management**: CRUD operations for all prompt types (agent, template, tool, MCP)
- **Version Control**: Semantic versioning with full history and rollback
- **Benchmarking**: Automated quality assessment via ATE integration
- **Self-Critique**: AI-powered improvement suggestions via ASRBS
- **Access Control**: Multi-level RBAC integrated with PERSONA
- **Search**: Full-text search with Elasticsearch
- **Real-time Sync**: WebSocket-based live updates

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

### Prompts

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/prompts` | List all prompts |
| POST | `/api/v1/prompts` | Create a new prompt |
| GET | `/api/v1/prompts/{id}` | Get prompt by ID |
| PUT | `/api/v1/prompts/{id}` | Update prompt |
| DELETE | `/api/v1/prompts/{id}` | Delete prompt |

### Versions

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/prompts/{id}/versions` | List versions |
| GET | `/api/v1/prompts/{id}/versions/{version}` | Get specific version |
| POST | `/api/v1/prompts/{id}/rollback` | Rollback to version |

### Benchmarks

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/api/v1/prompts/{id}/benchmark` | Run benchmark |
| GET | `/api/v1/prompts/{id}/benchmarks` | List benchmark results |

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

- [Platform Architecture](https://github.com/DeepCreative/CognitiveArchitecture/blob/main/architecture/hermes-platform.md)
- [Integration Guide](https://github.com/DeepCreative/CognitiveArchitecture/blob/main/architecture/hermes-integration.md)
- [Product Roadmap](https://github.com/DeepCreative/CognitiveArchitecture/blob/main/research/hermes-product-roadmap-2026.md)

---

## License

**Proprietary - Bravo Zero Inc.**

This software is proprietary and confidential. Unauthorized use, reproduction, or distribution is prohibited.

---

*Built with care by the Bravo Zero Platform Team*
