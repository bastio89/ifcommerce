import pytest

from app.decision.base import DecisionHints
from app.decision.heuristic_engine import HeuristicDecisionEngine, detect_legal_threat
from app.schemas import TicketCategory

engine = HeuristicDecisionEngine()


@pytest.mark.parametrize(
    ("text", "category"),
    [
        (
            "Hallo, wo ist meine Bestellung? Sie ist seit 10 Tagen noch nicht angekommen.",
            TicketCategory.WHERE_IS_MY_ORDER,
        ),
        ("Hi, my package hasn't arrived yet. Can you check the tracking?", TicketCategory.WHERE_IS_MY_ORDER),
        ("Ich möchte die Schuhe zurückschicken und mein Geld zurück.", TicketCategory.RETURN_OR_REFUND),
        ("I want a refund for the jacket, please send me a return label.", TicketCategory.RETURN_OR_REFUND),
        ("Der Mixer ist kaputt angekommen und funktioniert nicht.", TicketCategory.PRODUCT_ISSUE),
        ("You sent me the wrong size and the zipper is broken.", TicketCategory.PRODUCT_ISSUE),
        ("Mir wurde der Betrag doppelt abgebucht, bitte Rechnung prüfen.", TicketCategory.PAYMENT_OR_INVOICE),
        ("Can I get an invoice with VAT for my payment?", TicketCategory.PAYMENT_OR_INVOICE),
        ("Ist die Jacke in Größe M wieder auf Lager?", TicketCategory.GENERAL_INQUIRY),
        ("Do you ship to Switzerland?", TicketCategory.GENERAL_INQUIRY),
    ],
)
def test_categories(text: str, category: TicketCategory) -> None:
    assert engine.decide_sync(text, DecisionHints()).category is category


def test_legal_threat_is_maximum_urgency() -> None:
    decision = engine.decide_sync(
        "Seit 3 Wochen keine Ware! Ich schalte jetzt meinen Anwalt und die Verbraucherzentrale ein!!!",
        DecisionHints(),
    )
    assert decision.urgency == 5


def test_neutral_question_is_low_urgency() -> None:
    decision = engine.decide_sync("Habt ihr die Tasse auch in Blau?", DecisionHints())
    assert decision.urgency == 1
    assert decision.category is TicketCategory.GENERAL_INQUIRY


def test_cancellation_detection_and_negation() -> None:
    cancel = engine.decide_sync("Bitte storniert sofort meine Bestellung!", DecisionHints())
    assert cancel.is_cancellation_request
    assert cancel.urgency >= 4
    assert cancel.category is TicketCategory.RETURN_OR_REFUND

    no_cancel = engine.decide_sync("Bitte nicht stornieren, ich warte gern noch.", DecisionHints())
    assert not no_cancel.is_cancellation_request


def test_order_number_hint_is_used() -> None:
    assert engine.decide_sync(
        "Frage zur Bestellung", DecisionHints(order_reference_detected=True)
    ).contains_order_number


def test_confidence_is_bounded() -> None:
    for text in ["", "?", "Wo ist mein Paket? Tracking? DHL? Lieferstatus? Noch nicht angekommen!"]:
        decision = engine.decide_sync(text, DecisionHints())
        assert 0.0 <= decision.confidence <= 0.95


@pytest.mark.parametrize(
    "text",
    [
        "Wenn das Paket nicht bis Freitag da ist, schalte ich meinen Anwalt ein.",
        "Sonst gehe ich zur Verbraucherzentrale.",
        "Ich werde rechtliche Schritte einleiten.",
        "Das ist doch Betrug!",
        "Ich werde euch verklagen.",
        "If this isn't fixed by tomorrow I'll file a chargeback and report you for fraud.",
        "I will sue you.",
        "My lawyer will contact you.",
        "This is a scam!",
    ],
)
def test_legal_threats_are_detected(text: str) -> None:
    assert detect_legal_threat(text)


@pytest.mark.parametrize(
    "text",
    [
        # Aus dem Review: harmlose Tickets, die früher fälschlich als Stufe 5 galten.
        "Hi, are the Nike Court Vision sneakers available in size 42?",
        "Do you have tennis court shoes in black?",
        "Hello, I'm Sue and my order hasn't arrived.",
        "I got an SMS saying my parcel is held, is this a scam or from you?",
        "PayPal flagged my payment as fraud, can you resend the invoice?",
        "Is the Polizei-Kostüm for Fasching still available in size M?",
        "Gibt es das Buch 'Der Anwalt' von John Grisham noch?",
        "Mein Mann ist Anwalt und hat das Paket angenommen.",
    ],
)
def test_ordinary_words_are_not_legal_threats(text: str) -> None:
    assert not detect_legal_threat(text)
    assert engine.decide_sync(text, DecisionHints()).urgency < 5
