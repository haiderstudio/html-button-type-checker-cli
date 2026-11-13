# html-button-type-checker-cli

Check every `<button>` in HTML files carries a valid `type`, fail CI when one is missing.

[![CI](https://github.com/haiderstudio/html-button-type-checker-cli/actions/workflows/ci.yml/badge.svg)](https://github.com/haiderstudio/html-button-type-checker-cli/actions/workflows/ci.yml) [![Licence: MIT](https://img.shields.io/badge/Licence-MIT-yellow.svg)](LICENSE)

## What it does

`html_button_type_checker` reads HTML files and finds
every `<button>` tag missing its `type` attribute — or
carrying one that is empty or not one of `button`,
`submit`, or `reset` — and reports each one with the
file, the button, and the line number. It exits 1 when
any button fails, so it can fail a CI run. A file where
every button carries a valid type exits 0.

- A `<button>` with no `type` defaults to `submit`, so a
  button meant to open a dialog or clear a field
  silently submits the form instead. That is a real bug
  that ships constantly, because nothing stops it. The
  fix is one word per button, but nothing stops you
  shipping a page without it — this catches it before
  the page ships.
- A type counts as missing when it is absent, and as
  invalid when it is empty or not one of the three valid
  values: `type=""` and `type="foo"` both fail, because
  both leave the browser treating the button as a
  submit button. A bare `type` with no value counts as
  empty, for the same reason.
- The check is case-insensitive — `TYPE="BUTTON"` and
  `type="Submit"` both pass — and single-quoted,
  double-quoted, and unquoted values are all found.
  Buttons inside a form and buttons outside one are
  checked the same way: a button outside a form still
  needs a type, because it may end up inside one later.
- A `<button>` inside an HTML comment does not count,
  and neither does text inside `<script>` or `<style>`
  blocks: only real buttons count. The button's own
  text is shown in the report, so you can tell one
  button from another on the same line.
- A file given directly on the command line is always
  checked, whatever its name. A folder is walked for
  `.html` and `.htm` files, recursively by default
  (`--no-recursive` stops at the top level). `.git`
  folders are never walked, and directory links are never
  followed.
- `--json` prints the result as JSON (the human-readable
  lines go to standard error), and `--stdin` checks one
  HTML document read from standard input.

## Who it is for

Anyone who owns a website with a form and does not want
a click to submit it by surprise — front-end
developers, teams that review each other's templates,
and anyone whose pages carry buttons added by hand or
by a CMS.

## What it does NOT do

- It does not check `<input type="button">`. That is a
  different element: an input's type is required by the
  element itself, and a missing one is a different bug.
  This tool checks `<button>` elements only.
- It does not check form labels. That is repo #85,
  html-label-checker-cli, which checks labels only —
  button types are a different check on the same pages.
- It does not check whether a `submit` button is the
  right choice for the job — only that the type is
  present and valid. Whether a button should submit or
  not is a design decision, not something a checker can
  decide.
- It does not fetch a live site, and it never rewrites a
  file. It is report-only, and it never touches the
  network.

## How this differs

- The field is empty for this job: a fresh search of
  GitHub on Nov 12, 2026 found 0 results for
  `"html-button-type-checker-cli"` and 8 results for
  `html button type checker`, all noise (strength
  checkers and palindrome checkers built with HTML —
  pages that merely contain a button and a checker).
  No rival checks button types.
- Repo #85, html-label-checker-cli, checks form labels
  only; button types are a different check on the same
  pages. Repo #30, image-alt-checker-cli, checks
  images; buttons are a different check.

## Install

```sh
git clone https://github.com/haiderstudio/html-button-type-checker-cli.git
cd html-button-type-checker-cli
```

There is nothing else to install: Python 3.10 or newer,
standard library only, no dependencies.

## Usage

Check one HTML file:

```sh
python3 src/html_button_type_checker.py page.html
```

A file where every button has a valid type passes:

```sh
$ python3 src/html_button_type_checker.py examples/good.html
OK — 1 file(s) checked, every button has a valid type.
```

A file with buttons missing or misusing a type fails,
with the button and line for each one:

```sh
$ python3 src/html_button_type_checker.py examples/bad.html
FAIL examples/bad.html: <button "Search"> line 8 is missing type
FAIL examples/bad.html: <button "Clear"> line 10 has invalid type "foo"
FAIL examples/bad.html: <button "Reset"> line 11 has an empty type
Checked 1 file(s), 3 problem(s) in 1 file(s).
```

Check a whole folder (HTML files only):

```sh
$ python3 src/html_button_type_checker.py examples/
FAIL examples/bad.html: <button "Search"> line 8 is missing type
FAIL examples/bad.html: <button "Clear"> line 10 has invalid type "foo"
FAIL examples/bad.html: <button "Reset"> line 11 has an empty type
Checked 3 file(s), 3 problem(s) in 1 file(s).
```

Check one document from standard input:

```sh
$ python3 src/html_button_type_checker.py --stdin < examples/bad.html
FAIL <stdin>: <button "Search"> line 8 is missing type
FAIL <stdin>: <button "Clear"> line 10 has invalid type "foo"
FAIL <stdin>: <button "Reset"> line 11 has an empty type
Checked 1 file(s), 3 problem(s) in 1 file(s).
```

Machine-readable output:

```sh
$ python3 src/html_button_type_checker.py --json examples/bad.html
{
  "files": [
    {
      "path": "examples/bad.html",
      "buttons": [
        {
          "line": 8,
          "text": "Search",
          "type": null,
          "problem": "missing"
        },
        {
          "line": 10,
          "text": "Clear",
          "type": "foo",
          "problem": "invalid"
        },
        {
          "line": 11,
          "text": "Reset",
          "type": "",
          "problem": "empty"
        }
      ],
      "error": null
    }
  ],
  "checked": 1,
  "problems": 3
}
```

Exit codes: 0 when every button has a valid type, 1
when any button is missing a type or has an invalid
one, or a file cannot be read, 2 for a usage error (a
missing path, a bad flag, or no HTML files found).

## Examples

An invalid type is as bad as a missing one — the
`type="foo"` on line 10 of `examples/bad.html` fails,
while the valid `type="button"` on line 9 passes, and
the commented-out `<button>` and the one inside the
`<script>` are ignored:

```sh
$ python3 src/html_button_type_checker.py examples/bad.html
FAIL examples/bad.html: <button "Search"> line 8 is missing type
FAIL examples/bad.html: <button "Clear"> line 10 has invalid type "foo"
FAIL examples/bad.html: <button "Reset"> line 11 has an empty type
Checked 1 file(s), 3 problem(s) in 1 file(s).
```

Quoting and case do not matter — the single-quoted,
unquoted, and uppercase buttons in
`examples/good.html` all pass, including the button
outside the form:

```sh
$ python3 src/html_button_type_checker.py examples/good.html
OK — 1 file(s) checked, every button has a valid type.
```

Run every bundled example at once with `sh
examples/run-example.sh` — the output is saved in
[examples/sample-output.md](examples/sample-output.md).

## How it is tested

```sh
python3 tests/test_html_button_type_checker.py
```

72 tests cover button parsing (type `button`, `submit`,
and `reset` pass, missing type, invalid type, empty
type, whitespace-only type, a bare `type` with no value,
uppercase `BUTTON` and `TYPE` values, mixed-case
values, a value with surrounding spaces, single-quoted,
double-quoted, and unquoted values, buttons inside and
outside forms, buttons reported in document order with
lines, self-closing buttons, button text from nested
elements, whitespace collapsed in button text, long
button text cut short, `<input type="button">` ignored,
non-button tags ignored, buttons inside comments,
`<script>`, and `<style>` ignored, unclosed buttons,
malformed HTML tolerated, a document with no buttons,
an empty document), the check itself (clean files pass,
bad files report with file and line, a non-UTF-8 file
reported, input files left unchanged), the CLI (exit
0/1/2, folder walking, `.html` and `.htm` only, `.git`
skipped, `--no-recursive`, `--exclude`, a direct file
checked even without an HTML name, `--stdin`, `--json`
output, `--version`, bad flags, missing paths, empty
folders, a non-UTF-8 file reported), the bundled
examples (sample output compared byte-for-byte against
a fresh run, and the README-quoted outputs checked
against it), and hygiene checks (no placeholder text,
no absolute paths, no secrets, stdlib imports only,
`.env` first in `.gitignore`, CI file runs the test
file).

## Contributing

Small, focused improvements are welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Licence

MIT — see [LICENSE](LICENSE).

## Original work

This tool was written from scratch for this repo. The
idea of checking button types is not new, but no
existing tool does this one job as a tested
command-line gate — the field is empty, as the search
above shows — and every line of code here is original,
built on nothing but Python's standard library.
