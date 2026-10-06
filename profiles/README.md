# Governance profiles

Every file here is a **template only**. It is a convenience preset and is **not legal or regulatory advice**.
Pecca enforces only what is written in your `pecca.yaml`. Review profiles with your compliance team and edit freely.
Control strings are illustrative placeholders (`<FRAMEWORK>-<clause>`); no real clause numbers are claimed.

Use one with `pecca init --profile <name>` or `governance: {extends: <name>}`.

## Contributing a profile
Add `profiles/<name>.yaml` containing a complete `governance:` block, keep the two-line disclaimer header,
validate with `pecca apply`, and open a PR (sign off commits with `git commit -s`).
