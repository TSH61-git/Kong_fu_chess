"""Integration tests for the text-script DSL harness."""
from pathlib import Path

from texttests.script_parser import ScriptParser
from texttests.script_runner import ScriptRunner


def test_all_kfc_scripts_match_expected_output():
    script_dir = Path(__file__).parent / "scripts"
    scripts = sorted(script_dir.glob("*.kfc"))
    assert scripts, "Expected at least one .kfc script to exercise the harness"

    runner = ScriptRunner()
    for script_path in scripts:
        parsed = ScriptParser.parse(script_path)
        actual = runner.run_script(script_path)
        assert actual == parsed.expected_text
