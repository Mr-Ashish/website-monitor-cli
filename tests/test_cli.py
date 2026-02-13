from typer.testing import CliRunner

from cli_boilerplate.main import app

runner = CliRunner()


def test_help_shows_root_description() -> None:
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Website Monitor CLI boilerplate" in result.stdout


def test_demo_run_smoke() -> None:
    result = runner.invoke(app, ["demo", "run", "--total", "3", "--delay", "0"])
    assert result.exit_code == 0
    assert "Demo command finished" in result.stdout
