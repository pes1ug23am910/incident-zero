"""Build, inspect and explain the local hint index."""
import argparse
import json
from pathlib import Path

from .index import KnowledgeIndex


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, help="SQLite index path")
    parser.add_argument("--root", type=Path, help="Repository/data root")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("build", help="Index runbooks, catalogue and stored incident summaries")
    search = commands.add_parser("search", help="Print ranked snippets and provenance as JSON")
    search.add_argument("query")
    search.add_argument("--section", help="Restrict runbook hits, e.g. remediation")
    explain = commands.add_parser("explain", help="Print the citations retained in a report")
    explain.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    index = KnowledgeIndex(args.index, root=args.root)
    if args.command == "build":
        result = index.build()
    elif args.command == "search":
        result = index.search(args.query, section=args.section)
    else:
        result = index.explain(json.loads(args.report.read_text(encoding="utf-8")))
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
