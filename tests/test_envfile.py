"""Tests des schreibenden Zugriffs auf die ``.env``.

In dieser Datei stehen die Zugangsdaten. Zwei Dinge duerfen dabei nie
passieren:

* **Etwas verlieren.** Die ``.env`` ist auch Dokumentation - die Hinweise
  darin sind mehr wert als die Bequemlichkeit, sie neu zu erzeugen.
* **Zu weit oeffnen.** Auf einem Server mit mehreren Konten entscheiden die
  Dateirechte darueber, wer den API-Key lesen kann.
"""

from __future__ import annotations

import stat
from pathlib import Path

from core.envfile import (
    SECRET_FILE_MODE,
    file_is_world_readable,
    mask,
    read_env_value,
    update_env_file,
)

EXAMPLE = """\
# =============================================================================
#  Trading-System Konfiguration
# =============================================================================

# --- Bybit --------------------------------------------------------------
BYBIT__ENVIRONMENT=demo
BYBIT__API_KEY=
BYBIT__API_SECRET=

# API-Key-Rechte auf Bybit:
#   [x] Read      [x] Trade      [ ] Withdrawal  <- NIEMALS aktivieren!
BYBIT__SYMBOL=BTCUSDT

# --- Risiko -------------------------------------------------------------
RISK__MAX_DRAWDOWN_PCT=15.0
"""


class TestUpdate:
    def test_values_are_set(self, tmp_path: Path) -> None:
        path = tmp_path / ".env"
        path.write_text(EXAMPLE)

        update_env_file(path, {"BYBIT__API_KEY": "abc123", "BYBIT__API_SECRET": "geheim"})

        assert read_env_value(path, "BYBIT__API_KEY") == "abc123"
        assert read_env_value(path, "BYBIT__API_SECRET") == "geheim"

    def test_comments_and_other_keys_survive(self, tmp_path: Path) -> None:
        """Der wichtigste Test dieser Datei.

        Wer die ``.env`` neu generiert statt sie zu bearbeiten, wirft die
        Warnhinweise weg - und genau die halten jemanden davon ab, das
        Auszahlungsrecht zu aktivieren.
        """
        path = tmp_path / ".env"
        path.write_text(EXAMPLE)

        update_env_file(path, {"BYBIT__API_KEY": "abc123"})
        content = path.read_text()

        assert "NIEMALS aktivieren!" in content
        assert "# --- Risiko" in content
        assert read_env_value(path, "RISK__MAX_DRAWDOWN_PCT") == "15.0"
        assert read_env_value(path, "BYBIT__SYMBOL") == "BTCUSDT"

    def test_existing_value_is_replaced_not_duplicated(self, tmp_path: Path) -> None:
        """Sonst gewinnt beim Laden irgendeine Zeile - und welche, haengt am
        Parser statt an der Absicht."""
        path = tmp_path / ".env"
        path.write_text(EXAMPLE)

        update_env_file(path, {"BYBIT__API_KEY": "alt"})
        update_env_file(path, {"BYBIT__API_KEY": "neu"})

        lines = [
            line for line in path.read_text().splitlines()
            if line.startswith("BYBIT__API_KEY=")
        ]
        assert lines == ["BYBIT__API_KEY=neu"]

    def test_commented_out_key_is_not_treated_as_the_target(self, tmp_path: Path) -> None:
        """``# BYBIT__API_KEY=`` ist ein Beispiel, kein Eintrag.

        Wird es ueberschrieben, verschwindet der Kommentar - und der echte
        Eintrag wird trotzdem angehaengt. Das Ergebnis waere eine Datei, in
        der der Schluessel scheinbar zweimal steht.
        """
        path = tmp_path / ".env"
        path.write_text("# BYBIT__API_KEY=beispiel\nRISK__MAX_DRAWDOWN_PCT=15.0\n")

        update_env_file(path, {"BYBIT__API_KEY": "echt"})
        content = path.read_text()

        assert "# BYBIT__API_KEY=beispiel" in content
        assert "BYBIT__API_KEY=echt" in content
        assert read_env_value(path, "BYBIT__API_KEY") == "echt"

    def test_missing_key_is_appended(self, tmp_path: Path) -> None:
        path = tmp_path / ".env"
        path.write_text("RISK__MAX_DRAWDOWN_PCT=15.0\n")

        update_env_file(path, {"NOTIFY__TELEGRAM_CHAT_ID": "12345"})

        assert read_env_value(path, "NOTIFY__TELEGRAM_CHAT_ID") == "12345"
        assert read_env_value(path, "RISK__MAX_DRAWDOWN_PCT") == "15.0"

    def test_file_without_trailing_newline(self, tmp_path: Path) -> None:
        path = tmp_path / ".env"
        path.write_text("BYBIT__API_KEY=alt")  # kein Zeilenumbruch am Ende

        update_env_file(path, {"BYBIT__API_SECRET": "neu"})

        assert read_env_value(path, "BYBIT__API_KEY") == "alt"
        assert read_env_value(path, "BYBIT__API_SECRET") == "neu"
        assert path.read_text().endswith("\n")

    def test_missing_file_is_created(self, tmp_path: Path) -> None:
        path = tmp_path / ".env"

        update_env_file(path, {"BYBIT__API_KEY": "abc"})

        assert read_env_value(path, "BYBIT__API_KEY") == "abc"

    def test_no_leftover_temporary_file(self, tmp_path: Path) -> None:
        """Die Nebendatei traegt kurzzeitig das Secret - sie darf nicht bleiben."""
        path = tmp_path / ".env"
        path.write_text(EXAMPLE)

        update_env_file(path, {"BYBIT__API_SECRET": "geheim"})

        assert [p.name for p in tmp_path.iterdir()] == [".env"]


