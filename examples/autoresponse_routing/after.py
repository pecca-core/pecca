"""AFTER: one decorator. Shadow mode first; the LLM answer is still what the pipeline uses.

Run ``python greenfield.py`` (or ``pecca train``) first so a model exists.
"""

from mock_llm import CALLS, llm_route_rfi

import pecca
from pecca.data.synthetic import generate


@pecca.replace(
    "route_rfi",
    mode="shadow",  # change to "live" once governance gates pass (pecca promote ... --mode live)
    input_adapter=lambda subject, body: {"subject": subject, "body": body},
)
def route_rfi(subject: str, body: str) -> str:
    return llm_route_rfi(subject, body)  # unchanged


def handle_email(subject: str, body: str) -> str:
    return f"auto-reply template for {route_rfi(subject, body)}"


if __name__ == "__main__":
    emails = generate(200, seed=7)
    for r in emails.itertuples():
        handle_email(r.email_subject, r.email_body)
    from pecca.runtime.logging_sink import flush_all

    flush_all()
    rep = pecca.evaluate("route_rfi", "1d")
    print(f"{len(emails)} emails, {CALLS['llm_calls']} LLM calls (shadow still calls the LLM)")
    print(f"agreement with the LLM: {rep.agreement_rate:.2%} over {rep.n_rows} calls")
