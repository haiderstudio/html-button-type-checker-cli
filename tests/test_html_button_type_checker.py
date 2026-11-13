#!/usr/bin/env python3
"""Tests for html_button_type_checker — stdlib unittest only."""

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import html_button_type_checker as checker

REPO = Path(__file__).resolve().parent.parent


def run_cli(argv):
    """Run main(argv), capture stdout/stderr, return (code, out, err)."""
    out = io.StringIO()
    err = io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        try:
            code = checker.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def write(tmp, name, text, encoding="utf-8"):
    path = Path(tmp) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(text, bytes):
        path.write_bytes(text)
    else:
        path.write_text(text, encoding=encoding)
    return str(path)


class TestFindBadButtons(unittest.TestCase):
    def test_type_button_passes(self):
        html = '<button type="button">Open</button>'
        self.assertEqual(checker.find_bad_buttons(html), [])

    def test_type_submit_passes(self):
        html = '<button type="submit">Send</button>'
        self.assertEqual(checker.find_bad_buttons(html), [])

    def test_type_reset_passes(self):
        html = '<button type="reset">Clear</button>'
        self.assertEqual(checker.find_bad_buttons(html), [])

    def test_missing_type(self):
        html = '<button>Search</button>'
        got = checker.find_bad_buttons(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["line"], 1)
        self.assertEqual(got[0]["text"], "Search")
        self.assertIsNone(got[0]["type"])
        self.assertEqual(got[0]["problem"], "missing")

    def test_missing_type_no_text(self):
        html = '<button></button>'
        got = checker.find_bad_buttons(html)
        self.assertEqual(len(got), 1)
        self.assertIsNone(got[0]["text"])
        self.assertEqual(got[0]["problem"], "missing")

    def test_invalid_type_value(self):
        html = '<button type="foo">Clear</button>'
        got = checker.find_bad_buttons(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["type"], "foo")
        self.assertEqual(got[0]["problem"], "invalid")

    def test_empty_type(self):
        html = '<button type="">Reset</button>'
        got = checker.find_bad_buttons(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["type"], "")
        self.assertEqual(got[0]["problem"], "empty")

    def test_whitespace_only_type_is_empty(self):
        html = '<button type="  ">Reset</button>'
        got = checker.find_bad_buttons(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["problem"], "empty")

    def test_bare_type_attribute_is_empty(self):
        html = '<button type>Reset</button>'
        got = checker.find_bad_buttons(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["problem"], "empty")

    def test_uppercase_button_tag_and_type(self):
        html = '<BUTTON TYPE="BUTTON">Menu</BUTTON>'
        self.assertEqual(checker.find_bad_buttons(html), [])

    def test_uppercase_type_value_submit(self):
        html = '<button TYPE="SUBMIT">Send</button>'
        self.assertEqual(checker.find_bad_buttons(html), [])

    def test_mixed_case_type_value_passes(self):
        html = '<button type="Submit">Send</button>'
        self.assertEqual(checker.find_bad_buttons(html), [])

    def test_type_value_with_surrounding_spaces_passes(self):
        html = '<button type=" button ">Open</button>'
        self.assertEqual(checker.find_bad_buttons(html), [])

    def test_single_quoted_type_found(self):
        html = "<button type='button'>Open</button>"
        self.assertEqual(checker.find_bad_buttons(html), [])

    def test_unquoted_type_found(self):
        html = '<button type=reset>Clear</button>'
        self.assertEqual(checker.find_bad_buttons(html), [])

    def test_unquoted_invalid_found(self):
        html = '<button type=foo>Clear</button>'
        got = checker.find_bad_buttons(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["problem"], "invalid")

    def test_button_inside_form_missing(self):
        html = '<form action="/go"><button>Go</button></form>'
        got = checker.find_bad_buttons(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["problem"], "missing")

    def test_button_outside_form_missing(self):
        html = '<button>Help</button>'
        got = checker.find_bad_buttons(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["problem"], "missing")

    def test_button_inside_form_valid_passes(self):
        html = ('<form action="/go">'
                '<button type="submit">Go</button></form>')
        self.assertEqual(checker.find_bad_buttons(html), [])

    def test_buttons_reported_in_document_order_with_lines(self):
        html = ('<button>One</button>\n'
                '<p>text</p>\n'
                '<button type="button">Two</button>\n'
                '<button type="foo">Three</button>\n'
                '<button type="">Four</button>')
        got = checker.find_bad_buttons(html)
        self.assertEqual(
            [(g["text"], g["line"], g["problem"]) for g in got],
            [("One", 1, "missing"),
             ("Three", 4, "invalid"),
             ("Four", 5, "empty")])

    def test_self_closing_button_with_type_passes(self):
        html = '<button type="button" />'
        self.assertEqual(checker.find_bad_buttons(html), [])

    def test_self_closing_button_without_type_fails(self):
        html = '<button />'
        got = checker.find_bad_buttons(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["problem"], "missing")

    def test_button_text_with_nested_element(self):
        html = '<button><span>Click</span> me</button>'
        got = checker.find_bad_buttons(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["text"], "Click me")

    def test_button_text_whitespace_collapsed(self):
        html = '<button>\n  Open\n  dialog\n</button>'
        got = checker.find_bad_buttons(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["text"], "Open dialog")

    def test_long_button_text_truncated(self):
        html = ('<button>' + 'x' * 50 + '</button>')
        got = checker.find_bad_buttons(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["text"], "x" * 37 + "...")

    def test_input_type_button_is_not_a_button(self):
        html = '<input type="button" value="Go">'
        self.assertEqual(checker.find_bad_buttons(html), [])

    def test_non_button_tags_ignored(self):
        html = '<div type="button"></div><a type="submit">x</a>'
        self.assertEqual(checker.find_bad_buttons(html), [])

    def test_button_inside_comment_ignored(self):
        html = ('<button type="button">Real</button>\n'
                '<!-- <button>not a real button -->')
        self.assertEqual(checker.find_bad_buttons(html), [])

    def test_button_inside_script_ignored(self):
        html = ('<script>\n'
                'var s = \'<button>fake</button>\';\n</script>\n'
                '<button type="button">Real</button>')
        self.assertEqual(checker.find_bad_buttons(html), [])

    def test_button_inside_style_ignored(self):
        html = ('<style>\nbutton { color: red; }\n</style>\n'
                '<button type="button">Real</button>')
        self.assertEqual(checker.find_bad_buttons(html), [])

    def test_unclosed_button_still_reported(self):
        html = '<button>Open'
        got = checker.find_bad_buttons(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["text"], "Open")
        self.assertEqual(got[0]["problem"], "missing")

    def test_unclosed_tags_still_parsed(self):
        html = '<button>Open</button>\n<p>text'
        got = checker.find_bad_buttons(html)
        self.assertEqual(len(got), 1)

    def test_malformed_html_tolerated(self):
        html = '<button><div>oops</button></div>'
        got = checker.find_bad_buttons(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["problem"], "missing")

    def test_empty_document(self):
        self.assertEqual(checker.find_bad_buttons(""), [])

    def test_no_buttons_at_all(self):
        html = '<div><p>plain text</p></div>'
        self.assertEqual(checker.find_bad_buttons(html), [])

    def test_button_with_other_attributes_only(self):
        html = '<button id="go" class="big">Go</button>'
        got = checker.find_bad_buttons(html)
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0]["problem"], "missing")


