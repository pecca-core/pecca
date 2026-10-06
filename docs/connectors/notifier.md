# Notifier

`send(event, payload, rendered)`. Events: `trained`, `shadow`, `ready_for_approval`, `live`, `drift`, `revalidate`. Filter with `events: [...]`.

```yaml
integrations:
  notifier: {type: slack, webhook: ${SLACK_WEBHOOK}, channel: "#ai-platform", events: [trained, live, drift]}
```
`slack` (incoming webhook), `teams` (incoming webhook, Adaptive Card), `webhook` (`url`, JSON `{event, payload, text}`), `mcp` (`tool_map: {send: <tool>}`). Notification failures never affect the pipeline.