class TestPermissions:
    def test_written_file_is_owner_only(self, tmp_path: Path) -> None:
        """0600 - auf einem Server mit mehreren Konten der Unterschied
        zwischen geschuetzt und oeffentlich."""
        path = tmp_path / ".env"
        path.write_text(EXAMPLE)

        update_env_file(path, {"BYBIT__API_SECRET": "geheim"})

        mode = stat.S_IMODE(path.stat().st_mode)
        assert mode == SECRET_FILE_MODE
        assert not file_is_world_readable(path)

    def test_loose_permissions_are_tightened(self, tmp_path: Path) -> None:
        """Eine schon offene Datei wird beim Schreiben mitgeschlossen."""
        path = tmp_path / ".env"
        path.write_text(EXAMPLE)
        path.chmod(0o644)
        assert file_is_world_readable(path)

        update_env_file(path, {"BYBIT__API_KEY": "abc"})

        assert not file_is_world_readable(path)


class TestRead:
    def test_missing_file_returns_none(self, tmp_path: Path) -> None:
        assert read_env_value(tmp_path / "gibtsnicht", "BYBIT__API_KEY") is None

    def test_empty_value_is_empty_string(self, tmp_path: Path) -> None:
        """Wichtig fuer die Unterscheidung 'nicht gesetzt' und 'leer gesetzt' -
        der setup-Befehl fragt nur bei einem echten Wert nach dem Ueberschreiben."""
        path = tmp_path / ".env"
        path.write_text(EXAMPLE)

        assert read_env_value(path, "BYBIT__API_KEY") == ""

    def test_quotes_are_stripped(self, tmp_path: Path) -> None:
        path = tmp_path / ".env"
        path.write_text('BYBIT__API_KEY="abc123"\n')

        assert read_env_value(path, "BYBIT__API_KEY") == "abc123"

    def test_similar_key_names_do_not_collide(self, tmp_path: Path) -> None:
        """``BYBIT__API_KEY`` darf nicht auf ``BYBIT__API_KEY_ALT`` passen."""
        path = tmp_path / ".env"
        path.write_text("BYBIT__API_KEY_ALT=falsch\nBYBIT__API_KEY=richtig\n")

        assert read_env_value(path, "BYBIT__API_KEY") == "richtig"


class TestMask:
    def test_long_secret_shows_the_ends(self) -> None:
        assert mask("abcdefghijklmnop") == "abcd********mnop"

    def test_short_secret_is_fully_hidden(self) -> None:
        """Bei acht Zeichen waeren vier sichtbare bereits die halbe Miete."""
        assert mask("kurz1234") == "********"
        assert "kurz" not in mask("kurz1234")
