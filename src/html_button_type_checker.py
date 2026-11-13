#!/usr/bin/env python3
"""Check <button> tags in HTML files carry a type attribute.

Run: python3 src/html_button_type_checker.py page.html
     python3 src/html_button_type_checker.py site/
     python3 src/html_button_type_checker.py --stdin < page.html

A <button> with no type defaults to submit, so a button meant
to open a dialog or clear a field silently submits the form
instead — a real bug that ships constantly because nothing
stops it. The fix is one word per button — type="button",
type="submit", or type="reset" — but nothing stops you
shipping a page without it. This tool finds every <button>
missing a type, or carrying one that is empty or not one of
the three valid values, before the page ships, instead of
after a reader clicks a button and the form submits by
surprise.

It reads one or more HTML files, records every <button> tag
with its line number and its type attribute, and reports
each button that is missing a type or has an invalid one,
with the file and the line. It exits 1 when any button
fails, so it can fail a CI run. A file where every button
carries a valid type exits 0.

A type counts as missing when it is absent, and as invalid
when it is empty or not one of button, submit, or reset:
type="" and type="foo" both fail, because both leave the
browser treating the button as a submit button. The check
is case-insensitive — TYPE="BUTTON" passes — and single-
quoted, double-quoted, and unquoted values are all found.
A <button> inside an HTML comment does not count, and
neither does text inside <script> or <style> blocks: only
real buttons count. Buttons inside a form and buttons
outside one are checked the same way.

It never rewrites a file, never touches the network, and
reads only the files and folders you point it at.
"""

import argparse
import fnmatch
import json
import os
import sys
from html.parser import HTMLParser
from pathlib import Path

__version__ = "1.0.0"

HTML_EXTENSIONS = {".html", ".htm"}
VALID_TYPES = {"button", "submit", "reset"}


class _ButtonCollector(HTMLParser):
    """Collect (line, text, type, problem) for every <button> tag."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.buttons = []
        self._open = None

    def handle_starttag(self, tag, attrs):
        if tag == "button" and self._open is None:
            line, _ = self.getpos()
            values = {name: value for name, value in attrs}
            self._open = {"line": line, "text": "",
                          "has_type": "type" in values,
                          "type": values.get("type")}
        elif self._open is not None and tag == "button":
            # A button inside a button is not valid HTML; the
            # parser still reports it, so close the outer one
            # first and start a fresh record for the inner one.
            self._finish_open()
            line, _ = self.getpos()
            values = {name: value for name, value in attrs}
            self._open = {"line": line, "text": "",
                          "has_type": "type" in values,
                          "type": values.get("type")}

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag == "button":
            self._finish_open()

    def handle_endtag(self, tag):
        if tag == "button" and self._open is not None:
            self._finish_open()

    def handle_data(self, data):
        if self._open is not None:
            self._open["text"] += data

    def close(self):
        super().close()
        if self._open is not None:
            self._finish_open()

    def _finish_open(self):
        record = self._open
        self._open = None
        text = " ".join(record["text"].split())
        if len(text) > 40:
            text = text[:37] + "..."
        value = record["type"]
        if not record["has_type"]:
            problem = "missing"
        elif value is None or value.strip() == "":
            problem = "empty"
        elif value.strip().lower() not in VALID_TYPES:
            problem = "invalid"
        else:
            problem = None
        self.buttons.append(
            {"line": record["line"], "text": text or None,
             "type": value, "problem": problem})


def find_bad_buttons(text):
    """Return a list of <button> tags missing or misusing type.

    Each entry is {"line": int, "text": str or None,
    "type": str or None, "problem": "missing", "empty", or
    "invalid"}. Entries are in document order. Buttons
    carrying a valid type are not listed.
    """
    collector = _ButtonCollector()
    collector.feed(text)
    collector.close()
    return [b for b in collector.buttons if b["problem"]]


def check_text(text, path):
    """Check one document's text. Returns (bad buttons, error)."""
    try:
        return find_bad_buttons(text), None
    except Exception as exc:  # a malformed document must fail, not crash
        return [], "could not parse: %s" % exc


