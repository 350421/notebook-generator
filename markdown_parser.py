"""把 Markdown 文本解析为渲染器可消费的内容块。"""

from __future__ import annotations

import re


Block = dict[str, str]

_TITLE_RE = re.compile(r"^\s{0,3}(?P<marks>#{1,6})\s+(?P<content>.+?)\s*$")
_ORDERED_LIST_RE = re.compile(r"^\s*\d+\s*[.、．]\s*.+$")
_UNORDERED_LIST_RE = re.compile(r"^\s*[-+*]\s+.+$")
_IMAGE_RE = re.compile(
    r'^\s*!\[(?P<alt>[^\]]*)\]\(\s*(?P<src>\S+?)(?:\s+["\'][^"\']*["\'])?\s*\)\s*$'
)
_QUOTE_RE = re.compile(r"^\s*>\s?(.*)$")
_CHINESE_PREFIX_RE = re.compile(
    r"^\s*(?P<prefix>标题|小标题|正文)\s*[：:]\s*(?P<content>.*?)\s*$"
)
_NUMBERED_SUBTITLE_RE = re.compile(
    r"^\s*\d+\s*[.、．]\s*(?P<content>[^：:]{1,15}[：:].{1,24})\s*$"
)
_HORIZONTAL_RULE_RE = re.compile(
    r"^\s{0,3}(?:(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,})$"
)
_BODY_SENTENCE_END_RE = re.compile(r"[。；，,]\s*$")
_URLISH_RE = re.compile(
    r"(?:https?[:：]?/|www\.|[a-z0-9-]+\.(?:com|cn|net|org|io|ru)(?:/|\b))",
    re.IGNORECASE,
)


def _next_nonempty_line(lines: list[str], start_index: int) -> str:
    """返回 start_index 之后的下一行非空文本。"""
    for index in range(start_index + 1, len(lines)):
        if lines[index].strip():
            return lines[index].strip()
    return ""


def _ordered_subtitle_content(
    line: str,
    next_line: str,
) -> str | None:
    """判断 `1、标题` 是否更像小标题而不是列表项。"""
    if not _ORDERED_LIST_RE.match(line):
        return None

    content = re.sub(r"^\s*\d+\s*[.、．]\s*", "", line).strip()
    if not content:
        return None
    if len(content) > 24 or _BODY_SENTENCE_END_RE.search(content):
        return None
    if not next_line:
        return None
    if any(
        pattern.match(next_line)
        for pattern in (
            _TITLE_RE,
            _ORDERED_LIST_RE,
            _UNORDERED_LIST_RE,
            _IMAGE_RE,
            _QUOTE_RE,
            _CHINESE_PREFIX_RE,
            _HORIZONTAL_RULE_RE,
        )
    ):
        return None

    next_looks_like_body = (
        len(next_line) > 18
        or bool(_BODY_SENTENCE_END_RE.search(next_line))
        or "：" in next_line
        or ":" in next_line
    )
    return content if next_looks_like_body else None


def _is_plain_text_line(line: str) -> bool:
    """判断一行是否可参与纯文本标题智能识别。"""
    return not _URLISH_RE.search(line) and not any(
        pattern.match(line)
        for pattern in (
            _TITLE_RE,
            _IMAGE_RE,
            _QUOTE_RE,
            _ORDERED_LIST_RE,
            _UNORDERED_LIST_RE,
            _CHINESE_PREFIX_RE,
            _HORIZONTAL_RULE_RE,
        )
    )


def _smart_heading_indices(lines: list[str]) -> tuple[int | None, set[int]]:
    """识别无前缀纯文本中的一级标题和二级标题行。"""
    nonempty_indices = [index for index, line in enumerate(lines) if line.strip()]
    if not nonempty_indices:
        return None, set()

    explicit_primary_exists = any(
        (
            (match := _TITLE_RE.match(line)) is not None
            and len(match.group("marks")) == 1
        )
        or (
            (prefix_match := _CHINESE_PREFIX_RE.match(line)) is not None
            and prefix_match.group("prefix") == "标题"
        )
        for line in lines
        if line.strip()
    )

    primary_index: int | None = None
    first_index = nonempty_indices[0]
    first_text = lines[first_index].strip()
    if (
        not explicit_primary_exists
        and _is_plain_text_line(first_text)
        and len(first_text) <= 50
    ):
        followed_by_blank = (
            first_index + 1 < len(lines) and not lines[first_index + 1].strip()
        )
        looks_like_heading = not _BODY_SENTENCE_END_RE.search(first_text)
        if followed_by_blank or looks_like_heading:
            primary_index = first_index

    subtitle_indices: set[int] = set()
    for position, index in enumerate(nonempty_indices):
        if index == primary_index or position == len(nonempty_indices) - 1:
            continue

        text = lines[index].strip()
        next_index = nonempty_indices[position + 1]
        next_text = lines[next_index].strip()
        previous_text = (
            lines[nonempty_indices[position - 1]].strip()
            if position > 0
            else ""
        )
        if not _is_plain_text_line(text) or not _is_plain_text_line(next_text):
            continue
        if previous_text and _URLISH_RE.search(previous_text):
            continue
        if len(text) > 22 or _BODY_SENTENCE_END_RE.search(text):
            continue

        next_is_longer_body = len(next_text) > 15 or len(next_text) >= len(text) + 5
        if next_is_longer_body:
            subtitle_indices.add(index)

    return primary_index, subtitle_indices


