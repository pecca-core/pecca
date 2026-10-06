# Monitoring demos

Local stacks used by the `monitoring_*` notebooks (Docker required; every port is bound to 127.0.0.1).

| Folder | Stack | UI |
| --- | --- | --- |
| `jaeger/` | Jaeger all-in-one | http://localhost:16686 |
| `tempo/` + `grafana/` | Tempo + Grafana with the provisioned **Pecca: LLM replacement** dashboard | http://localhost:3000 |

```bash
docker compose -p pecca-jaeger -f examples/monitoring/jaeger/docker-compose.yml up -d
docker compose -p pecca-jaeger -f examples/monitoring/jaeger/docker-compose.yml down -v
```
Both stacks listen for OTLP/HTTP on port 4318, so run one at a time. Pecca's config is just:
```yaml
workspace:
  telemetry: {exporter: otlp, endpoint: http://localhost:4318/v1/traces}
```
