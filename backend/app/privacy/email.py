"""Conservative extraction of the latest message from common email formats."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import ClassVar

_HTML_TAG = re.compile(
    r"(?is)</?(?:html|body|p|div|span|br|blockquote|table|tr|td|ul|ol|li|a|b|strong|i|em|head|title)\b"
)
_QUOTE_BOUNDARY = re.compile(
    r"(?i)^\s*(?:"
    r"-{2,}\s*(?:original\s+message|forwarded\s+message|urspr(?:ü|ue)ngliche\s+nachricht|"
    r"weitergeleitete\s+nachricht)\s*-*"
    r"|begin\s+forwarded\s+message:"
    r"|(?:on|am)\s+.+\b(?:wrote|schrieb)\b.*:"
    r")\s*$"
)
_OUTLOOK_HEADERS = re.compile(r"(?im)^\s*(?:from|von):\s*.+$\n\s*(?:sent|gesendet):\s*.+$")


class _TextExtractor(HTMLParser):
    _BLOCK_TAGS: ClassVar[set[str]] = {
        "address",
        "article",
        "br",
        "div",
        "footer",
        "h1",
        "h2",
        "h3",
        "li",
        "p",
        "section",
        "tr",
    }
    _IGNORED_TAGS: ClassVar[set[str]] = {"script", "style", "noscript"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._IGNORED_TAGS:
            self._ignored_depth += 1
        elif not self._ignored_depth and tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag in self._IGNORED_TAGS and self._ignored_depth:
            self._ignored_depth -= 1
        elif not self._ignored_depth and tag in self._BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._ignored_depth:
            self.parts.append(data)


def _plain_text(text: str) -> str:
    if not _HTML_TAG.search(text):
        return text
    parser = _TextExtractor()
    parser.feed(text)
    parser.close()
    return "".join(parser.parts)


def preprocess_email(text: str) -> str:
    """Keep the latest recognizable email body, leaving unknown formats intact."""
    lines = _plain_text(text).replace("\r\n", "\n").replace("\r", "\n").split("\n")
    latest: list[str] = []
    for index, line in enumerate(lines):
        if _QUOTE_BOUNDARY.match(line):
            break
        if _OUTLOOK_HEADERS.match("\n".join(lines[index : index + 4])):
            break
        if line.lstrip().startswith(">"):
            continue
        latest.append(line)
    cleaned = "\n".join(latest)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()