class TestCheckFile(unittest.TestCase):
    def test_clean_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "ok.html",
                         '<button type="submit">Send</button>')
            bad, err = checker.check_file(path)
            self.assertEqual((bad, err), ([], None))

    def test_bad_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", '<button>Go</button>')
            bad, err = checker.check_file(path)
            self.assertIsNone(err)
            self.assertEqual(len(bad), 1)

    def test_missing_file_reports_error(self):
        bad, err = checker.check_file("/nonexistent/page.html")
        self.assertEqual(bad, [])
        self.assertIsNotNone(err)

    def test_non_utf8_file_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", b'<button>Go\xff</button>')
            bad, err = checker.check_file(path)
            self.assertEqual(bad, [])
            self.assertEqual(err, "not valid UTF-8")

    def test_input_file_left_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            text = '<button>Go</button>'
            path = write(tmp, "bad.html", text)
            checker.check_file(path)
            self.assertEqual(Path(path).read_text(), text)


class TestCollectFiles(unittest.TestCase):
    def test_direct_file_any_name_checked(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "page.txt", '<button>Go</button>')
            self.assertEqual(checker.collect_files([path]), [path])

    def test_folder_walk_finds_html_and_htm_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.html", "")
            b = write(tmp, "sub/b.htm", "")
            write(tmp, "c.md", "")
            write(tmp, "d.txt", "")
            got = checker.collect_files([tmp])
            self.assertEqual(got, sorted([a, b]))

    def test_git_folder_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, ".git/hooks/sample.html", "")
            a = write(tmp, "a.html", "")
            self.assertEqual(checker.collect_files([tmp]), [a])

    def test_no_recursive(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.html", "")
            write(tmp, "sub/b.html", "")
            self.assertEqual(
                checker.collect_files([tmp], recursive=False), [a])

    def test_exclude_pattern(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = write(tmp, "a.html", "")
            write(tmp, "skip.html", "")
            got = checker.collect_files([tmp], exclude=["skip.html"])
            self.assertEqual(got, [a])

    def test_missing_path_raises(self):
        with self.assertRaises(FileNotFoundError):
            checker.collect_files(["/nonexistent/path"])

    def test_duplicates_deduped(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "a.html", "")
            self.assertEqual(
                checker.collect_files([path, path]), [path])


class TestRun(unittest.TestCase):
    def test_clean_run_exit_0(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "ok.html",
                         '<button type="submit">Send</button>')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 0)
            self.assertIn(
                "OK — 1 file(s) checked, every button has a valid type.",
                out)

    def test_dirty_run_exit_1_and_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", '<button>Go</button>')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            # CWD-robust: assert on the file name and message, never
            # on the absolute path the CLI echoes.
            self.assertIn("bad.html", out)
            self.assertIn('<button "Go"> line 1 is missing type', out)
            self.assertIn("Checked 1 file(s), 1 problem(s) in 1 file(s).",
                          out)

    def test_invalid_type_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html",
                         '<button type="foo">Clear</button>')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("bad.html", out)
            self.assertIn(
                '<button "Clear"> line 1 has invalid type "foo"', out)

    def test_empty_type_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html",
                         '<button type="">Reset</button>')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn(
                '<button "Reset"> line 1 has an empty type', out)

    def test_button_without_text_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", '<button></button>')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("<button> line 1 is missing type", out)

    def test_folder_summary_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(tmp, "good.html",
                  '<button type="submit">Send</button>')
            write(tmp, "bad.html", '<button>Go</button>')
            code, out, _ = run_cli([tmp])
            self.assertEqual(code, 1)
            self.assertIn("Checked 2 file(s), 1 problem(s) in 1 file(s).",
                          out)

    def test_json_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html",
                         '<button>Go</button>\n'
                         '<button type="foo">Clear</button>')
            code, out, _ = run_cli(["--json", path])
            self.assertEqual(code, 1)
            data = json.loads(out)
            self.assertEqual(data["checked"], 1)
            self.assertEqual(data["problems"], 2)
            self.assertEqual(
                os.path.basename(data["files"][0]["path"]), "bad.html")
            self.assertEqual(data["files"][0]["buttons"][0]["text"], "Go")
            self.assertEqual(data["files"][0]["buttons"][0]["problem"],
                             "missing")
            self.assertIsNone(data["files"][0]["buttons"][0]["type"])
            self.assertEqual(data["files"][0]["buttons"][1]["type"], "foo")
            self.assertEqual(data["files"][0]["buttons"][1]["problem"],
                             "invalid")
            self.assertIsNone(data["files"][0]["error"])

    def test_stdin_clean(self):
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO("")
            code, out, _ = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 0)
        self.assertIn(
            "OK — 1 file(s) checked, every button has a valid type.",
            out)

    def test_stdin_dirty_via_main(self):
        old_stdin = sys.stdin
        try:
            sys.stdin = io.StringIO('<button>Go</button>')
            code, out, _ = run_cli(["--stdin"])
        finally:
            sys.stdin = old_stdin
        self.assertEqual(code, 1)
        self.assertIn(
            'FAIL <stdin>: <button "Go"> line 1 is missing type', out)

    def test_stdin_with_paths_is_usage_error(self):
        code, _, err = run_cli(["--stdin", "x.html"])
        self.assertEqual(code, 2)
        self.assertIn("--stdin takes no file", err)

    def test_no_paths_is_usage_error(self):
        code, _, err = run_cli([])
        self.assertEqual(code, 2)
        self.assertIn("at least one HTML file", err)

    def test_missing_path_exit_2(self):
        code, _, err = run_cli(["/nonexistent/page.html"])
        self.assertEqual(code, 2)
        self.assertIn("no such file or folder", err)

    def test_empty_folder_exit_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            code, _, err = run_cli([tmp])
            self.assertEqual(code, 2)
            self.assertIn("no HTML files found", err)

    def test_bad_flag_exit_2(self):
        code, _, _ = run_cli(["--nope"])
        self.assertEqual(code, 2)

    def test_version(self):
        code, out, _ = run_cli(["--version"])
        self.assertEqual(code, 0)
        self.assertIn("html_button_type_checker 1.0.0", out)

    def test_non_utf8_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = write(tmp, "bad.html", b'<button>Go\xff</button>')
            code, out, _ = run_cli([path])
            self.assertEqual(code, 1)
            self.assertIn("not valid UTF-8", out)


