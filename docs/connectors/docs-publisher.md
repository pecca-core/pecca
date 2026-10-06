# DocsPublisher

`publish(title, markdown, meta) → location`. `markdown` writes files to a directory; `confluence` creates or updates a page by title under `parent_page_id` (REST, storage format).
```yaml
integrations:
  docs: {type: confluence, url: https://x.atlassian.net/wiki, space: AI, parent_page_id: "123", email: ${JIRA_EMAIL}, token: ${CONFLUENCE_TOKEN}}
```
Use with `pecca audit PATH --out confluence`.
