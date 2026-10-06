"""GREENFIELD: no historical logs yet. Record the LLM's answers, then train, then shadow.

Everything runs offline against the mock LLM and ``.pecca/`` in the current directory.
"""

from mock_llm import llm_route_rfi

import pecca
from pecca.data.synthetic import generate
from pecca.runtime.logging_sink import flush_all


@pecca.replace(
    "route_rfi",
    mode="record",
    input_adapter=lambda subject, body: {"subject": subject, "body": body},
)
def route_rfi(subject: str, body: str) -> str:
    return llm_route_rfi(subject, body)


if __name__ == "__main__":
    emails = generate(1500, seed=42)
    for r in emails.itertuples():  # 1. normal production traffic; Pecca just records
        route_rfi(r.email_subject, r.email_body)
    flush_all()
    res = pecca.train("route_rfi", target_precision=0.9)  # 2. learn from what the LLM already said
    print(
        f"winner {res.winner}: {res.metric_name} {res.metric:.2f}, threshold {res.threshold:.2f}, "
        f"expected fallback {res.expected_fallback_rate:.0%}"
    )
    print(pecca.promote("route_rfi", "shadow"))  # 3. run next to the LLM
