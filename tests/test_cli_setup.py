"""Tests des ``setup``-Befehls.

Der Befehl nimmt die Zugangsdaten entgegen. Geprueft wird deshalb vor allem,
was er **nicht** tut: nichts speichern, wenn die Eingabe offensichtlich falsch
ist, und nichts ueberschreiben, ohne zu fragen.

Der Schluessel wird bewusst per Eingabeaufforderung abgefragt und nicht als
Kommandozeilenargument entgegengenommen - ein Argument stuende in der
Prozessliste und in der Shell-History.
"""

from __future__ import annotations

import stat
from pathlib import Path

import pytest
from typer.testing import CliRunner

from cli import app
from core.config import get_settings
from core.envfile import read_env_value

runner = CliRunner()

EXAMPLE = """\
BYBIT__ENVIRONMENT=demo
BYBIT__API_KEY=
BYBIT__API_SECRET=

# [x] Read   [x] Trade   [ ] Withdrawal  <- NIEMALS aktivieren!
RISK__MAX_DRAWDOWN_PCT=15.0
"""

KEY = "AbCdEfGhIjKlMnOpQr"
SECRET = "aBcDeFgHiJkLmNoPqRsTuVwXyZ0123456789abcd"


@pytest.fixture
def workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env.example").write_text(EXAMPLE)
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


class TestHappyPath:
    def test_credentials_are_written(self, workspace: Path) -> None:
        result = runner.invoke(
            app, ["setup", "--no-pruefen"], input=f"{KEY}\n{SECRET}\n"
        )

        assert result.exit_code == 0, result.output
        assert read_env_value(workspace / ".env", "BYBIT__API_KEY") == KEY
        assert read_env_value(workspace / ".env", "BYBIT__API_SECRET") == SECRET
        assert read_env_value(workspace / ".env", "BYBIT__ENVIRONMENT") == "demo"

    def test_secret_is_never_printed(self, workspace: Path) -> None:
        """Weder die Eingabe noch die Bestaetigung darf das Secret zeigen -
        sonst steht es im Terminal-Verlauf und in jeder Bildschirmaufnahme."""
        result = runner.invoke(
            app, ["setup", "--no-pruefen"], input=f"{KEY}\n{SECRET}\n"
        )

        assert SECRET not in result.output

    def test_file_is_owner_only(self, workspace: Path) -> None:
        runner.invoke(app, ["setup", "--no-pruefen"], input=f"{KEY}\n{SECRET}\n")

        mode = stat.S_IMODE((workspace / ".env").stat().st_mode)
        assert mode == 0o600

    def test_example_comments_survive(self, workspace: Path) -> None:
        runner.invoke(app, ["setup", "--no-pruefen"], input=f"{KEY}\n{SECRET}\n")

        assert "NIEMALS aktivieren!" in (workspace / ".env").read_text()

    def test_environment_is_set_along_with_the_key(self, workspace: Path) -> None:
        """Key und Umgebung gehoeren zusammen: Ein Demo-Key funktioniert nur
        gegen die Demo-URL. Getrennt gesetzt waere die haeufigste Fehlerquelle
        ein Key, der zur falschen Welt gehoert."""
        result = runner.invoke(
            app,
            ["setup", "--umgebung", "testnet", "--no-pruefen"],
            input=f"{KEY}\n{SECRET}\n",
        )

        assert result.exit_code == 0, result.output
        assert read_env_value(workspace / ".env", "BYBIT__ENVIRONMENT") == "testnet"


