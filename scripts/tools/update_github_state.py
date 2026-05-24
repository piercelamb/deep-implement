#!/usr/bin/env python3
"""Update GitHub state in session config.

Persists issue number and per-section PR info for resume support.

Usage:
    # Store tracking issue number
    uv run {plugin_root}/scripts/tools/update_github_state.py \
        --state-dir "{state_dir}" \
        --issue-number 42

    # Store per-section PR info
    uv run {plugin_root}/scripts/tools/update_github_state.py \
        --state-dir "{state_dir}" \
        --section "section-01-foundation" \
        --pr-number 43 \
        --pr-url "https://github.com/owner/repo/pull/43"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.lib.config import load_session_config, save_session_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Update GitHub state in session config")
    parser.add_argument("--state-dir", required=True, help="Path to state directory")
    parser.add_argument("--issue-number", type=int, help="Tracking issue number")
    parser.add_argument("--section", help="Section name (required with --pr-number)")
    parser.add_argument("--pr-number", type=int, help="PR number for section")
    parser.add_argument("--pr-url", help="PR URL for section")
    args = parser.parse_args()

    state_dir = Path(args.state_dir)

    config = load_session_config(state_dir)
    if config is None:
        print(f"Error: No config found in {state_dir}")
        return 1

    if "github" not in config:
        config["github"] = {
            "enabled": False,
            "owner_repo": None,
            "base_branch": None,
            "issue_number": None,
            "section_prs": {},
        }

    if args.issue_number is not None:
        config["github"]["issue_number"] = args.issue_number
        config["github"]["enabled"] = True
        save_session_config(state_dir, config)
        print(f"Updated issue_number={args.issue_number}")
        return 0

    if args.pr_number is not None:
        if not args.section:
            print("Error: --section is required with --pr-number")
            return 1
        if "section_prs" not in config["github"]:
            config["github"]["section_prs"] = {}
        config["github"]["section_prs"][args.section] = {
            "number": args.pr_number,
            "url": args.pr_url or "",
        }
        save_session_config(state_dir, config)
        print(f"Updated {args.section}: pr_number={args.pr_number}")
        return 0

    print("Error: Must provide --issue-number or --pr-number")
    return 1


if __name__ == "__main__":
    sys.exit(main())
