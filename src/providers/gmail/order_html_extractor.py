from __future__ import annotations

from html.parser import HTMLParser
from urllib.parse import urlparse

from providers.gmail.models import GmailPhase2Link
from providers.gmail.order_scrubber_rules import IMPORTANT_LINK_PATTERNS, TRACKING_HOST_PATTERNS


BLOCK_TAGS = {
    "address",
    "article",
    "br",
    "div",
    "footer",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "header",
    "li",
    "p",
    "section",
    "table",
    "td",
    "th",
    "tr",
    "ul",
}
SKIP_TAGS = {"head", "noscript", "script", "style", "title"}
IGNORE_TAGS = {"meta", "link", "comment"}


class _VisibleTextHTMLParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._chunks: list[str] = []
        self._skip_stack: list[str] = []
        self._hidden_stack: list[str] = []
        self._anchor_stack: list[dict[str, str | list[str]]] = []
        self._hidden_nodes_removed = 0
        self._tracking_images_removed = 0
        self.links: list[GmailPhase2Link] = []

    @property
    def hidden_nodes_removed(self) -> int:
        return self._hidden_nodes_removed

    @property
    def tracking_images_removed(self) -> int:
        return self._tracking_images_removed

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {key.lower(): (value or "") for key, value in attrs}
        normalized_tag = tag.lower()
        if normalized_tag in IGNORE_TAGS:
            return
        if normalized_tag in SKIP_TAGS:
            self._skip_stack.append(normalized_tag)
            return
        if self._is_hidden(normalized_tag, attr_map):
            self._hidden_stack.append(normalized_tag)
            self._hidden_nodes_removed += 1
            return
        if normalized_tag == "img" and self._is_tracking_image(attr_map):
            self._tracking_images_removed += 1
            return
        if normalized_tag in BLOCK_TAGS:
            self._newline()
        if normalized_tag == "a":
            self._anchor_stack.append({"href": attr_map.get("href", ""), "text": []})

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.lower()
        if self._skip_stack:
            if normalized_tag in self._skip_stack:
                while self._skip_stack:
                    popped = self._skip_stack.pop()
                    if popped == normalized_tag:
                        break
            return
        if self._hidden_stack:
            if normalized_tag in self._hidden_stack:
                while self._hidden_stack:
                    popped = self._hidden_stack.pop()
                    if popped == normalized_tag:
                        break
            return
        if normalized_tag in BLOCK_TAGS:
            self._newline()
        if normalized_tag == "a" and self._anchor_stack:
            anchor = self._anchor_stack.pop()
            href = str(anchor.get("href") or "").strip()
            label = " ".join(str(part).strip() for part in anchor.get("text", []) if str(part).strip()).strip() or None
            if href:
                self.links.append(
                    GmailPhase2Link(
                        label=label,
                        url=href,
                        raw_url=href,
                        normalized_url=href,
                        link_type=_classify_link(label=label, url=href),
                        source="html_anchor",
                        is_tracking=_is_tracking_link(href),
                    )
                )

    def handle_data(self, data: str) -> None:
        if self._skip_stack or self._hidden_stack:
            return
        if not data.strip():
            if self._chunks and not self._chunks[-1].endswith("\n"):
                self._chunks.append(" ")
            return
        if self._anchor_stack:
            self._anchor_stack[-1]["text"].append(data)
        self._chunks.append(data)

    def get_text(self) -> str:
        text = "".join(self._chunks)
        lines = [" ".join(line.split()) for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()

    def handle_comment(self, data: str) -> None:
        del data
        return

    def _newline(self) -> None:
        if not self._chunks or self._chunks[-1].endswith("\n"):
            return
        self._chunks.append("\n")

    @staticmethod
    def _is_hidden(tag: str, attrs: dict[str, str]) -> bool:
        if attrs.get("hidden", "").lower() in {"", "hidden"} and "hidden" in attrs:
            return True
        if attrs.get("aria-hidden", "").lower() == "true":
            return True
        style = attrs.get("style", "").replace(" ", "").lower()
        if any(token in style for token in ("display:none", "visibility:hidden", "opacity:0", "max-height:0", "height:0", "width:0", "font-size:0")):
            return True
        classes = attrs.get("class", "").lower()
        if "preheader" in classes and tag in {"div", "span", "td", "p"}:
            return True
        return False

    @staticmethod
    def _is_tracking_image(attrs: dict[str, str]) -> bool:
        width = attrs.get("width", "").strip()
        height = attrs.get("height", "").strip()
        src = attrs.get("src", "")
        if width == "1" and height == "1":
            return True
        return _is_tracking_link(src)


def _is_tracking_link(url: str) -> bool:
    if not url:
        return False
    return any(pattern.search(url) for pattern in TRACKING_HOST_PATTERNS)


def _classify_link(*, label: str | None, url: str) -> str:
    text = f"{label or ''} {url}".strip()
    for link_type, pattern in IMPORTANT_LINK_PATTERNS.items():
        if pattern.search(text):
            return link_type
    return "other"


def extract_visible_text_from_html(html: str) -> tuple[str, list[GmailPhase2Link], dict[str, int]]:
    parser = _VisibleTextHTMLParser()
    parser.feed(html)
    parser.close()
    return (
        parser.get_text(),
        parser.links,
        {
            "hidden_nodes_removed": parser.hidden_nodes_removed,
            "tracking_images_removed": parser.tracking_images_removed,
        },
    )
