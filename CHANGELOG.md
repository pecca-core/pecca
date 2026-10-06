# Changelog
All notable changes follow [Keep a Changelog](https://keepachangelog.com/).

## [0.1.0] - 2026-10-06
### Added
- Profiler, tournament training (TF-IDF, multilingual-e5 + linear head, optional fine-tuned XLM-R, tabular models, custom candidates), calibration and precision-targeted thresholds.
- `@pecca.replace` runtime with `off` / `record` / `shadow` / `live` modes, OpenTelemetry spans and exception isolation.
- Governance: gates, approvals, evidence, retention, schedule, controls mapping; eight editable profiles (templates only, not legal advice).
- Audit packs (Markdown, JSON, Confluence; PDF is untested).
- Connectors: data sources (CSV, Parquet, Postgres, Databricks, Snowflake, BigQuery, OTel traces, LiteLLM, Databricks AI Gateway, MCP), registries (local, MLflow / Unity Catalog, W&B), notifiers, ticketers, schedulers, serving targets, secrets, docs publishers, identity.
- CLI (`pecca init|apply|connect|profile|train|status|eval|promote|approve|diff|audit|logs|doctor|plugins|scheduler|mcp|datasets`), MCP server, agent-framework shims (LangGraph, Strands, Google ADK, OpenAI Agents SDK, Claude Agent SDK).
- Documentation site, synthetic demo dataset and demo model, example project.

### Known limitations
- TF-IDF models are served from the pickled pipeline (ONNX output did not match scikit-learn); the e5 ONNX export covers the linear head only.
- Extraction calls are profiled but not replaceable.
- Remote MCP adapters do not support auth headers.
