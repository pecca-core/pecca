# Identity

`current_principal() → {user, groups}`. The default returns `{user: $USER, groups: [local]}`. `oidc` reads the claims of the JWT in `PECCA_ID_TOKEN` (`email`, `groups`). The signature is **not** verified, so this is a convenience for recording who approved, never authentication.
