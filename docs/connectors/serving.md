# ServingTarget

`deploy(path_key, version)` and `endpoint(path_key)`.
`onnx_local` is the default in-process serving (the `@replace` decorator). `docker_export` writes a folder with a `Dockerfile`, a FastAPI `/predict` app, `requirements.txt` and the model for one version. `databricks_serving` creates a Model Serving endpoint for a Unity Catalog model (`pecca[databricks]`).
