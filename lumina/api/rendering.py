"""
lumina/api/rendering.py — 面向不可信内容的安全 HTML 渲染。
"""
from __future__ import annotations

import markdown as md
import nh3

_ALLOWED_TAGS = {
    "a",
    "blockquote",
    "br",
    "code",
    "del",
    "em",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "hr",
    "li",
    "ol",
    "p",
    "pre",
    "strong",
    "table",
    "tbody",
    "td",
    "th",
    "thead",
    "tr",
    "ul",
}

_ALLOWED_ATTRIBUTES = {
    "a": {"href", "title"},
    "code": {"class"},
}

_ALLOWED_URL_SCHEMES = {"http", "https", "mailto"}


def sanitize_html_fragment(html: str) -> str:
    return nh3.clean(
        html or "",
        tags=_ALLOWED_TAGS,
        attributes=_ALLOWED_ATTRIBUTES,
        url_schemes=_ALLOWED_URL_SCHEMES,
        link_rel="noopener noreferrer nofollow",
        strip_comments=True,
    )


def render_markdown_html(content: str) -> str:
    try:
        raw_html = md.markdown(content or "", extensions=["fenced_code", "tables"])
    except TypeError:
        raw_html = md.markdown(content or "")
    return sanitize_html_fragment(raw_html)
