#!/usr/bin/env python3
"""Set, change or clear the dashboard password.

    ./run.sh set-password          # prompt, hidden input
    ./run.sh set-password --clear  # back to token-only, localhost model

With a password set, every dashboard API route needs a login — reads
included — because a tunnel makes remote requests look local and the
loopback bind stops proving anything.
"""

import argparse
import getpass
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import auth  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Set the dashboard password")
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Remove the password and return to the localhost/token model",
    )
    args = parser.parse_args()

    if args.clear:
        if auth.clear_password():
            print("Password removed. Reads are open on localhost again, and")
            print("writes fall back to the bearer token in data/dashboard.token.")
        else:
            print("No password was set.")
        return 0

    if auth.password_is_set():
        print("A password is already set. Entering a new one replaces it.")

    first = getpass.getpass("New dashboard password: ")
    second = getpass.getpass("Repeat it: ")
    if first != second:
        print("Those do not match. Nothing changed.", file=sys.stderr)
        return 1

    try:
        auth.set_password(first)
    except ValueError as e:
        print(f"{e} Nothing changed.", file=sys.stderr)
        return 1

    print(f"Saved to {auth.AUTH_FILE} (owner-only).")
    print("Restart the dashboard, then log in from any device on your tailnet.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
