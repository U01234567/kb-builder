"""Turn one PDF or saved web page into passages, each with the place it came from (page or headings)."""

import io
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path

from pypdf import PdfReader

SUPPORTED = {".pdf", ".html", ".htm"}
PASSAGE_CHARS = 1200  # roughly a few paragraphs: long enough for context, short enough to judge


@dataclass(frozen=True)
class Passage:
    """A piece of a source, and where in the source it is ('p. 3' or 'Heading › Subheading')."""

    location: str
    text: str


@dataclass(frozen=True)
class Document:
    """Everything kb-builder takes from one file: a title, a URL if the file names one, the passages."""

    title: str
    url: str
    passages: tuple

    @property
    def text(self) -> str:
        """All passages as one text."""
        return "\n\n".join(p.text for p in self.passages)


def read(path: Path) -> Document:
    """Read a .pdf or .html/.htm file; the file name is the title when the file has none."""
    if path.suffix.lower() == ".pdf":
        return read_pdf(path.read_bytes(), fallback_title=path.stem)
    return read_html(path.read_text(encoding="utf-8", errors="replace"), fallback_title=path.stem)


def chunk(blocks: list[str], size: int = PASSAGE_CHARS) -> list[str]:
    """Join blocks (paragraphs) into pieces of about `size` characters, never splitting a block."""
    pieces, current = [], ""
    for block in blocks:
        if current and len(current) + len(block) > size:
            pieces.append(current)
            current = ""
        current = f"{current}\n{block}" if current else block
    return pieces + [current] if current else pieces


def read_pdf(data: bytes, fallback_title: str = "") -> Document:
    """Passages per page. The title comes from the PDF's metadata, else its first line."""
    reader = PdfReader(io.BytesIO(data))
    passages = []
    for number, page in enumerate(reader.pages, start=1):
        blocks = [b.strip() for b in re.split(r"\n\s*\n", page.extract_text() or "") if b.strip()]
        passages += [Passage(f"p. {number}", text) for text in chunk(blocks)]
    title = (reader.metadata.title if reader.metadata else None) or ""
    if not title and passages:
        title = passages[0].text.splitlines()[0][:120]
    return Document(title.strip() or fallback_title, "", tuple(passages))


SKIP = {"script", "style", "noscript", "template", "svg", "nav", "header", "footer", "form", "button"}
BLOCKS = {"p", "li", "dd", "dt", "blockquote", "pre", "figcaption", "caption", "tr", "h1", "h2", "h3", "h4", "h5", "h6"}
HEADINGS = {"h1": 1, "h2": 2, "h3": 3, "h4": 4, "h5": 5, "h6": 6}


class _PageParser(HTMLParser):
    """Collects the visible text blocks of a page, each with the path of headings above it.

    Menus, scripts, headers, footers and forms are skipped. Table cells are joined with ' | ',
    and an image counts as '[figure: <alt text>]'.
    """

    def __init__(self) -> None:
        """Start with no title, URL, headings or text."""
        super().__init__(convert_charrefs=True)
        self.skipping = 0  # > 0 while inside a tag from SKIP
        self.title, self.url, self.in_title, self.first_heading = "", "", False, ""
        self.headings: list[tuple[int, str]] = []
        self.blocks: list[tuple[str, str]] = []  # (heading path, text)
        self.buffer: list[str] = []

    def handle_starttag(self, tag, attrs):
        """Track skipped parts, the title, the page's own URL, figures, table cells and block starts."""
        attrs = dict(attrs)
        if tag in SKIP:
            self.skipping += 1
        elif tag == "title":
            self.in_title = True
        elif tag == "link" and attrs.get("rel") == "canonical":
            self.url = attrs.get("href") or self.url
        elif tag == "meta" and attrs.get("property") == "og:url" and not self.url:
            self.url = attrs.get("content") or ""
        elif tag == "img" and attrs.get("alt") and not self.skipping:
            self.buffer.append(f"[figure: {attrs['alt']}]")
        elif tag in ("td", "th"):
            self.buffer.append(" | ")
        elif tag in BLOCKS or tag == "br":
            self.flush()

    def handle_endtag(self, tag):
        """Close skipped parts and the title; a closing heading becomes part of the heading path."""
        if tag in SKIP:
            self.skipping = max(0, self.skipping - 1)
        elif tag == "title":
            self.in_title = False
        elif tag in HEADINGS and not self.skipping:
            text = self.take_text()
            if text:
                level = HEADINGS[tag]
                self.headings = [h for h in self.headings if h[0] < level] + [(level, text)]
                self.first_heading = self.first_heading or text
        elif tag in BLOCKS:
            self.flush()

    def handle_data(self, data):
        """Text goes to the title, or to the current block unless it is in a skipped part."""
        if self.in_title:
            self.title += data
        elif not self.skipping:
            self.buffer.append(data)

    def take_text(self) -> str:
        """The text collected since the last block, with whitespace tidied, and start a new one."""
        text = re.sub(r"\s+", " ", "".join(self.buffer)).strip(" |")
        self.buffer = []
        return text

    def flush(self) -> None:
        """End the current block, keeping it with the headings above it if it has any text."""
        text = self.take_text()
        if text:
            self.blocks.append((" › ".join(h[1] for h in self.headings), text))


def read_html(html: str, fallback_title: str = "") -> Document:
    """Passages per section (the blocks under the same headings). The title is <title>, else the first heading."""
    parser = _PageParser()
    parser.feed(html)
    parser.close()
    parser.flush()
    passages = []
    for location in dict.fromkeys(path for path, _ in parser.blocks):
        texts = [text for path, text in parser.blocks if path == location]
        passages += [Passage(location or "(top of page)", piece) for piece in chunk(texts)]
    title = parser.title.strip() or parser.first_heading or fallback_title
    return Document(re.sub(r"\s+", " ", title), parser.url, tuple(passages))
