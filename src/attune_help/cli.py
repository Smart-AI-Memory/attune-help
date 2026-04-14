"""attune-help CLI.

Minimal user-facing CLI wrapped around :class:`HelpEngine`.
Exposes the handful of operations most useful from a
terminal:

    attune-help lookup <topic>
    attune-help list [--type <kind>] [--limit N]
    attune-help search <query> [--limit N]
    attune-help simpler <topic>

The MCP server (``attune-help-mcp``) is the equivalent
surface for agent/IDE clients. Both wrap the same public
``HelpEngine`` API — the CLI exists so terminal users have
a first-class entry point without standing up an MCP
client.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from attune_help import HelpEngine, __version__

_RENDERERS = ("plain", "cli", "claude_code", "marketplace", "json")


def _build_parser() -> argparse.ArgumentParser:
    """Build the top-level argument parser."""
    parser = argparse.ArgumentParser(
        prog="attune-help",
        description=("Look up, list, and search progressive-depth " "help templates."),
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"attune-help {__version__}",
    )
    parser.add_argument(
        "--template-dir",
        help=("Override template directory. Defaults to " "bundled templates."),
    )
    parser.add_argument(
        "--renderer",
        default="plain",
        choices=_RENDERERS,
        help="Output renderer. Default: plain.",
    )

    sub = parser.add_subparsers(dest="command", required=True)

    p_lookup = sub.add_parser(
        "lookup",
        help="Look up a topic with progressive depth.",
    )
    p_lookup.add_argument("topic")

    p_list = sub.add_parser(
        "list",
        help="List available topic slugs.",
    )
    p_list.add_argument(
        "--type",
        dest="type_filter",
        help=("Filter by template type (e.g. concept, task, " "reference)."),
    )
    p_list.add_argument(
        "--limit",
        type=int,
        help="Maximum number of topics to show.",
    )

    p_search = sub.add_parser(
        "search",
        help="Fuzzy-search topic slugs.",
    )
    p_search.add_argument("query")
    p_search.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Maximum results. Default: 10.",
    )

    p_simpler = sub.add_parser(
        "simpler",
        help=("Step the topic's progressive depth back one " "level."),
    )
    p_simpler.add_argument("topic")

    return parser


def _engine(args: argparse.Namespace) -> HelpEngine:
    """Build a HelpEngine from parsed CLI args."""
    return HelpEngine(
        template_dir=args.template_dir,
        renderer=args.renderer,
    )


def _cmd_lookup(args: argparse.Namespace) -> int:
    engine = _engine(args)
    result = engine.lookup(args.topic)
    if result is None:
        # Miss: show "did you mean" suggestions on stderr and
        # return nonzero so scripts can react.
        suggestions = engine.suggest(args.topic)
        if suggestions:
            joined = ", ".join(suggestions)
            print(
                f"No help for {args.topic!r}. Did you mean: {joined}?",
                file=sys.stderr,
            )
        else:
            print(f"No help for {args.topic!r}.", file=sys.stderr)
        return 1
    print(result)
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    engine = _engine(args)
    topics = engine.list_topics(
        type_filter=args.type_filter,
        limit=args.limit,
    )
    if not topics:
        print("No topics found.", file=sys.stderr)
        return 1
    for topic in topics:
        print(topic)
    return 0


def _cmd_search(args: argparse.Namespace) -> int:
    engine = _engine(args)
    hits = engine.search(args.query, limit=args.limit)
    if not hits:
        print(f"No matches for {args.query!r}.", file=sys.stderr)
        return 1
    for slug, score in hits:
        print(f"{slug}\t{score:.2f}")
    return 0


def _cmd_simpler(args: argparse.Namespace) -> int:
    engine = _engine(args)
    result = engine.simpler(args.topic)
    if result is None:
        print(f"No help for {args.topic!r}.", file=sys.stderr)
        return 1
    print(result)
    return 0


_DISPATCH = {
    "lookup": _cmd_lookup,
    "list": _cmd_list,
    "search": _cmd_search,
    "simpler": _cmd_simpler,
}


def main(argv: Sequence[str] | None = None) -> int:
    """Entry point for the ``attune-help`` console script."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    handler = _DISPATCH[args.command]
    try:
        return handler(args)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
