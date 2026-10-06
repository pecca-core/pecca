# Profiles

!!! warning "Templates only"
    Profiles are convenience presets and are **not legal or regulatory advice**. Review them with your compliance team and edit freely. Pecca enforces only what is written in your config.

Use one with `pecca init --profile <name>` or `governance: {extends: <name>}`; anything you write overrides the profile.

| Profile | Gates | Approvals | Evidence | Retention |
| --- | --- | --- | --- | --- |
| `none` | `cv_metric >= 0.80`; `agreement >= 0.85`, `shadow_days >= 7` | none | none | 1y |
| `default` | `0.85`, `rows >= 2000`; `agreement >= 0.90`, `shadow_days >= 14` | `ml-leads` (manual) | 4 core sections | 3y evidence |
| `sr11-7`, `cbuae`, `bsp`, `rbi`, `sarb` | as `default` | `model-risk` **and** `business-owner` (all) | all 7 sections | 7y, signed |
| `eu-ai-act` | as `default` | as above | 7 sections + `human_oversight_log` | 7y, signed |

Control strings in the regulatory profiles are illustrative placeholders such as `"SR11-7-<clause>"`. No real clause numbers are claimed. See `profiles/README.md` to contribute one.
