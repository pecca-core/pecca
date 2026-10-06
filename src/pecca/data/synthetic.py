"""Deterministic synthetic support-email dataset for the fictional "Northbridge Bank".

No real names or companies. 12 domains x 5 RFI topics = 60 classes.
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

# domain -> {rfi: [phrase variants]}. Slots: {amt} {date} {last4} {prod}
CATALOG: dict[str, dict[str, list[str]]] = {
    "cards": {
        "card_lost_stolen": ["my card was stolen yesterday", "I lost my debit card ending {last4}", "my wallet with the card {last4} is missing, please block it"],
        "card_replacement": ["I need a replacement card", "my card is damaged and the chip no longer works", "please send me a new card, the old one is worn out"],
        "card_activation": ["how do I activate my new card", "the new card I received will not activate", "I cannot activate the card ending {last4}"],
        "card_limit_change": ["please raise my card limit to {amt}", "I want to change my daily card spending limit", "can you lower my monthly card limit to {amt}"],
        "card_declined": ["my card keeps getting declined at shops", "the payment with card ending {last4} was declined", "why was my card refused at the till on {date}"],
    },
    "current_accounts": {
        "account_opening": ["I would like to open a {prod}", "what documents do I need to open a new current account", "how can I open an account online"],
        "account_closure": ["please close my {prod}", "I want to close my current account", "how do I shut down my account permanently"],
        "account_statement": ["I need a statement for the last three months", "please send my account statement for {date}", "where can I download my bank statements"],
        "account_details_update": ["I changed my address and need to update my details", "please update my phone number on file", "my surname changed, how do I update my account"],
        "dormant_account_reactivation": ["my account is dormant, how do I reactivate it", "I have not used my account for years and want to reactivate", "please unlock my inactive account"],
    },
    "personal_loans": {
        "loan_application_status": ["what is the status of my loan application", "I applied for a personal loan on {date}, any update", "has my loan of {amt} been approved yet"],
        "loan_early_settlement": ["I want to settle my loan early", "what is the payoff amount to close my loan", "can I repay my personal loan in full before the term ends"],
        "loan_interest_rate_query": ["what interest rate applies to my personal loan", "why is my loan rate higher than advertised", "can you explain the interest on my loan of {amt}"],
        "loan_payment_holiday": ["I need a payment holiday on my loan", "can I skip a loan instalment this month", "I lost my job and need to pause my loan payments"],
        "loan_top_up": ["can I top up my existing loan by {amt}", "I would like to borrow more on my current loan", "is a loan top up possible for me"],
    },
    "payments_transfers": {
        "transfer_not_received": ["the transfer of {amt} has not arrived", "my payment sent on {date} never reached the recipient", "the person says they have not received my transfer"],
        "wrong_beneficiary_transfer": ["I sent money to the wrong account number", "I made a transfer to the wrong beneficiary by mistake", "please recall my payment of {amt}, wrong recipient"],
        "international_transfer_fees": ["what are the fees for an international transfer", "how much do you charge to send money abroad", "what exchange rate applies to overseas payments"],
        "standing_order_setup": ["how do I set up a standing order", "please create a monthly standing order of {amt}", "I want a recurring payment every month on the 1st"],
        "direct_debit_dispute": ["I do not recognise this direct debit", "a direct debit of {amt} was taken in error", "please cancel the direct debit to {prod}"],
    },
    "fraud_security": {
        "unauthorised_transaction": ["there is a transaction on my account I did not make", "I see a charge of {amt} on {date} that is not mine", "someone used my card without permission"],
        "phishing_report": ["I received a suspicious email pretending to be the bank", "I got a fake text asking for my login details", "I want to report a phishing message"],
        "account_takeover": ["someone changed my password and locked me out", "my account was hacked and details were changed", "I think a stranger has taken over my online account"],
        "scam_victim_refund": ["I was scammed into sending {amt}, can I get a refund", "I fell for a scam and paid a fraudster", "please investigate a scam payment I made on {date}"],
        "lock_account_request": ["please freeze my account immediately", "I want to temporarily lock my account for safety", "block all access to my account right now"],
    },
    "mortgages": {
        "mortgage_application": ["I want to apply for a mortgage", "what do I need to apply for a home loan", "how long does a mortgage application take"],
        "mortgage_rate_fixing": ["my fixed rate ends soon, what are my options", "I want to fix my mortgage rate again", "what rates can I get when my deal expires on {date}"],
        "mortgage_overpayment": ["can I overpay my mortgage by {amt}", "is there a penalty for overpaying my home loan", "I want to make an extra payment on my mortgage"],
        "mortgage_statement_request": ["please send my annual mortgage statement", "I need a mortgage balance certificate", "can I get a statement of my home loan interest"],
        "mortgage_redemption": ["I am selling my house and need a redemption figure", "what is the amount to fully repay my mortgage", "please issue a redemption statement for {date}"],
    },
    "savings_investments": {
        "savings_interest_query": ["what interest does my {prod} pay", "why did my savings interest rate drop", "when is savings interest paid into my account"],
        "fixed_deposit_maturity": ["my fixed deposit matures on {date}, what happens next", "how do I renew my term deposit", "I want to withdraw my fixed deposit at maturity"],
        "savings_withdrawal_limits": ["how many withdrawals can I make from my savings", "is there a limit on withdrawing from my {prod}", "I need to withdraw {amt} from my saver account"],
        "investment_account_opening": ["I want to open an investment account", "how do I start investing with the bank", "please set up a share dealing account for me"],
        "isa_transfer": ["I want to transfer my tax-free savings to you", "how do I move my ISA from another provider", "please start a tax-free account transfer of {amt}"],
    },
    "fees_charges": {
        "fee_reversal_request": ["please reverse the fee charged on {date}", "I was charged {amt} unfairly, can you refund it", "can you waive this bank charge as a goodwill gesture"],
        "overdraft_fee_query": ["why was I charged an overdraft fee", "explain the overdraft charges on my account", "I went overdrawn by mistake and got a fee of {amt}"],
        "monthly_fee_explanation": ["what is this monthly account fee", "why am I paying a monthly maintenance fee", "how can I avoid the monthly fee on my {prod}"],
        "atm_fee_query": ["why was I charged for using an ATM", "what are the fees for withdrawing cash abroad", "an ATM took {amt} in fees on {date}"],
        "late_payment_fee_dispute": ["I was charged a late payment fee but paid on time", "please remove the late fee of {amt}", "I dispute the late payment charge on my account"],
    },
    "digital_banking": {
        "app_login_issue": ["I cannot log in to the mobile app", "the app says my login failed", "I am unable to sign in to online banking"],
        "password_reset": ["I forgot my password and need to reset it", "how do I change my online banking password", "the password reset link does not work"],
        "otp_not_received": ["I am not receiving the one time passcode", "the SMS verification code never arrives", "my OTP is not coming through to my phone"],
        "app_crash_bug": ["the app crashes every time I open it", "the mobile app freezes on the payments screen", "I found a bug in the banking app after the update"],
        "biometric_setup": ["how do I set up fingerprint login", "I want to enable face recognition in the app", "biometric login stopped working on my phone"],
    },
    "complaints_feedback": {
        "service_complaint": ["I want to complain about the service I received", "I am unhappy with how my request was handled", "your support team was unhelpful and rude"],
        "branch_complaint": ["I want to complain about my local branch", "I waited over an hour at the branch on {date}", "the branch staff gave me wrong information"],
        "positive_feedback": ["I want to thank the agent who helped me", "great service from your team, well done", "I would like to give some positive feedback"],
        "complaint_escalation": ["my complaint was not resolved, please escalate it", "I want to speak to a manager about my case", "escalate my complaint to the ombudsman"],
        "complaint_status": ["what is the status of my complaint", "I filed a complaint on {date} and have heard nothing", "can I get an update on my open complaint"],
    },
    "kyc_compliance": {
        "id_verification_pending": ["my identity verification is still pending", "why is my ID check taking so long", "I uploaded my passport but the verification is not complete"],
        "proof_of_address_upload": ["where do I upload my proof of address", "I need to send a utility bill to verify my address", "my proof of address was rejected, what is accepted"],
        "source_of_funds_query": ["why do you need proof of my source of funds", "what documents show the source of a deposit of {amt}", "you asked about where my money came from"],
        "tax_residency_update": ["I need to update my tax residency", "please change my tax status after moving countries", "how do I submit a new self certification form"],
        "sanctions_screening_delay": ["my payment is held for compliance screening", "why is my transfer under review for sanctions checks", "my account is restricted pending a compliance review"],
    },
    "insurance": {
        "insurance_claim_status": ["what is the status of my insurance claim", "I submitted a claim on {date} and need an update", "has my claim for {amt} been approved"],
        "policy_cancellation": ["I want to cancel my insurance policy", "please cancel my {prod} cover", "how do I end my policy before renewal"],
        "policy_renewal_quote": ["can I get a renewal quote for my policy", "my insurance renews on {date}, what is the new price", "why did my premium go up at renewal"],
        "add_beneficiary": ["I want to add a beneficiary to my policy", "how do I change the beneficiary on my life cover", "please name my spouse as beneficiary"],
        "premium_payment_issue": ["my insurance premium payment failed", "I was charged my premium twice this month", "I want to change how I pay my insurance premium"],
    },
}

PRODUCTS = ["Northbridge Everyday Account", "Harbor Saver", "Lighthouse Plus", "Keystone Card", "Beacon Home Cover", "Pinewood Loan"]
AMOUNTS = ["$120", "$250", "$480", "$1,200", "$3,500", "R900", "R2,750", "PHP 5,000", "PHP 18,000", "EUR 640"]
GREET = {
    "en": ["Hello,", "Hi team,", "Good morning,", "Dear Northbridge Bank,", "Hello support,"],
    "tl": ["Hello po,", "Magandang araw po,", "Kumusta po,"],
    "es": ["Hola,", "Buenos días,", "Estimado equipo,"],
    "af": ["Goeiedag,", "Hallo,", "Beste span,"],
}
OPEN = {
    "en": ["I am writing about the following:", "I need some help.", "Hope you can assist me.", "I have a question."],
    "tl": ["Gusto ko po sanang itanong:", "Kailangan ko po ng tulong, ", "Paki-tulungan po ako,"],
    "es": ["Necesito ayuda con lo siguiente:", "Les escribo porque", "Tengo una consulta:"],
    "af": ["Ek het hulp nodig met die volgende:", "Ek skryf oor die volgende:", "Ek het 'n vraag:"],
}
DETAIL = {
    "en": [
        "This has been going on since {date} and it is affecting my daily life.",
        "I have already tried calling the helpline but could not get through.",
        "My customer number is {cust} in case you need to look me up.",
        "I would appreciate a response as soon as possible.",
        "Please let me know what information you need from my side.",
        "I have attached screenshots of what I am seeing on my phone.",
        "I have been a customer of Northbridge Bank for several years.",
        "The reference on my side is {ref}, please quote it in your reply.",
        "I am travelling next week so a quick answer would really help.",
        "Please confirm by email once this has been sorted out.",
    ],
    "tl": ["Matagal ko na po itong problema mula {date}.", "Salamat po sa agarang tulong ninyo.", "Ang customer number ko po ay {cust}.", "Pakisagot po agad kung maaari."],
    "es": ["Esto ocurre desde el {date} y necesito una solución.", "Mi número de cliente es {cust}.", "Les agradezco una respuesta lo antes posible.", "Por favor confirmen por correo cuando esté resuelto."],
    "af": ["Dit gebeur al sedert {date} en ek benodig hulp.", "My kliëntnommer is {cust}.", "Ek sal 'n vinnige antwoord waardeer.", "Bevestig asseblief per e-pos sodra dit opgelos is."],
}
CLOSE = {
    "en": ["Thank you,", "Kind regards,", "Thanks in advance,", "Best wishes,"],
    "tl": ["Maraming salamat po,", "Salamat po,"],
    "es": ["Muchas gracias,", "Saludos cordiales,"],
    "af": ["Dankie,", "Vriendelike groete,"],
}
NAMES = ["A. Rivers", "J. Moreno", "T. Dlamini", "M. Santos", "L. Visser", "K. Okafor", "S. Hartley", "P. Cruz"]
BANNED_TOKENS = ["hsbc", "barclays", "jpmorgan", "chase", "citibank", "standard chartered", "dbs", "capitec", "absa", "bdo", "bpi", "emirates nbd", "sbi", "hdfc", "icici", "santander", "wells fargo", "bank of america", "nedbank", "tymebank", "gotyme"]

LANG_WEIGHTS = [("en", 0.70), ("tl", 0.15), ("es", 0.10), ("af", 0.05)]
RFIS: list[tuple[str, str]] = [(d, r) for d, rs in CATALOG.items() for r in rs]
DOMAINS = list(CATALOG)
RFI_DOMAIN = {r: d for d, r in RFIS}
END_DATE = datetime(2026, 9, 30, 23, 59, 59)


def _fill(text: str, rng: random.Random) -> str:
    return text.format(
        amt=rng.choice(AMOUNTS),
        date=(END_DATE - timedelta(days=rng.randint(1, 120))).strftime("%d %b"),
        last4=f"****{rng.randint(1000, 9999)}",
        prod=rng.choice(PRODUCTS),
        cust=f"NB{rng.randint(100000, 999999)}",
        ref=f"REF-{rng.randint(10000, 99999)}",
    )


def _body(rfi: str, lang: str, rng: random.Random) -> tuple[str, str]:
    domain = RFI_DOMAIN[rfi]
    phrase = _fill(rng.choice(CATALOG[domain][rfi]), rng)
    parts = [rng.choice(GREET[lang]), f"{rng.choice(OPEN[lang])} {phrase}."]
    pool = DETAIL[lang][:]
    rng.shuffle(pool)
    target = rng.randint(40, 110)
    for sent in pool:
        if sum(len(p.split()) for p in parts) >= target:
            break
        parts.append(_fill(sent, rng))
    if sum(len(p.split()) for p in parts) < 40:  # tiny pools: pad from the English pool
        for sent in DETAIL["en"]:
            parts.append(_fill(sent, rng))
            if sum(len(p.split()) for p in parts) >= 40:
                break
    parts += [rng.choice(CLOSE[lang]), rng.choice(NAMES)]
    words = " ".join(parts).split()
    body = "\n".join(parts) if len(words) <= 120 else " ".join(words[:120])
    subject = phrase[:60].strip().capitalize()
    if rng.random() < 0.2:
        subject = "Re: " + subject
    return subject, body


def generate(n: int = 6000, seed: int = 42) -> pd.DataFrame:
    rng = random.Random(seed)
    langs = [lg for lg, _ in LANG_WEIGHTS]
    weights = [w for _, w in LANG_WEIGHTS]
    rows = []
    start = END_DATE - timedelta(days=90)
    for i in range(n):
        domain, rfi = RFIS[i % len(RFIS)] if i < len(RFIS) * 2 else rng.choice(RFIS)
        lang = rng.choices(langs, weights)[0]
        subject, body = _body(rfi, lang, rng)
        ts = start + timedelta(seconds=rng.randint(0, 90 * 86400 - 1))
        siblings = [r for r in CATALOG[domain] if r != rfi]
        # LLM noise: 15% rfi, 10% domain.
        llm_rfi = rfi
        if rng.random() < 0.15:
            llm_rfi = rng.choice(siblings) if rng.random() < 0.7 else rng.choice(RFIS)[1]
        llm_domain = domain
        if rng.random() < 0.10:
            llm_domain = rng.choice([d for d in DOMAINS if d != domain])
        human_rfi = None
        if rng.random() < 0.55:
            human_rfi = rfi if rng.random() < 0.97 else rng.choice(siblings)
        rows.append(
            {
                "request_id": f"REQ-{i:06d}",
                "timestamp": ts.isoformat(),
                "email_subject": subject,
                "email_body": body,
                "language": lang,
                "domain": domain,
                "rfi": rfi,
                "llm_domain": llm_domain,
                "llm_rfi": llm_rfi,
                "human_rfi": human_rfi,
                "llm_model": "demo-llm",
                "channel": "email",
            }
        )
    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    return df


def assert_clean(df: pd.DataFrame) -> None:
    text = (df["email_subject"] + " " + df["email_body"]).str.lower().str.cat(sep=" ")
    bad = [t for t in BANNED_TOKENS if t in text]
    if bad:
        raise AssertionError(f"banned tokens present in synthetic data: {bad}")


REPLY_OPEN = ["Thank you for contacting Northbridge Bank.", "Thanks for getting in touch.", "We have received your message."]


def to_long(df: pd.DataFrame, n_reply: int = 800) -> pd.DataFrame:
    """Long format used by the CLI quickstart: one row per LLM call, ``call_name`` says which call.

    ``route_domain`` / ``route_rfi`` are closed sets (replaceable); ``generate_reply`` returns a unique
    free-text answer per email (not replaceable), so ``pecca profile`` shows both outcomes.
    """
    base = ["request_id", "timestamp", "email_subject", "email_body", "language", "llm_model"]
    rfi = df[base].assign(call_name="route_rfi", llm_output=df["llm_rfi"], human_label=df["human_rfi"])
    human_domain = df["human_rfi"].map(RFI_DOMAIN)
    dom = df[base].assign(call_name="route_domain", llm_output=df["llm_domain"], human_label=human_domain)
    rng = random.Random(42)
    sub = df.head(n_reply)
    replies = [
        f"{rng.choice(REPLY_OPEN)} Regarding \"{str(r.email_subject)[:50]}\" (ref {r.request_id!s}): "
        f"we will respond within {rng.randint(1, 5)} business days. Your case number is {rng.randint(100000, 999999)}."
        for r in sub.itertuples()
    ]
    rep = sub[base].assign(call_name="generate_reply", llm_output=replies, human_label=None)
    return pd.concat([rfi, dom, rep], ignore_index=True)


CARD = """---
license: cc-by-4.0
task_categories:
- text-classification
language: [en, tl, es, af]
size_categories:
- n<10K
tags: [synthetic, customer-support, banking, pecca]
---
# pecca-core/demo-support-emails

