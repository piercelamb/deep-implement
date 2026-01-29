#!/usr/bin/env python3
"""Update section state after successful commit.

Usage:
    uv run {plugin_root}/scripts/tools/update_section_state.py \
        --state-dir "{state_dir}" \
        --section "section-01-foundation" \
        --commit-hash "abc1234"
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.lib.config import load_session_config, save_session_config


def main() -> int:
    parser = argparse.ArgumentParser(description="Update section state")
    parser.add_argument("--state-dir", required=True, help="Path to state directory")
    parser.add_argument("--section", required=True, help="Section name")
    parser.add_argument("--commit-hash", required=True, help="Git commit hash")
    parser.add_argument("--review-file", help="Review file name (optional)")
    args = parser.parse_args()

    state_dir = Path(args.state_dir)

    # Load existing config
    config = load_session_config(state_dir)
    if config is None:
        print(f"Error: No config found in {state_dir}")
        return 1

    # Update sections_state
    if "sections_state" not in config:
        config["sections_state"] = {}

    config["sections_state"][args.section] = {
        "status": "complete",
        "commit_hash": args.commit_hash,
    }

    if args.review_file:
        config["sections_state"][args.section]["review_file"] = args.review_file

    # Save
    save_session_config(state_dir, config)

    print(f"Updated {args.section}: commit_hash={args.commit_hash}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
