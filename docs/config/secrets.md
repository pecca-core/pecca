# Secrets

Config values may reference `${VAR}`. Variables are resolved at use time through the workspace **Secrets** connector; `pecca apply` fails if one cannot be resolved. Resolved values are **never** written to `.pecca/config.resolved.yaml`.

```yaml
workspace:
  secrets: {provider: env}                       # env | vault | aws-secrets-manager
  # secrets: {provider: vault, url: https://vault:8200, path: pecca, mount: secret}
  # secrets: {provider: aws-secrets-manager, region: eu-west-1, prefix: "pecca/"}
```

| Provider | Install | Reads |
| --- | --- | --- |
| `env` | built in | environment variables (and a `.env` you export yourself) |
| `vault` | `pip install 'pecca[vault]'` | key `NAME` in the KV v2 secret at `path` |
| `aws-secrets-manager` | `pip install 'pecca[aws]'` | secret id `<prefix>NAME`: plain string, or JSON with key `NAME` |

Never commit tokens. `.env` is git-ignored by `pecca init`; `pecca doctor` reports unresolved variables.