class TestInputValidation:
    def test_swapped_key_and_secret_are_caught(self, workspace: Path) -> None:
        """Bei Bybit ist das Secret laenger als der Key. Andersherum hat
        jemand die Felder vertauscht - das faellt sonst erst beim
        Health-Check auf, mit einer nichtssagenden Signaturmeldung."""
        result = runner.invoke(
            app, ["setup", "--no-pruefen"], input=f"{SECRET}\n{KEY}\n"
        )

        assert result.exit_code == 2
        assert "vertauscht" in result.output
        assert not (workspace / ".env").exists() or not read_env_value(
            workspace / ".env", "BYBIT__API_KEY"
        )

    def test_pasted_whitespace_is_caught(self, workspace: Path) -> None:
        """Beim Kopieren aus dem Browser wandert leicht ein Leerzeichen mit."""
        result = runner.invoke(
            app, ["setup", "--no-pruefen"], input=f"AbCd EfGh\n{SECRET}\n"
        )

        assert result.exit_code == 2
        assert "Leerzeichen" in result.output

    def test_empty_secret_is_refused(self, workspace: Path) -> None:
        """Eine leere Eingabe fragt erneut, statt sie zu uebernehmen.

        Das erledigt bereits die Eingabeaufforderung; entscheidend ist, dass
        am Ende nichts Leeres in der Datei steht.
        """
        result = runner.invoke(app, ["setup", "--no-pruefen"], input=f"{KEY}\n\n")

        assert result.exit_code != 0
        assert read_env_value(workspace / ".env", "BYBIT__API_SECRET") == ""

    def test_credential_check_catches_empty_values(self) -> None:
        """Der Pruefer selbst - unabhaengig davon, was die Eingabe schon
        abfaengt. Er wird auch aufgerufen, wenn spaeter eine andere Quelle
        die Werte liefert."""
        from cli import _check_credentials

        assert _check_credentials("", SECRET)
        assert _check_credentials(KEY, "")
        assert _check_credentials(KEY, SECRET) == []

    def test_unknown_environment_is_refused(self, workspace: Path) -> None:
        result = runner.invoke(app, ["setup", "--umgebung", "produktion"])

        assert result.exit_code != 0
        assert "demo" in result.output


class TestGuards:
    def test_existing_key_is_not_overwritten_without_asking(
        self, workspace: Path
    ) -> None:
        runner.invoke(app, ["setup", "--no-pruefen"], input=f"{KEY}\n{SECRET}\n")

        result = runner.invoke(
            app, ["setup", "--no-pruefen"], input="n\nNEUERKEY\nNEUESSECRET\n"
        )

        assert result.exit_code == 1
        assert "Abgebrochen" in result.output
        assert read_env_value(workspace / ".env", "BYBIT__API_KEY") == KEY

    def test_existing_key_is_shown_masked(self, workspace: Path) -> None:
        runner.invoke(app, ["setup", "--no-pruefen"], input=f"{KEY}\n{SECRET}\n")

        result = runner.invoke(app, ["setup", "--no-pruefen"], input="n\n")

        assert KEY not in result.output
        assert "AbCd" in result.output  # maskiert, aber wiedererkennbar

    def test_mainnet_needs_confirmation(self, workspace: Path) -> None:
        """Echtes Geld bekommt eine eigene Rueckfrage - vor der Eingabe,
        nicht danach."""
        result = runner.invoke(
            app, ["setup", "--umgebung", "mainnet", "--no-pruefen"], input="n\n"
        )

        assert result.exit_code == 1
        assert "echtes Geld" in result.output
        assert not (workspace / ".env").exists()

    def test_missing_example_is_reported(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Ohne .env.example steht man im falschen Verzeichnis."""
        monkeypatch.chdir(tmp_path)
        get_settings.cache_clear()

        result = runner.invoke(app, ["setup", "--no-pruefen"], input=f"{KEY}\n{SECRET}\n")

        assert result.exit_code == 2
        assert "falsches Verzeichnis" in result.output


class TestGuidance:
    def test_demo_explains_the_separate_key(self, workspace: Path) -> None:
        """Der haeufigste Stolperstein beim Demo-Start: Demo-Keys werden im
        Demo-Konto erzeugt und funktionieren nur dort."""
        result = runner.invoke(app, ["setup", "--no-pruefen"], input=f"{KEY}\n{SECRET}\n")

        assert "Demo Trading" in result.output
        assert "nur dort" in result.output

    def test_read_write_is_named_explicitly(self, workspace: Path) -> None:
        """Bybit fragt beim Anlegen zuerst 'Read-Only oder Read-Write'.

        Read-Only ist die naheliegende, sichere Wahl - und die falsche: Ein
        solcher Key kann keine Order platzieren, der Handel scheitert dann
        bei jedem Signal mit einer Rechtemeldung.
        """
        result = runner.invoke(app, ["setup", "--no-pruefen"], input=f"{KEY}\n{SECRET}\n")

        assert "Read-Write" in result.output
        assert "keine Order" in result.output

    def test_withdrawal_warning_is_shown(self, workspace: Path) -> None:
        result = runner.invoke(app, ["setup", "--no-pruefen"], input=f"{KEY}\n{SECRET}\n")

        assert "NIEMALS aktivieren" in result.output
