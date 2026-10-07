from app.decision.pipeline import DecisionPipeline
from app.privacy.email import preprocess_email


def test_strips_quoted_reply_and_html_markup() -> None:
    message = """<div>Danke, das Paket ist angekommen.</div>
    <div>Am 5. Oktober schrieb Max Mustermann:</div>
    <blockquote>Wenn es nicht kommt, schalte ich meinen Anwalt ein.</blockquote>"""

    result = preprocess_email(message)

    assert result == "Danke, das Paket ist angekommen."
    assert "Anwalt" not in result


def test_strips_plain_quoted_lines_but_keeps_unmarked_text() -> None:
    assert preprocess_email("Alles angekommen.\n> Ich werde euch verklagen.") == "Alles angekommen."
    assert preprocess_email("Bitte prüfen Sie meine Retoure.") == "Bitte prüfen Sie meine Retoure."


async def test_quoted_legal_threat_does_not_escalate_latest_reply() -> None:
    result = await DecisionPipeline(primary=None).analyze(
        "Danke, das Paket ist angekommen.\n\nAm 5. Oktober schrieb Max Mustermann:\n"
        "> Wenn das Paket nicht kommt, schalte ich meinen Anwalt ein."
    )

    assert result.decision.urgency < 5
    assert "Anwalt" not in result.anonymized_text
