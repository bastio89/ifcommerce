"""DSGVO-Schutzschicht: anonymisiert personenbezogene Daten, BEVOR Text die KI erreicht.

Die Pipeline arbeitet rein lokal (Regex + Validierungslogik, keine externen
Calls) und läuft in Mikrosekunden. Reihenfolge:

1. Bestell-/Referenznummern schützen (werden für die Entscheidung gebraucht
   und dürfen nicht als Telefonnummer o. ä. fehlklassifiziert werden).
2. Strukturierte PII: E-Mail, IBAN (Prüfsumme), Kreditkarte (Luhn), IP, Telefon.
3. Adressen (Straße + Hausnummer, PLZ + Ort).
4. Klarnamen: Anrede ("Herr Müller"), Selbstvorstellung ("Mein Name ist …"),
   Grußformel-Signatur ("Viele Grüße\\nMax Mustermann") und Vornamen-Lexikon.
5. Geschützte Referenzen wiederherstellen.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field

from app.privacy.names import FIRST_NAMES, NON_NAME_TOKENS

PLACEHOLDERS = {
    "EMAIL": "[ANONYMOUS_EMAIL]",
    "PHONE": "[ANONYMOUS_PHONE]",
    "NAME": "[ANONYMOUS_NAME]",
    "IBAN": "[ANONYMOUS_IBAN]",
    "CARD": "[ANONYMOUS_CARD]",
    "IP": "[ANONYMOUS_IP]",
    "ADDRESS": "[ANONYMOUS_ADDRESS]",
}

_CAP = r"[A-ZÄÖÜ][a-zäöüß]+"  # ein großgeschriebenes Wort (Namensbestandteil)
_NAME_SEQ = rf"{_CAP}(?:-{_CAP})?(?:[ \t]+{_CAP}(?:-{_CAP})?){{0,2}}"

# ---------------------------------------------------------------------------
# 1) Bestell- und Referenznummern
# ---------------------------------------------------------------------------
_ORDER_LABELS = (
    r"bestell(?:ungs?)?[\s-]?(?:nummer|nr\.?|no\.?|id)?|auftrags?[\s-]?(?:nummer|nr\.?)?"
    r"|rechnungs?[\s-]?(?:nummer|nr\.?)?|order[\s-]?(?:number|no\.?|nr\.?|id)?"
    r"|invoice[\s-]?(?:number|no\.?|nr\.?|id)?"
)
_OTHER_REF_LABELS = (
    r"kunden[\s-]?(?:nummer|nr\.?)|customer[\s-]?(?:number|no\.?|id)"
    r"|sendungs[\s-]?(?:nummer|nr\.?)|tracking[\s-]?(?:nummer|number|nr\.?|id|code)?"
    r"|retouren[\s-]?(?:nummer|nr\.?)|referenz(?:nummer)?|reference(?:\s+number)?|ticket(?:nummer)?"
)
_LABELED_REF = re.compile(
    rf"(?i:\b(?P<label>{_ORDER_LABELS}|{_OTHER_REF_LABELS}))"
    r"\s*(?:[:#.]|(?i:\bist\b|\bis\b|\blautet\b|\bwar\b))?\s*(?:#\s*)?"
    r"(?P<ref>(?i:[A-Z0-9](?:[A-Z0-9]|[-_/](?=[A-Z0-9])){3,30}))"
)
_HASH_ORDER = re.compile(r"(?<![\w#])#\s?(?P<ref>\d{3,12})\b")
_CODE_ORDER = re.compile(r"\b(?P<ref>(?:ORD|ORDER|BE|BN|AUF|SO|WEB|INV|RE)[-_]?\d{4,14})\b")
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

# ---------------------------------------------------------------------------
# 2) Strukturierte PII
# ---------------------------------------------------------------------------
_EMAIL = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,24}\b")
_OBFUSCATED_EMAIL = re.compile(
    r"\b[\w.+-]+\s*(?:\[at\]|\(at\)|\{at\}|\[@\])\s*[\w-]+"
    r"(?:\s*(?:\[dot\]|\(dot\)|\{dot\}|\.)\s*[\w-]+)+",
    re.IGNORECASE,
)
_IBAN = re.compile(r"\b[A-Z]{2}\d{2}(?:[ ]?[A-Z0-9]{4}){2,7}(?:[ ]?[A-Z0-9]{1,3})?\b")
_CARD = re.compile(r"(?<![\d-])(?:\d[ -]?){12,18}\d(?![\d-])")
_IPV4 = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}(?:25[0-5]|2[0-4]\d|1?\d?\d)\b")
_CONTEXT_PHONE = re.compile(
    r"(?i:\b(?:tel(?:efon)?(?:nummer)?|phone(?:\s+number)?|handy(?:nummer)?|mobil(?:e|nummer)?"
    r"|fon|cell|whatsapp|erreichbar\s+unter|ruf(?:en\s+sie)?\s+mich\s+(?:an\s+)?unter"
    r"|call\s+me\s+(?:at|on)|reach\s+me\s+(?:at|on))\b\.?:?)\s*"
    r"(?P<num>\+?\(?\d[\d \t./()-]{5,}\d)"
)
_PHONE = re.compile(
    r"(?<![\w+])(?:"
    r"(?:\+|00)\d{1,3}[ \t./-]?(?:\(0\)[ \t./-]?)?(?:\(?\d{1,5}\)?[ \t./-]?){1,5}\d{2,}"
    r"|0\d{2,5}[ \t./-]?\(?\d{2,}\)?(?:[ \t./-]?\d{2,}){0,3}"
    r"|\(\d{3}\)[ \t]?\d{3}[ \t.-]?\d{4}"
    r"|\d{3}[.-]\d{3}[.-]\d{4}"
    r")(?!\w)"
)
_DATE_LIKE = re.compile(r"^\d{1,2}[./]\d{1,2}[./]\d{2,4}$")

# ---------------------------------------------------------------------------
# 3) Adressen
# ---------------------------------------------------------------------------
_STREET_SUFFIX = r"(?:straße|strasse|str\.|weg|gasse|allee|platz|ring|damm|ufer|chaussee|steig|pfad)"
_STREET = re.compile(
    rf"\b(?:{_CAP}(?:-{_CAP})*{_STREET_SUFFIX}"
    r"|[A-ZÄÖÜ][a-zäöüß]+\s+(?:Straße|Strasse|Str\.|Weg|Gasse|Allee|Platz|Ring|Damm|Ufer|Chaussee))"
    r"\s+\d{1,4}\s?[a-zA-Z]?\b"
    r"|\b\d{1,5}\s+(?:[A-Z][a-z]+\s){1,3}(?:Street|St\.|Avenue|Ave\.?|Road|Rd\.?|Boulevard|Blvd\.?"
    r"|Lane|Ln\.?|Drive|Way|Court|Ct\.?)"
)
_ZIP_AFTER_ADDRESS = re.compile(
    r"\[ANONYMOUS_ADDRESS\](?P<sep>,[ \t]*|[ \t]*\n[ \t]*|[ \t]+)(?:D-)?\d{5}[ \t]+[A-ZÄÖÜ][\wäöüß-]+"
)
_ZIP_LABELED = re.compile(r"(?i:\bPLZ\b):?\s*\d{5}(?:[ \t]+[A-ZÄÖÜ][\wäöüß-]+)?")

# ---------------------------------------------------------------------------
# 4) Klarnamen
# ---------------------------------------------------------------------------
_SALUTATION_NAME = re.compile(
    r"\b(?P<title>Herrn?|Frau|Hr\.|Fr\.|Mr\.?|Mrs\.?|Ms\.?|Miss|Mister|Dr\.|Prof\.)"
    rf"[ \t]+(?P<name>(?:Dr\.[ \t]+)?{_NAME_SEQ})"
)
_STRONG_INTRO = re.compile(
    r"(?i:\b(?:mein\s+name\s+ist|ich\s+hei(?:ß|ss)e|my\s+name\s+is|my\s+name's|name:))"
    rf"[ \t]+(?P<name>{_NAME_SEQ})"
)
_WEAK_INTRO = re.compile(
    r"(?i:\b(?:this\s+is|hier\s+(?:ist|schreibt)|i\s+am|i'm|ich\s+bin))"
    rf"[ \t]+(?P<name>{_NAME_SEQ})"
)
_SIGN_OFF_NAME = re.compile(
    r"(?i:\b(?:mit\s+freundlichen\s+gr(?:ü|ue|u)(?:ß|ss)en|freundliche\s+gr(?:ü|ue|u)(?:ß|ss)e|mfg"
    r"|(?:viele|liebe|beste|herzliche|sch(?:ö|oe)ne)\s+gr(?:ü|ue|u)(?:ß|ss)e|gr(?:ü|ue|u)(?:ß|ss)e"
    r"|gru(?:ß|ss)|lg|vg|best\s+regards|kind\s+regards|warm\s+regards|regards|best\s+wishes|best"
    r"|cheers|thanks|thank\s+you|many\s+thanks|danke|vielen\s+dank|(?:yours\s+)?sincerely|yours))"
    rf"[ \t]*[,.!]?[ \t]*\n?[ \t]*(?P<name>{_NAME_SEQ})[ \t]*$",
    re.MULTILINE,
)
_CAPITALIZED_SEQ = re.compile(rf"\b(?P<name>{_NAME_SEQ})")


@dataclass(slots=True)
class ScrubResult:
    text: str
    entities: dict[str, int]
    order_references: list[str] = field(default_factory=list)
    other_references: list[str] = field(default_factory=list)

    @property
    def redacted(self) -> bool:
        return bool(self.entities)

    @property
    def order_reference_detected(self) -> bool:
        return bool(self.order_references)


class _Scrubber:
    def __init__(self, text: str) -> None:
        self.text = text
        self.counts: Counter[str] = Counter()
        self._protected: list[str] = []
        self.order_refs: list[str] = []
        self.other_refs: list[str] = []

    # -- Referenzen ---------------------------------------------------------
    def _protect(self, value: str) -> str:
        self._protected.append(value)
        return f"\x00{len(self._protected) - 1}\x00"

    def protect_references(self) -> None:
        def labeled(match: re.Match[str]) -> str:
            ref = match.group("ref")
            if sum(ch.isdigit() for ch in ref) < 3 or _ISO_DATE.match(ref):
                return match.group(0)
            label = match.group("label").lower()
            is_order = re.match(r"bestell|auftrag|rechnung|order|invoice", label) is not None
            (self.order_refs if is_order else self.other_refs).append(ref)
            start = match.start("ref") - match.start()
            return match.group(0)[:start] + self._protect(ref)

        self.text = _LABELED_REF.sub(labeled, self.text)

        def plain_order(match: re.Match[str]) -> str:
            ref = match.group("ref")
            self.order_refs.append(ref)
            start = match.start("ref") - match.start()
            return match.group(0)[:start] + self._protect(ref)

        self.text = _HASH_ORDER.sub(plain_order, self.text)
        self.text = _CODE_ORDER.sub(plain_order, self.text)

    def restore_references(self) -> None:
        self.text = re.sub(r"\x00(\d+)\x00", lambda m: self._protected[int(m.group(1))], self.text)

    # -- Hilfsfunktionen ----------------------------------------------------
    def _replace(
        self,
        pattern: re.Pattern[str],
        kind: str,
        *,
        group: str | int = 0,
        validate: Callable[[str], bool] | None = None,
    ) -> None:
        placeholder = PLACEHOLDERS[kind]

        def repl(match: re.Match[str]) -> str:
            value = match.group(group)
            if validate is not None and not validate(value):
                return match.group(0)
            self.counts[kind] += 1
            if group == 0:
                return placeholder
            start, end = match.start(group) - match.start(), match.end(group) - match.start()
            whole = match.group(0)
            return whole[:start] + placeholder + whole[end:]

        self.text = pattern.sub(repl, self.text)

    # -- Namen ----------------------------------------------------------------
    @staticmethod
    def _trim_name(candidate: str, *, require_known_first_name: bool) -> str | None:
        """Schneidet Nicht-Namens-Tokens ab; None, wenn kein Name übrig bleibt."""
        tokens = candidate.split()
        kept: list[str] = []
        for token in tokens:
            if token.lower().rstrip(".") in NON_NAME_TOKENS:
                break
            kept.append(token)
        if not kept:
            return None
        if require_known_first_name and kept[0].split("-")[0].lower() not in FIRST_NAMES:
            return None
        return " ".join(kept)

    def _replace_names(self, pattern: re.Pattern[str], *, require_known_first_name: bool) -> None:
        def repl(match: re.Match[str]) -> str:
            name = self._trim_name(match.group("name"), require_known_first_name=require_known_first_name)
            if name is None:
                return match.group(0)
            self.counts["NAME"] += 1
            whole = match.group(0)
            start = match.start("name") - match.start()
            return whole[:start] + PLACEHOLDERS["NAME"] + whole[start + len(name) :]

        self.text = pattern.sub(repl, self.text)

    def replace_lexicon_names(self) -> None:
        def repl(match: re.Match[str]) -> str:
            tokens = match.group("name").split()
            out: list[str] = []
            i = 0
            while i < len(tokens):
                token = tokens[i]
                if token.split("-")[0].lower() in FIRST_NAMES:
                    # Vorname + optional ein Nachname (sofern kein Nicht-Namens-Token).
                    if i + 1 < len(tokens) and tokens[i + 1].lower() not in NON_NAME_TOKENS:
                        i += 1
                    out.append(PLACEHOLDERS["NAME"])
                    self.counts["NAME"] += 1
                else:
                    out.append(token)
                i += 1
            return " ".join(out)

        self.text = _CAPITALIZED_SEQ.sub(repl, self.text)

    # -- Ablauf -----------------------------------------------------------------
    def run(self) -> ScrubResult:
        self.protect_references()

        self._replace(_EMAIL, "EMAIL")
        self._replace(_OBFUSCATED_EMAIL, "EMAIL")
        self._replace(_IBAN, "IBAN", validate=_valid_iban)
        self._replace(_CARD, "CARD", validate=_valid_luhn)
        self._replace(_IPV4, "IP")
        self._replace(_CONTEXT_PHONE, "PHONE", group="num", validate=_plausible_phone)
        self._replace(_PHONE, "PHONE", validate=_plausible_phone)

        self._replace(_STREET, "ADDRESS")
        self.text = _ZIP_AFTER_ADDRESS.sub(lambda m: PLACEHOLDERS["ADDRESS"], self.text)
        self._replace(_ZIP_LABELED, "ADDRESS")

        self._replace_names(_SALUTATION_NAME, require_known_first_name=False)
        self._replace_names(_STRONG_INTRO, require_known_first_name=False)
        self._replace_names(_SIGN_OFF_NAME, require_known_first_name=False)
        self._replace_names(_WEAK_INTRO, require_known_first_name=True)
        self.replace_lexicon_names()

        self.restore_references()
        return ScrubResult(
            text=self.text,
            entities=dict(self.counts),
            order_references=self.order_refs,
            other_references=self.other_refs,
        )


def _digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _plausible_phone(value: str) -> bool:
    if _DATE_LIKE.match(value.strip()):
        return False
    return 7 <= len(_digits(value)) <= 15


def _valid_luhn(value: str) -> bool:
    digits = _digits(value)
    if not 13 <= len(digits) <= 19:
        return False
    total = 0
    for index, char in enumerate(reversed(digits)):
        number = int(char)
        if index % 2 == 1:
            number *= 2
            if number > 9:
                number -= 9
        total += number
    return total % 10 == 0


def _valid_iban(value: str) -> bool:
    compact = value.replace(" ", "").upper()
    if not 15 <= len(compact) <= 34:
        return False
    rearranged = compact[4:] + compact[:4]
    numeric = "".join(str(int(ch, 36)) for ch in rearranged)
    return int(numeric) % 97 == 1


def scrub_pii(text: str) -> ScrubResult:
    """Anonymisiert personenbezogene Daten im Text. Idempotent und seiteneffektfrei."""
    return _Scrubber(text.replace("\x00", "")).run()