class TestExamples(unittest.TestCase):
    def test_run_example_output_matches_sample(self):
        result = subprocess.run(
            ["sh", "examples/run-example.sh"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        expected = (REPO / "examples/sample-output.md").read_text()
        self.assertEqual(result.stdout, expected)

    def test_readme_quotes_match_real_runs(self):
        readme = (REPO / "README.md").read_text()
        good = subprocess.run(
            [sys.executable, "src/html_button_type_checker.py",
             "examples/good.html"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(good.returncode, 0)
        self.assertIn(good.stdout.strip(), readme)
        bad = subprocess.run(
            [sys.executable, "src/html_button_type_checker.py",
             "examples/bad.html"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(bad.returncode, 1)
        self.assertIn(bad.stdout.strip(), readme)
        folder = subprocess.run(
            [sys.executable, "src/html_button_type_checker.py",
             "examples/"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(folder.returncode, 1)
        self.assertIn("Checked 3 file(s), 3 problem(s) in 1 file(s).",
                      folder.stdout)
        self.assertIn("Checked 3 file(s), 3 problem(s) in 1 file(s).",
                      readme)
        js = subprocess.run(
            [sys.executable, "src/html_button_type_checker.py",
             "--json", "examples/bad.html"],
            cwd=REPO, capture_output=True, text=True)
        self.assertEqual(js.returncode, 1)
        self.assertIn(js.stdout.strip(), readme)


class TestHygiene(unittest.TestCase):
    def _repo_files(self):
        for root, dirs, files in os.walk(REPO):
            dirs[:] = [d for d in dirs
                       if d not in (".git", "__pycache__")]
            for name in files:
                if name.endswith(".pyc"):
                    continue
                yield Path(root) / name

    def test_no_placeholder_text(self):
        banned = ["TODO", "coming soon", "lorem", "FIXME", "XXX"]
        hits = []
        for path in self._repo_files():
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="ignore")
            for word in banned:
                if word in text:
                    hits.append("%s: %s" % (path.name, word))
        self.assertEqual(hits, [])

    def test_no_absolute_paths(self):
        hits = []
        for path in self._repo_files():
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="ignore")
            for marker in ("/home/", "/Users/", "C:\\"):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_no_secrets(self):
        hits = []
        for path in self._repo_files():
            if "tests" in path.parts:
                continue
            text = path.read_text(errors="ignore").lower()
            for marker in ("api_key", "api-key", "password", "secret=",
                           "token="):
                if marker in text:
                    hits.append("%s: %s" % (path.name, marker))
        self.assertEqual(hits, [])

    def test_stdlib_imports_only(self):
        import ast
        src = REPO / "src/html_button_type_checker.py"
        tree = ast.parse(src.read_text())
        stdlib = set(sys.stdlib_module_names)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse(imported - stdlib, imported)
        self.assertNotIn("yaml", imported)

    def test_gitignore_lists_env_first(self):
        lines = (REPO / ".gitignore").read_text().splitlines()
        self.assertEqual(lines[0], ".env")

    def test_ci_runs_this_test_file(self):
        ci = (REPO / ".github/workflows/ci.yml").read_text()
        self.assertIn("tests/test_html_button_type_checker.py", ci)
        self.assertIn("ubuntu-latest", ci)
        self.assertIn("3.12", ci)
        self.assertIn("actions/checkout", ci)
        self.assertIn("setup-python", ci)


if __name__ == "__main__":
    unittest.main()
