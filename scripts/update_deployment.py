"""Update Study Planner image references in the kube repository."""
from __future__ import annotations

import argparse
from pathlib import Path
import re

IMAGE_RE = re.compile(
    r"(?P<indent>\s+)(?P<key>api|web):\n"
    r"(?P<repo_indent>\s+)image:\n"
    r"(?P<repo_line>\s+)repository: (?P<repository>[^\n]+)\n"
    r"(?P<tag_line>\s+)tag: (?P<reference>[^\n]+)"
)


def update_helmrelease(text: str, tag: str, api_digest: str, web_digest: str) -> str:
    """Replace both app image refs, preserving YAML layout and repositories."""
    replacements = {
        "api": f"{tag}@{api_digest}",
        "web": f"{tag}@{web_digest}",
    }
    seen: set[str] = set()

    def replace(match: re.Match[str]) -> str:
        key = match.group("key")
        if key not in replacements:
            return match.group(0)
        seen.add(key)
        return match.group(0).replace(
            f"tag: {match.group('reference')}", f"tag: {replacements[key]}"
        )

    updated = IMAGE_RE.sub(replace, text)
    missing = {"api", "web"} - seen
    if missing:
        raise ValueError(f"missing image entries: {', '.join(sorted(missing))}")
    return updated


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--file", action="append", type=Path, required=True)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--api-digest", required=True)
    parser.add_argument("--web-digest", required=True)
    args = parser.parse_args()
    for path in args.file:
        original = path.read_text()
        updated = update_helmrelease(original, args.tag, args.api_digest, args.web_digest)
        path.write_text(updated)
        print(path)


if __name__ == "__main__":
    main()
