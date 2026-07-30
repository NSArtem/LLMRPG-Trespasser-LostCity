#!/usr/bin/env python3
"""Export a public ChatGPT shared conversation, including reasoning messages.

ChatGPT share pages embed the conversation as a flattened JSON value in a
React Router stream.  This script downloads (or reads) that HTML, decodes the
flattened value, locates the conversation graph, and writes a lossless,
message-oriented JSON export using only the Python standard library.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "Chrome/131.0 Safari/537.36"
)
ENQUEUE_MARKER = "window.__reactRouterContext.streamController.enqueue("
SHARE_ID_RE = re.compile(
    r"(?:https?://)?(?:www\.)?chatgpt\.com/share/"
    r"(?P<id>[0-9a-fA-F-]+)"
)


class ScriptCollector(HTMLParser):
    """Collect inline script bodies without needing an HTML dependency."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_script = False
        self._parts: list[str] = []
        self.scripts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag.lower() == "script":
            self._in_script = True
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._in_script:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._in_script:
            self.scripts.append("".join(self._parts))
            self._in_script = False
            self._parts = []


def canonical_share_url(value: str) -> tuple[str, str]:
    match = SHARE_ID_RE.fullmatch(value.rstrip("/"))
    if not match:
        raise ValueError(
            "expected a public URL like https://chatgpt.com/share/<share-id>"
        )
    share_id = match.group("id")
    return f"https://chatgpt.com/share/{share_id}", share_id


def download_html(url: str) -> str:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(charset)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"ChatGPT returned HTTP {exc.code} for {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"could not download {url}: {exc.reason}") from exc


def iter_enqueued_strings(html: str) -> Iterator[str]:
    parser = ScriptCollector()
    parser.feed(html)
    decoder = json.JSONDecoder()
    for script in parser.scripts:
        offset = 0
        while True:
            marker_at = script.find(ENQUEUE_MARKER, offset)
            if marker_at < 0:
                break
            argument_at = marker_at + len(ENQUEUE_MARKER)
            try:
                value, consumed = decoder.raw_decode(script[argument_at:].lstrip())
            except json.JSONDecodeError as exc:
                raise ValueError("invalid React Router stream payload") from exc
            if isinstance(value, str):
                yield value
            offset = argument_at + consumed


def extract_flattened_value(html: str) -> list[Any]:
    for payload in iter_enqueued_strings(html):
        for line in payload.splitlines():
            if not line.startswith("["):
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(value, list) and value:
                return value
    raise ValueError("the share page contains no flattened conversation payload")


class FlattenedDecoder:
    """Decode ChatGPT's devalue-style indexed JSON representation."""

    _SPECIAL = {
        -1: {"$special": "undefined"},
        -2: {"$special": "hole"},
        -3: {"$special": "NaN"},
        -4: {"$special": "positive-infinity"},
        -5: {"$special": "negative-infinity"},
        -6: {"$special": "negative-zero"},
    }

    def __init__(self, values: list[Any]) -> None:
        self.values = values
        self.memo: dict[int, Any] = {}

    def decode(self) -> Any:
        return self._hydrate(0)

    def _hydrate(self, reference: Any) -> Any:
        if not isinstance(reference, int) or isinstance(reference, bool):
            return reference
        if reference < 0:
            return self._SPECIAL.get(reference, {"$special": reference})
        if reference >= len(self.values):
            raise ValueError(f"flattened value references missing index {reference}")
        if reference in self.memo:
            return self.memo[reference]

        value = self.values[reference]
        if isinstance(value, list):
            result: list[Any] = []
            self.memo[reference] = result
            result.extend(self._hydrate(item) for item in value)
            return result
        if isinstance(value, dict):
            result_dict: dict[str, Any] = {}
            self.memo[reference] = result_dict
            for encoded_key, encoded_value in value.items():
                key = encoded_key
                if encoded_key.startswith("_") and encoded_key[1:].isdigit():
                    decoded_key = self._hydrate(int(encoded_key[1:]))
                    key = str(decoded_key)
                result_dict[key] = self._hydrate(encoded_value)
            return result_dict

        self.memo[reference] = value
        return value


def walk_values(value: Any, seen: set[int] | None = None) -> Iterator[Any]:
    if seen is None:
        seen = set()
    if isinstance(value, (dict, list)):
        identity = id(value)
        if identity in seen:
            return
        seen.add(identity)
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from walk_values(child, seen)
    elif isinstance(value, list):
        for child in value:
            yield from walk_values(child, seen)


def find_conversation(decoded: Any) -> dict[str, Any]:
    candidates: list[tuple[int, dict[str, Any]]] = []
    for value in walk_values(decoded):
        if not isinstance(value, dict):
            continue
        mapping = value.get("mapping")
        if not isinstance(mapping, dict) or not mapping:
            continue
        score = sum(
            key in value
            for key in ("title", "current_node", "conversation_id", "create_time")
        )
        candidates.append((score, value))
    if not candidates:
        raise ValueError("could not locate a conversation mapping in the payload")
    return max(candidates, key=lambda item: item[0])[1]


