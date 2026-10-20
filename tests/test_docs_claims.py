import importlib.util
import shutil

import pytest

from conftest import REPO

_spec = importlib.util.spec_from_file_location("check_docs", REPO / "scripts" / "check_docs.py")
check_docs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_docs)


@pytest.fixture
def repo_copy(tmp_path):
    dst = tmp_path / "repo"
    shutil.copytree(REPO, dst, ignore=shutil.ignore_patterns(".git", ".venv", "out", "__pycache__", "*.egg-info"))
    return dst


def test_repo_docs_are_clean():
    assert check_docs.check(REPO) == []


def test_exit_codes(repo_copy, capsys):
    assert check_docs.main(["--root", str(REPO)]) == 0
    assert capsys.readouterr().out == ""
    (repo_copy / "ios" / "README.md").write_text("[gone](nope.md)\n")
    assert check_docs.main(["--root", str(repo_copy)]) == 1
    assert capsys.readouterr().out.count("\n") == 1


def test_reports_invented_flag_broken_link_and_missing_test(repo_copy, capsys):
    readme = repo_copy / "README.md"
    readme.write_text(readme.read_text() + (
        "\n```bash\npython -m arrival sim --episodes 2 --warp-speed 9\n```\n"
        "\nSee [the guide](docs/NO-SUCH-GUIDE.md).\n"
        "\nRun `tests/test_cli.py::test_no_such_thing_exists`.\n"))
    assert check_docs.main(["--root", str(repo_copy)]) == 1
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 3
    assert any("--warp-speed" in x and "does not parse" in x for x in lines)
    assert any("broken link docs/NO-SUCH-GUIDE.md" in x for x in lines)
    assert any("no test named test_no_such_thing_exists" in x for x in lines)


def test_parser_rejects_bad_subcommand_and_choice():
    parser = check_docs._cli_parser()
    assert check_docs.check_command(parser, "python -m arrival sim --episodes 2") is None
    assert check_docs.check_command(parser, "python -m arrival frobnicate")
    assert check_docs.check_command(parser, "python -m arrival sim --policy magic")


def test_continuation_lines_and_comments_are_joined():
    text = "```\npython -m arrival sim \\\n  --episodes 2  # tiny\n```\n"
    assert check_docs.fenced_commands(text) == [(2, "python -m arrival sim --episodes 2")]


def test_task_listed_done_and_open(tmp_path):
    doc = tmp_path / "README.md"
    text = "**Done:** CAP-1, MAN-2. **Open:** MAN-2, SIM-5."
    assert check_docs.check_status_lists(doc, tmp_path, text) == [
        "README.md:1: MAN-2 is listed as both Done and Open"]
    assert check_docs.check_status_lists(doc, tmp_path, "**Done:** A-1. **Partial:** CAP-1. **Open:** SIM-5.") == []


def test_label_sentence_must_match_writer_constants(tmp_path):
    consts = check_docs.writer_constants(REPO)
    assert consts[("demo", "arrival_physically_valid")] == "false"
    assert consts[("sim", "arrival_physically_valid")] == "true"
    doc = tmp_path / "README.md"
    bad = "`python -m arrival sim` writes data (`arrival_physically_valid: false`)."
    good = "`python -m arrival demo` writes data (`arrival_physically_valid: false`)."
    assert len(check_docs.check_labels(doc, tmp_path, bad, consts)) == 1
    assert check_docs.check_labels(doc, tmp_path, good, consts) == []
