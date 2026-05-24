#!/usr/bin/env python3

"""
Publish Markdown documentation to WordPress Pages using the WordPress REST API.

What this script does:
- Reads docs/wp-pages.yml
- Converts Markdown files to HTML
- Authenticates to WordPress using an Application Password
- Searches for existing WordPress Pages by slug
- Updates the page if the slug exists
- Creates the page if the slug does not exist
- Defaults to draft status

Required environment variables:
- WP_BASE_URL
- WP_USERNAME
- WP_APP_PASSWORD

Optional environment variable:
- WP_STATUS defaults to draft

Example:
    python scripts/publish_wp_pages.py --dry-run
    python scripts/publish_wp_pages.py
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any

import markdown
import requests
import yaml
from requests.auth import HTTPBasicAuth


ALLOWED_STATUSES = {"draft", "publish", "pending", "private"}
SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class PublishError(Exception):
    """Used for clean script error messages."""


def require_env(name: str) -> str:
    value = os.getenv(name)

    if not value:
        raise PublishError(f"Missing required environment variable: {name}")

    return value.strip()


def load_mapping(mapping_path: Path) -> list[dict[str, Any]]:
    if not mapping_path.exists():
        raise PublishError(f"Mapping file not found: {mapping_path}")

    with mapping_path.open("r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    if not isinstance(data, dict):
        raise PublishError("Mapping file must be a YAML object.")

    pages = data.get("pages")

    if not isinstance(pages, list):
        raise PublishError("Mapping file must contain a top-level 'pages' list.")

    if not pages:
        raise PublishError("Mapping file contains no pages.")

    return pages


def validate_page_entry(entry: dict[str, Any], repo_root: Path) -> tuple[Path, str, str]:
    if not isinstance(entry, dict):
        raise PublishError(f"Invalid page entry: {entry}")

    source = entry.get("source")
    title = entry.get("title")
    slug = entry.get("slug")

    if not source or not isinstance(source, str):
        raise PublishError(f"Page entry is missing a valid 'source': {entry}")

    if not title or not isinstance(title, str):
        raise PublishError(f"Page entry is missing a valid 'title': {entry}")

    if not slug or not isinstance(slug, str):
        raise PublishError(f"Page entry is missing a valid 'slug': {entry}")

    slug = slug.strip()
    title = title.strip()
    source_path = repo_root / source

    if not SLUG_PATTERN.match(slug):
        raise PublishError(
            f"Invalid slug '{slug}'. Use lowercase letters, numbers, and hyphens only."
        )

    if not source_path.exists():
        raise PublishError(f"Markdown source file not found: {source_path}")

    if source_path.suffix.lower() != ".md":
        raise PublishError(f"Source file must end in .md: {source_path}")

    return source_path, title, slug


def convert_markdown_to_html(markdown_path: Path) -> str:
    markdown_text = markdown_path.read_text(encoding="utf-8")

    html = markdown.markdown(
        markdown_text,
        extensions=[
            "extra",
            "tables",
            "fenced_code",
            "sane_lists",
            "toc",
        ],
        output_format="html5",
    )

    if not html.strip():
        raise PublishError(f"Converted HTML is empty for file: {markdown_path}")

    return html


def wp_request(
    method: str,
    url: str,
    auth: HTTPBasicAuth,
    **kwargs: Any,
) -> requests.Response:
    try:
        response = requests.request(
            method=method,
            url=url,
            auth=auth,
            timeout=30,
            **kwargs,
        )
    except requests.RequestException as exc:
        raise PublishError(f"Request failed: {exc}") from exc

    if not response.ok:
        preview = response.text[:1000]
        raise PublishError(
            f"WordPress API error: {response.status_code} {response.reason}\n"
            f"URL: {url}\n"
            f"Response preview:\n{preview}"
        )

    return response


def find_page_by_slug(
    api_pages_url: str,
    slug: str,
    auth: HTTPBasicAuth,
) -> dict[str, Any] | None:
    response = wp_request(
        method="GET",
        url=api_pages_url,
        auth=auth,
        params={
            "slug": slug,
            "status": "any",
            "context": "edit",
            "per_page": 100,
        },
    )

    pages = response.json()

    if not isinstance(pages, list):
        raise PublishError(f"Unexpected WordPress response while searching slug: {slug}")

    exact_matches = [page for page in pages if page.get("slug") == slug]

    if len(exact_matches) > 1:
        ids = [str(page.get("id")) for page in exact_matches]
        raise PublishError(
            f"Duplicate WordPress Pages found for slug '{slug}'. "
            f"Page IDs: {', '.join(ids)}. Resolve duplicates manually before publishing."
        )

    if not exact_matches:
        return None

    return exact_matches[0]


def create_or_update_page(
    api_pages_url: str,
    auth: HTTPBasicAuth,
    title: str,
    slug: str,
    html: str,
    status: str,
    dry_run: bool,
) -> str:
    existing_page = find_page_by_slug(
        api_pages_url=api_pages_url,
        slug=slug,
        auth=auth,
    )

    payload = {
        "title": title,
        "slug": slug,
        "content": html,
        "status": status,
    }

    if existing_page:
        page_id = existing_page.get("id")

        if not page_id:
            raise PublishError(f"Existing page for slug '{slug}' has no page ID.")

        update_url = f"{api_pages_url}/{page_id}"

        if dry_run:
            return f"DRY RUN: would update '{title}' at /{slug}/ using page ID {page_id}"

        wp_request(
            method="POST",
            url=update_url,
            auth=auth,
            json=payload,
        )

        return f"Updated '{title}' at /{slug}/ using page ID {page_id}"

    if dry_run:
        return f"DRY RUN: would create '{title}' at /{slug}/"

    response = wp_request(
        method="POST",
        url=api_pages_url,
        auth=auth,
        json=payload,
    )

    created_page = response.json()
    page_id = created_page.get("id", "unknown")

    return f"Created '{title}' at /{slug}/ using page ID {page_id}"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Publish Markdown docs to WordPress Pages."
    )

    parser.add_argument(
        "--mapping",
        default="docs/wp-pages.yml",
        help="Path to the WordPress page mapping file.",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate files and show intended changes without publishing.",
    )

    args = parser.parse_args()

    repo_root = Path.cwd()
    mapping_path = repo_root / args.mapping

    try:
        wp_base_url = require_env("WP_BASE_URL").rstrip("/")
        wp_username = require_env("WP_USERNAME")
        wp_app_password = require_env("WP_APP_PASSWORD").replace(" ", "")

        wp_status = os.getenv("WP_STATUS", "draft").strip().lower()

        if wp_status not in ALLOWED_STATUSES:
            allowed = ", ".join(sorted(ALLOWED_STATUSES))
            raise PublishError(
                f"Invalid WP_STATUS '{wp_status}'. Allowed values are: {allowed}"
            )

        api_pages_url = f"{wp_base_url}/index.php?rest_route=/wp/v2/pages"
        auth = HTTPBasicAuth(wp_username, wp_app_password)

        pages = load_mapping(mapping_path)

        seen_slugs: set[str] = set()
        seen_sources: set[str] = set()

        print(f"WordPress base URL: {wp_base_url}")
        print(f"WordPress status: {wp_status}")
        print(f"Mapping file: {mapping_path}")
        print(f"Dry run: {args.dry_run}")
        print()

        for entry in pages:
            source_path, title, slug = validate_page_entry(entry, repo_root)

            source_key = str(source_path.resolve())

            if slug in seen_slugs:
                raise PublishError(f"Duplicate slug in mapping file: {slug}")

            if source_key in seen_sources:
                raise PublishError(f"Duplicate source file in mapping file: {source_path}")

            seen_slugs.add(slug)
            seen_sources.add(source_key)

            html = convert_markdown_to_html(source_path)

            result = create_or_update_page(
                api_pages_url=api_pages_url,
                auth=auth,
                title=title,
                slug=slug,
                html=html,
                status=wp_status,
                dry_run=args.dry_run,
            )

            print(result)

        print()
        print("Done.")
        return 0

    except PublishError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())