def check_file(path):
    """Check one file. Returns (bad buttons, error)."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return [], "not valid UTF-8"
    except OSError as exc:
        return [], str(exc)
    return check_text(text, str(path))


def _is_html_file(path):
    return Path(path).suffix.lower() in HTML_EXTENSIONS


def collect_files(paths, recursive=True, exclude=None):
    """Expand CLI paths into a sorted list of HTML files to check.

    A file given directly is always checked, whatever its name. A
    folder is walked for .html/.htm files. .git folders are never
    walked, and directory links are never followed.
    """
    exclude = exclude or []
    found = []
    for raw in paths:
        path = Path(raw)
        if path.is_file():
            found.append(str(path))
        elif path.is_dir():
            for root, dirs, files in os.walk(path, followlinks=False):
                dirs[:] = [
                    d for d in dirs
                    if d != ".git"
                    and not any(fnmatch.fnmatch(d, pat) for pat in exclude)
                ]
                for name in files:
                    candidate = Path(root) / name
                    if not _is_html_file(candidate):
                        continue
                    if any(
                        fnmatch.fnmatch(str(candidate), pat)
                        or fnmatch.fnmatch(name, pat)
                        for pat in exclude
                    ):
                        continue
                    found.append(str(candidate))
                if not recursive:
                    break
        else:
            raise FileNotFoundError("no such file or folder: %s" % raw)
    seen = set()
    unique = []
    for item in found:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return sorted(unique)


def format_problem(path, button):
    """One human-readable line for one button failing the check."""
    if button["text"]:
        label = '<button "%s">' % button["text"]
    else:
        label = "<button>"
    if button["problem"] == "missing":
        what = "is missing type"
    elif button["problem"] == "empty":
        what = "has an empty type"
    else:
        what = 'has invalid type "%s"' % button["type"]
    return "FAIL %s: %s line %d %s" % (path, label, button["line"], what)


def run(paths, recursive=True, exclude=None, as_json=False):
    """Check paths, print the report, return the exit code."""
    try:
        files = collect_files(paths, recursive=recursive, exclude=exclude)
    except FileNotFoundError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 2
    if not files:
        print("error: no HTML files found", file=sys.stderr)
        return 2
    results = []
    problems = 0
    files_with_problems = 0
    for path in files:
        bad, error = check_file(path)
        count = len(bad) + (1 if error else 0)
        if count:
            problems += count
            files_with_problems += 1
        results.append({"path": path, "buttons": bad, "error": error})
    if as_json:
        print(json.dumps(
            {"files": results, "checked": len(files),
             "problems": problems},
            indent=2))
    else:
        for result in results:
            if result["error"]:
                print("FAIL %s: %s" % (result["path"], result["error"]))
            for button in result["buttons"]:
                print(format_problem(result["path"], button))
        if problems:
            print("Checked %d file(s), %d problem(s) in %d file(s)."
                  % (len(files), problems, files_with_problems))
        else:
            print("OK — %d file(s) checked, every button has a valid type."
                  % len(files))
    return 1 if problems else 0


def run_stdin(as_json=False):
    """Check one HTML document read from standard input."""
    text = sys.stdin.read()
    bad, error = check_text(text, "<stdin>")
    problems = len(bad) + (1 if error else 0)
    if as_json:
        print(json.dumps(
            {"files": [{"path": "<stdin>", "buttons": bad,
                        "error": error}],
             "checked": 1, "problems": problems},
            indent=2))
    else:
        if error:
            print("FAIL <stdin>: %s" % error)
        for button in bad:
            print(format_problem("<stdin>", button))
        if problems:
            print("Checked 1 file(s), %d problem(s) in 1 file(s)." % problems)
        else:
            print("OK — 1 file(s) checked, every button has a valid type.")
    return 1 if problems else 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="html_button_type_checker",
        description="Check <button> tags in HTML files carry a valid "
                    "type attribute, fail CI when one is missing.")
    parser.add_argument("paths", nargs="*", help="HTML files or folders")
    parser.add_argument("--no-recursive", action="store_true",
                        help="do not walk into subfolders")
    parser.add_argument("--exclude", action="append", default=[],
                        help="skip files or folders matching this pattern "
                             "(repeatable)")
    parser.add_argument("--json", action="store_true",
                        help="print the result as JSON")
    parser.add_argument("--stdin", action="store_true",
                        help="check one HTML document from standard input")
    parser.add_argument("--version", action="version",
                        version="%(prog)s " + __version__)
    args = parser.parse_args(argv)
    if args.stdin:
        if args.paths:
            parser.error("--stdin takes no file or folder arguments")
        return run_stdin(as_json=args.json)
    if not args.paths:
        parser.error("give at least one HTML file or folder")
    return run(args.paths, recursive=not args.no_recursive,
               exclude=args.exclude, as_json=args.json)


if __name__ == "__main__":
    sys.exit(main())
