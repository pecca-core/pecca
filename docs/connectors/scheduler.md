# Scheduler

`register_job(name, every, command)` and `list_jobs()`. Durations: `7d`, `2w`, `1m`, `1y`.
`cron` prints a crontab line (`0 6 */7 * * pecca scheduler run --once`) and keeps a job list; `airflow` writes a DAG file per job (and exposes a lazy `PeccaOperator`); `databricks_workflows` writes job JSON and creates the job with `deploy: true`.

`pecca scheduler run [--once]` is the tick: it retrains calls past `train_every`, regenerates the audit pack for due revalidations and runs drift reviews, notifying as configured.
