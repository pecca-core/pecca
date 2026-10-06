# Writing a connector

Example: Raj needs approvals in ServiceNow.

```python
# my_pkg/servicenow.py
import httpx
import pecca.connectors as connectors
from pecca.connectors.base import Ticketer


@connectors.register(interface="ticketer", type="servicenow")
class ServiceNowTicketer(Ticketer):
    def __init__(self, url: str, user: str, password: str, **_):
        self.url, self.auth = url, (user, password)

    def create(self, title, body, meta):
        r = httpx.post(
            f"{self.url}/api/now/table/change_request",
            auth=self.auth,
            json={"short_description": title, "description": body},
        )
        r.raise_for_status()
        return r.json()["result"]["number"]

    def get_status(self, ticket_id): ...
    def get_approvers(self, ticket_id): ...  # [{"principal": "a@b.com", "group": "model-risk"}]
    def comment(self, ticket_id, body): ...
    def close(self, ticket_id): ...
```
Import the module before Pecca loads the config (or from your app's entry point), then:
```yaml
integrations:
  ticketer: {type: servicenow, url: https://x.service-now.com, user: ${SN_USER}, password: ${SN_PASSWORD}}
```
Tips: raise `ConnectorError(message, hint)` for failures; test with `respx` (no network in CI); import optional dependencies lazily. Open a PR to add it to the reference implementations (use the *connector request* issue template).