def parse_markdown(markdown_text: str) -> list[Block]:
    """
    将 Markdown 解析为标题、正文、列表、图片和引用内容块。

    返回示例：
    [{"type": "title", "content": "标题"}]
    """
    if not isinstance(markdown_text, str):
        raise TypeError("markdown_text 必须是字符串")

    lines = markdown_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    smart_primary_index, smart_subtitle_indices = _smart_heading_indices(lines)

    blocks: list[Block] = []
    pending_type: str | None = None
    pending_list_kind: str | None = None
    pending_lines: list[str] = []

    def flush_pending() -> None:
        nonlocal pending_type, pending_list_kind, pending_lines
        if pending_type and pending_lines:
            url_line_count = sum(
                bool(_URLISH_RE.search(line)) for line in pending_lines
            )
            is_multiline_url_list = (
                pending_type == "body"
                and len(pending_lines) >= 5
                and url_line_count >= 3
                and url_line_count * 2 >= len(pending_lines)
            )
            if is_multiline_url_list:
                blocks.extend(
                    {"type": "body", "content": line.strip()}
                    for line in pending_lines
                    if line.strip()
                )
            elif pending_type == "body":
                # 长正文按自然段自动拆分，避免单段过长导致分页失败
                combined = "\n".join(pending_lines).strip()
                if len(combined) > 300:
                    parts = re.split(r"(?<=[。！？])", combined)
                    chunk = ""
                    for part in parts:
                        if len(chunk) + len(part) > 280 and chunk:
                            blocks.append({"type": "body", "content": chunk.strip()})
                            chunk = part
                        else:
                            chunk += part
                    if chunk.strip():
                        blocks.append({"type": "body", "content": chunk.strip()})
                else:
                    blocks.append({"type": "body", "content": combined})
            else:
                blocks.append(
                    {
                        "type": pending_type,
                        "content": "\n".join(pending_lines).strip(),
                    }
                )
        pending_type = None
        pending_list_kind = None
        pending_lines = []

    for line_index, raw_line in enumerate(lines):
        line = raw_line.rstrip()
        next_nonempty_line = _next_nonempty_line(lines, line_index)

        if not line.strip():
            flush_pending()
            continue

        if _HORIZONTAL_RULE_RE.match(line):
            flush_pending()
            continue

        title_match = _TITLE_RE.match(line)
        if title_match:
            flush_pending()
            blocks.append(
                {"type": "title", "content": title_match.group("content").strip()}
            )
            continue

        numbered_subtitle_match = _NUMBERED_SUBTITLE_RE.match(line)
        if numbered_subtitle_match:
            flush_pending()
            blocks.append(
                {
                    "type": "title",
                    "content": numbered_subtitle_match.group("content").strip(),
                }
            )
            continue

        ordered_subtitle_content = _ordered_subtitle_content(
            line,
            next_nonempty_line,
        )
        if ordered_subtitle_content is not None:
            flush_pending()
            blocks.append({"type": "title", "content": ordered_subtitle_content})
            continue

        image_match = _IMAGE_RE.match(line)
        if image_match:
            flush_pending()
            blocks.append({"type": "image", "content": image_match.group("src")})
            continue

        quote_match = _QUOTE_RE.match(line)
        if quote_match:
            if pending_type != "quote":
                flush_pending()
                pending_type = "quote"
            pending_lines.append(quote_match.group(1).strip())
            continue

        if _ORDERED_LIST_RE.match(line):
            if pending_type != "list" or pending_list_kind != "ordered":
                flush_pending()
                pending_type = "list"
                pending_list_kind = "ordered"
            pending_lines.append(line.strip())
            continue

        if _UNORDERED_LIST_RE.match(line):
            if pending_type != "list" or pending_list_kind != "unordered":
                flush_pending()
                pending_type = "list"
                pending_list_kind = "unordered"
            pending_lines.append(line.strip())
            continue

        prefix_match = _CHINESE_PREFIX_RE.match(line)
        if prefix_match:
            prefix = prefix_match.group("prefix")
            content = prefix_match.group("content").strip()
            if not content:
                flush_pending()
                continue
            if prefix in {"标题", "小标题"}:
                flush_pending()
                blocks.append({"type": "title", "content": content})
            else:
                ordered_prefixed_subtitle = _ordered_subtitle_content(
                    content,
                    next_nonempty_line,
                )
                if ordered_prefixed_subtitle is not None:
                    flush_pending()
                    blocks.append(
                        {"type": "title", "content": ordered_prefixed_subtitle}
                    )
                    continue
                if pending_type != "body":
                    flush_pending()
                    pending_type = "body"
                pending_lines.append(content)
            continue

        if line_index == smart_primary_index or line_index in smart_subtitle_indices:
            flush_pending()
            blocks.append({"type": "title", "content": line.strip()})
            continue

        if pending_type != "body":
            flush_pending()
            pending_type = "body"
        pending_lines.append(line.strip())

    flush_pending()
    return blocks