def message_text(content: Any) -> str:
    """Return a searchable rendering while retaining the original content."""

    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(filter(None, (message_text(item) for item in content)))
    if not isinstance(content, dict):
        return ""

    parts = content.get("parts")
    if isinstance(parts, list):
        return "\n".join(filter(None, (message_text(part) for part in parts)))
    thoughts = content.get("thoughts")
    if isinstance(thoughts, list):
        rendered_thoughts: list[str] = []
        for thought in thoughts:
            if not isinstance(thought, dict):
                rendered_thoughts.append(message_text(thought))
                continue
            summary = message_text(thought.get("summary"))
            detail = message_text(thought.get("content"))
            if summary and detail:
                rendered_thoughts.append(f"{summary}\n{detail}")
            else:
                rendered_thoughts.append(summary or detail)
        return "\n\n".join(filter(None, rendered_thoughts))
    for key in ("text", "summary", "content", "result", "code"):
        if key in content:
            rendered = message_text(content[key])
            if rendered:
                return rendered
    return ""


def ordered_node_ids(
    mapping: dict[str, Any], current_node: str | None
) -> tuple[list[str], set[str]]:
    """Put the active branch first, then retain any detached/alternate nodes."""

    active_reversed: list[str] = []
    node_id = current_node
    visited: set[str] = set()
    while isinstance(node_id, str) and node_id in mapping and node_id not in visited:
        visited.add(node_id)
        active_reversed.append(node_id)
        parent = mapping[node_id].get("parent")
        node_id = parent if isinstance(parent, str) else None
    active = list(reversed(active_reversed))

    remainder = [node_id for node_id in mapping if node_id not in visited]
    remainder.sort(
        key=lambda candidate: (
            (mapping[candidate].get("message") or {}).get("create_time")
            is None,
            (mapping[candidate].get("message") or {}).get("create_time") or 0,
            candidate,
        )
    )
    return active + remainder, set(active)


def build_export(
    conversation: dict[str, Any], source_url: str, share_id: str
) -> dict[str, Any]:
    mapping = conversation["mapping"]
    current_node = conversation.get("current_node")
    node_ids, active_ids = ordered_node_ids(mapping, current_node)
    nodes: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    for node_id in node_ids:
        node = mapping[node_id]
        message = node.get("message")
        exported: dict[str, Any] = {
            "node_id": node_id,
            "parent": node.get("parent"),
            "children": node.get("children", []),
            "on_active_branch": node_id in active_ids,
            "message": message,
        }
        if isinstance(message, dict):
            author = message.get("author") or {}
            role = author.get("role", "unknown")
            content = message.get("content")
            content_type = (
                content.get("content_type", "unknown")
                if isinstance(content, dict)
                else type(content).__name__
            )
            counts[content_type] = counts.get(content_type, 0) + 1
            exported["role"] = role
            exported["content_type"] = content_type
            exported["text"] = message_text(content)
        nodes.append(exported)

    conversation_metadata = {
        key: value
        for key, value in conversation.items()
        if key != "mapping"
    }
    return {
        "schema": "chatgpt-share-export/v1",
        "source_url": source_url,
        "share_id": share_id,
        "extracted_at": datetime.now(timezone.utc).isoformat(),
        "title": conversation.get("title"),
        "conversation_id": conversation.get("conversation_id"),
        "current_node": current_node,
        "message_count": sum(node.get("message") is not None for node in mapping.values()),
        "node_count": len(mapping),
        "content_type_counts": dict(sorted(counts.items())),
        "conversation_metadata": conversation_metadata,
        "nodes": nodes,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("share_url", help="public https://chatgpt.com/share/... URL")
    parser.add_argument(
        "-o", "--output", type=Path, required=True, help="destination JSON path"
    )
    parser.add_argument(
        "--html",
        type=Path,
        help="read an already-downloaded share page instead of using the network",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    try:
        source_url, share_id = canonical_share_url(args.share_url)
        html = (
            args.html.read_text(encoding="utf-8")
            if args.html
            else download_html(source_url)
        )
        flattened = extract_flattened_value(html)
        decoded = FlattenedDecoder(flattened).decode()
        conversation = find_conversation(decoded)
        exported = build_export(conversation, source_url, share_id)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(exported, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    thinking_count = sum(
        count
        for content_type, count in exported["content_type_counts"].items()
        if content_type in {"thoughts", "reasoning", "reasoning_recap"}
        or "thought" in content_type
    )
    print(
        f"Wrote {args.output}: {exported['message_count']} messages, "
        f"{thinking_count} explicit thinking/reasoning messages."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
