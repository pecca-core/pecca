"""BEFORE: every incoming email makes an LLM call to decide which RFI topic it is."""

from mock_llm import CALLS, llm_route_rfi

from pecca.data.synthetic import generate


def route_rfi(subject: str, body: str) -> str:
    return llm_route_rfi(subject, body)  # in production: openai / bedrock / claude / local


def handle_email(subject: str, body: str) -> str:
    topic = route_rfi(subject, body)
    return f"auto-reply template for {topic}"


if __name__ == "__main__":
    emails = generate(200, seed=7)
    for r in emails.itertuples():
        handle_email(r.email_subject, r.email_body)
    print(f"{len(emails)} emails -> {CALLS['llm_calls']} LLM calls")
