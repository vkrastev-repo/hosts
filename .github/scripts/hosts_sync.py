#!/usr/bin/env python3
"""
Helper for keeping a StevenBlack/hosts fork in sync, touching only the `hosts` file.

Usage:
  hosts_sync.py merge CURRENT UPSTREAM OUT
      Write OUT = UPSTREAM, but keep the "custom host records" block from CURRENT
      (your own additions between the two marker lines are preserved).

  hosts_sync.py check FILE REPORT
      Exit 1 if any domain in FILE points to something other than 0.0.0.0.
      A human-readable report (used as the email body) is written to REPORT.
"""
import sys

CUSTOM_START = "# Custom host records are listed here."
CUSTOM_END = "# End of custom host records."

# Standard header entries at the top of the StevenBlack file that legitimately
# point to loopback/broadcast/IPv6 addresses. Everything else must be 0.0.0.0.
ALLOWED = {
    ("127.0.0.1", "localhost"),
    ("127.0.0.1", "localhost.localdomain"),
    ("127.0.0.1", "local"),
    ("255.255.255.255", "broadcasthost"),
    ("::1", "localhost"),
    ("::1", "ip6-localhost"),
    ("::1", "ip6-loopback"),
    ("fe80::1%lo0", "localhost"),
    ("ff00::0", "ip6-localnet"),
    ("ff00::0", "ip6-mcastprefix"),
    ("ff02::1", "ip6-allnodes"),
    ("ff02::2", "ip6-allrouters"),
    ("ff02::3", "ip6-allhosts"),
}

MAX_LINES_IN_REPORT = 300


def read_lines(path):
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().splitlines()


def find_block(lines):
    """Return (start, end) indexes of the custom-records marker lines, or None."""
    start = end = None
    for i, line in enumerate(lines):
        s = line.strip()
        if start is None and s == CUSTOM_START:
            start = i
        elif start is not None and s == CUSTOM_END:
            end = i
            break
    return (start, end) if start is not None and end is not None else None


def merge(current_path, upstream_path, out_path):
    current = read_lines(current_path)
    upstream = read_lines(upstream_path)
    cur_block = find_block(current)
    up_block = find_block(upstream)

    custom = current[cur_block[0] + 1 : cur_block[1]] if cur_block else []
    has_custom = any(l.strip() for l in custom)

    if up_block:
        out = upstream[: up_block[0] + 1] + custom + upstream[up_block[1] :]
    elif has_custom:
        print("::warning::Upstream file has no custom-records markers; "
              "appending your custom records at the end.")
        out = upstream + ["", CUSTOM_START] + custom + [CUSTOM_END]
    else:
        out = upstream

    with open(out_path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(out) + "\n")
    print(f"Merged: {len(upstream)} upstream lines, "
          f"{sum(1 for l in custom if l.strip())} custom lines kept.")


def check(path, report_path):
    problems = []
    domains = 0
    for n, raw in enumerate(read_lines(path), 1):
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = line.split()
        ip, names = parts[0], parts[1:]
        if not names:
            problems.append((n, raw.strip(), "malformed line (no IP/hostname pair)"))
            continue
        domains += len(names)
        if ip == "0.0.0.0":
            continue
        if all((ip, h) in ALLOWED for h in names):
            continue
        problems.append((n, raw.strip(), f"points to {ip}"))

    if not problems:
        msg = f"OK: all {domains} domain entries point to 0.0.0.0 (header entries excepted)."
        print(msg)
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(msg + "\n")
        return 0

    lines = [
        f"The upstream hosts file was NOT merged: {len(problems)} line(s) "
        f"point somewhere other than 0.0.0.0.",
        "",
    ]
    for n, text, why in problems[:MAX_LINES_IN_REPORT]:
        lines.append(f"line {n}: {text}    <-- {why}")
    if len(problems) > MAX_LINES_IN_REPORT:
        lines.append(f"... and {len(problems) - MAX_LINES_IN_REPORT} more.")
    report = "\n".join(lines) + "\n"
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(report)
    print(f"::error::{len(problems)} non-0.0.0.0 entries found; merge blocked.")
    return 1


if __name__ == "__main__":
    if len(sys.argv) == 5 and sys.argv[1] == "merge":
        merge(*sys.argv[2:5])
    elif len(sys.argv) == 4 and sys.argv[1] == "check":
        sys.exit(check(sys.argv[2], sys.argv[3]))
    else:
        print(__doc__)
        sys.exit(2)
