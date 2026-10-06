# `pecca`

Pecca: replace repetitive LLM calls with small, auditable models.

**Usage**:

```console
$ pecca [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `init`: Create pecca.yaml, templates/, .pecca/ and...
* `apply`: Validate, resolve and store the config;...
* `connect`: Test datasource connectivity and print row...
* `doctor`: Check python, registry, secrets, OTel,...
* `version`: Print the Pecca version.
* `profile`: Table of CallProfiles.
* `train`: Run the tournament and print the leaderboard.
* `status`: Workspace, project or call view.
* `eval`: Agreement, fallback rate and drift over a...
* `promote`: Governance-gated mode change.
* `approve`: Record a manual approval.
* `diff`: Side-by-side comparison of two versions.
* `audit`: Generate the audit pack.
* `logs`: Tail decision logs.
* `datasets`: Demo datasets
* `plugins`: Registered candidates and connectors
* `scheduler`: Scheduler
* `mcp`: MCP server

## `pecca init`

Create pecca.yaml, templates/, .pecca/ and .env.example.

**Usage**:

```console
$ pecca init [OPTIONS]
```

**Options**:

* `--profile <str>`: Governance profile (none, default, sr11-7, ...)  [default: default]
* `--project <str>`: Project name  [default: default]
* `--force`: Overwrite an existing pecca.yaml
* `--help`: Show this message and exit.

## `pecca apply`

Validate, resolve and store the config; print the diff vs the stored one.

**Usage**:

```console
$ pecca apply [OPTIONS] [path]
```

**Arguments**:

* `path`: [default: pecca.yaml]

**Options**:

* `--help`: Show this message and exit.

## `pecca connect`

Test datasource connectivity and print row counts per call.

**Usage**:

```console
$ pecca connect [OPTIONS]
```

**Options**:

* `--project <str>`: [default: default]
* `--help`: Show this message and exit.

## `pecca doctor`

Check python, registry, secrets, OTel, ONNX runtime, long shadows and due revalidations.

**Usage**:

```console
$ pecca doctor [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `pecca version`

Print the Pecca version.

**Usage**:

```console
$ pecca version [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `pecca profile`

Table of CallProfiles.

**Usage**:

```console
$ pecca profile [OPTIONS] [path]
```

**Arguments**:

* `path`: workspace/project/call (default: every call in the project datasource)

**Options**:

* `--project <str>`: [default: default]
* `--min-rows <int>`: [default: 500]
* `--help`: Show this message and exit.

## `pecca train`

Run the tournament and print the leaderboard.

**Usage**:

```console
$ pecca train [OPTIONS] {path}
```

**Arguments**:

* `path`: [required]

**Options**:

* `--metric <str>`
* `--latency-budget-ms <float>`
* `--candidates <str>`: Comma-separated override, e.g. tfidf_linear,e5_logreg (skips slow xlmr_finetune on CPU)
* `--help`: Show this message and exit.

## `pecca status`

Workspace, project or call view.

**Usage**:

```console
$ pecca status [OPTIONS] [path]
```

**Arguments**:

* `path`

**Options**:

* `--help`: Show this message and exit.

## `pecca eval`

Agreement, fallback rate and drift over a window.

**Usage**:

```console
$ pecca eval [OPTIONS] {path}
```

**Arguments**:

* `path`: [required]

**Options**:

* `--since <str>`: [default: 14d]
* `--help`: Show this message and exit.

## `pecca promote`

Governance-gated mode change. Prints the Decision.

**Usage**:

```console
$ pecca promote [OPTIONS] {path}
```

**Arguments**:

* `path`: [required]

**Options**:

* `--mode <str>`: off | record | shadow | live  [required]
* `--force`: Override gates (requires PECCA_ALLOW_FORCE=1)
* `--help`: Show this message and exit.

## `pecca approve`

Record a manual approval.

**Usage**:

```console
$ pecca approve [OPTIONS] {path}
```

**Arguments**:

* `path`: [required]

**Options**:

* `--version <str>`: [required]
* `--approver <str>`: Approver email  [required]
* `--ticket <str>`
* `--note <str>`
* `--group <str>`: Group(s) the approver represents (repeatable)
* `--help`: Show this message and exit.

## `pecca diff`

Side-by-side comparison of two versions.

**Usage**:

```console
$ pecca diff [OPTIONS] {path} {a} {b}
```

**Arguments**:

* `path`: [required]
* `a`: [required]
* `b`: [required]

**Options**:

* `--help`: Show this message and exit.

## `pecca audit`

Generate the audit pack.

**Usage**:

```console
$ pecca audit [OPTIONS] {path}
```

**Arguments**:

* `path`: [required]

**Options**:

* `--version <str>`
* `--out <str>`: markdown | json | confluence | pdf (pdf is untested)  [default: markdown]
* `--path <str>`
* `--help`: Show this message and exit.

## `pecca logs`

Tail decision logs.

**Usage**:

```console
$ pecca logs [OPTIONS] {path}
```

**Arguments**:

* `path`: [required]

**Options**:

* `--since <str>`: [default: 1d]
* `--disagreements`
* `--fallbacks`
* `--limit <int>`: [default: 20]
* `--help`: Show this message and exit.

## `pecca datasets`

Demo datasets

**Usage**:

```console
$ pecca datasets [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `demo`: Write the synthetic Northbridge Bank demo...

### `pecca datasets demo`

Write the synthetic Northbridge Bank demo dataset.

**Usage**:

```console
$ pecca datasets demo [OPTIONS]
```

**Options**:

* `--out <str>`: Output directory  [default: ./data/demo]
* `--help`: Show this message and exit.

## `pecca plugins`

Registered candidates and connectors

**Usage**:

```console
$ pecca plugins [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `list`: List registered candidates and connectors...

### `pecca plugins list`

List registered candidates and connectors with their source module.

**Usage**:

```console
$ pecca plugins list [OPTIONS]
```

**Options**:

* `--help`: Show this message and exit.

## `pecca scheduler`

Scheduler

**Usage**:

```console
$ pecca scheduler [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `run`: Evaluate due train_every / revalidate /...

### `pecca scheduler run`

Evaluate due train_every / revalidate / drift_review items, execute them and notify.

**Usage**:

```console
$ pecca scheduler run [OPTIONS]
```

**Options**:

* `--once`: Run a single tick and exit
* `--interval <int>`: Seconds between ticks  [default: 60]
* `--help`: Show this message and exit.

## `pecca mcp`

MCP server

**Usage**:

```console
$ pecca mcp [OPTIONS] COMMAND [ARGS]...
```

**Options**:

* `--help`: Show this message and exit.

**Commands**:

* `serve`: Run the Pecca MCP server.

### `pecca mcp serve`

Run the Pecca MCP server.

**Usage**:

```console
$ pecca mcp serve [OPTIONS]
```

**Options**:

* `--transport <str>`: [default: stdio]
* `--port <int>`: [default: 8765]
* `--workspace <str>`
* `--allow-promote`: Expose pecca_promote
* `--help`: Show this message and exit.