## Summary
6,000 **synthetic** support emails for the fictional "Northbridge Bank". No real people, companies or PII.
Used by the Pecca quickstart, tests and demo model.

## Schema
| column | description |
| --- | --- |
| request_id | unique id |
| timestamp | ISO8601, spans 90 days |
| email_subject, email_body | text (40-120 words body) |
| language | en 70%, tl 15% (Taglish-style), es 10%, af 5% |
| domain | 12 classes (ground truth) |
| rfi | 60 classes, each mapped to one domain (ground truth) |
| llm_domain, llm_rfi | simulated LLM answers (10% / 15% noise) |
| human_rfi | agent tag, present for ~55% rows, equals `rfi` 97% of the time |
| llm_model, channel | constants (`demo-llm`, `email`) |

## Generation method
`scripts/generate_synthetic_dataset.py` (seed 42): per-RFI templates x slot fillers (amounts, dates, card last-4,
fictional product names) with paraphrase variants. Non-English rows are code-mixed: the frame is in the target
language while the topic phrase stays in English.

## Intended use
Demos, tests and documentation of Pecca. Not for training production models.

## Limitations
Synthetic distribution: far cleaner and more separable than real email. Metrics here do not predict real performance.

## Citation
Pecca, https://github.com/pecca-core/pecca (Apache-2.0 code, CC-BY-4.0 data).
"""


def write_dataset(out_dir: str | Path, n: int = 6000, seed: int = 42) -> pd.DataFrame:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    df = generate(n, seed)
    assert_clean(df)
    df.to_parquet(out / "train.parquet", index=False)
    df.to_csv(out / "train.csv", index=False)
    (out / "README.md").write_text(CARD)
    (out / "LICENSE").write_text("Creative Commons Attribution 4.0 International (CC-BY-4.0)\nhttps://creativecommons.org/licenses/by/4.0/legalcode\n")
    return df
