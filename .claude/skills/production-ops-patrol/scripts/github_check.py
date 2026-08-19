#!/usr/bin/env python3
"""
github_check.py — GitHub Issue association for patrol fingerprints.

Searches existing open issues for a fingerprint hash in the body,
so that the same recurring bug gets linked to the same issue.

Usage:
    python github_check.py --fingerprint <hash> --error-type <ExceptionType>
    python github_check.py --fingerprint <hash> --error-type <ExceptionType> --repo owner/repo

Output: JSON with 'found', 'issue_number', 'issue_url', 'issue_title'.
"""

import argparse
import json
import subprocess


def search_issues(fingerprint: str, error_type: str, repo: str | None = None) -> dict:
    """Search GitHub issues for a fingerprint hash."""
    cmd = ["gh", "issue", "list", "--state", "open", "--limit", "20",
           "--json", "number,title,url,body,labels"]
    if repo:
        cmd.extend(["--repo", repo])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {
                "found": False,
                "error": f"gh CLI failed: {result.stderr.strip()}",
                "fingerprint": fingerprint,
            }

        issues = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        return {"found": False, "error": str(e), "fingerprint": fingerprint}

    # Look for fingerprint match in issue body
    for issue in issues:
        body = issue.get("body", "") or ""
        if fingerprint in body:
            return {
                "found": True,
                "issue_number": issue["number"],
                "issue_url": issue["url"],
                "issue_title": issue["title"],
                "fingerprint": fingerprint,
            }

    # Also search by error type keyword if no fingerprint match
    if error_type:
        cmd_search = ["gh", "issue", "list", "--state", "open", "--limit", "10",
                      "--json", "number,title,url,body",
                      "--search", f"{error_type} in:title"]
        if repo:
            cmd_search.extend(["--repo", repo])

        try:
            result2 = subprocess.run(cmd_search, capture_output=True, text=True, timeout=30)
            if result2.returncode == 0:
                issues2 = json.loads(result2.stdout)
                if issues2:
                    return {
                        "found": True,
                        "issue_number": issues2[0]["number"],
                        "issue_url": issues2[0]["url"],
                        "issue_title": issues2[0]["title"],
                        "match_type": "error_type_keyword",
                        "fingerprint": fingerprint,
                        "note": "Matched by error type, not fingerprint — may need verification",
                    }
        except (subprocess.TimeoutExpired, json.JSONDecodeError):
            pass

    return {"found": False, "fingerprint": fingerprint}


def main():
    parser = argparse.ArgumentParser(description="GitHub Issue fingerprint lookup")
    parser.add_argument("--fingerprint", required=True, help="Exception fingerprint hash")
    parser.add_argument("--error-type", default="", help="Exception type for keyword search")
    parser.add_argument("--repo", default=None, help="GitHub repo (owner/name). Defaults to current repo.")
    args = parser.parse_args()

    result = search_issues(args.fingerprint, args.error_type, args.repo)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
