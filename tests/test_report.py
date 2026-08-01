"""Tests fuer den selbstsendenden Bericht.

Zwei Eigenschaften sind hier wichtiger als alles andere, weil ihr Versagen
oeffentlich und unumkehrbar waere:

**Es darf nur mitgehen, was gemeint war.** Ein automatischer Vorgang, der
einsammelt, was gerade herumliegt, committet frueher oder spaeter etwas, das
niemand veroeffentlichen wollte. Deshalb gibt es hier einen Test, der eine
fremde geaenderte Datei danebenlegt und prueft, dass sie unangetastet bleibt.

**Es darf nichts Vertrauliches drinstehen.** Das Repository ist oeffentlich.
Git behaelt die Historie; ein einmal veroeffentlichter Schluessel ist auch nach
dem Loeschen noch da. Der Filter arbeitet auf Schluesselnamen und wird hier
gegen die Schreibweisen geprueft, die tatsaechlich vorkommen.

Dazu die unbequeme Eigenschaft: **Senden darf nie den Lauf abbrechen.** Ein
fehlgeschlagener Push ist ein Uebermittlungsproblem, kein Forschungsergebnis.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from core.report import (
    PublishStatus,
    publish,
    scrub,
    write_report,
)


def git(root: Path, *args: str) -> None:
    subprocess.run(
        ["git", *args], cwd=root, check=True, capture_output=True, text=True
    )


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Ein echtes Git-Repository mit echtem Remote - kein Double.

    Ein nachgebautes Git waere hier wertlos: Genau die Eigenheiten, an denen
    das schiefgeht (Pathspec, fehlende Identitaet, abgelehnter Push), sind die,
    die ein Double nicht hat.
    """
    remote = tmp_path / "remote.git"
    subprocess.run(
        ["git", "init", "--bare", "-b", "haupt", str(remote)],
        check=True,
        capture_output=True,
    )

    work = tmp_path / "work"
    work.mkdir()
    git(work, "init", "-b", "haupt")
    git(work, "config", "user.email", "test@example.com")
    git(work, "config", "user.name", "Test")
    git(work, "remote", "add", "origin", str(remote))
    (work / "README.md").write_text("start\n")
    git(work, "add", "README.md")
    git(work, "commit", "-m", "erster")
    git(work, "push", "-u", "origin", "haupt")
    return work


# ---------------------------------------------------------------------------
#  Der Filter
# ---------------------------------------------------------------------------
class TestScrub:
    def test_entfernt_zugangsdaten(self) -> None:
        sauber = scrub(
            {
                "name": "Kandidat",
                "api_key": "abc",
                "apiKey": "abc",
                "BYBIT_API_SECRET": "geheim",
                "token": "t",
                "password": "p",
            }
        )

        assert sauber == {"name": "Kandidat"}

    def test_entfernt_kontostaende(self) -> None:
        """Prozent und R sagen alles, was fuer die Bewertung zaehlt.

        Der Kontostand sagt daruber hinaus nur etwas ueber den Nutzer - und
        das Repository ist oeffentlich.
        """
        sauber = scrub({"rendite_pct": 12.0, "balance": 500, "wallet_equity": 480})

        assert sauber == {"rendite_pct": 12.0}

    def test_wirkt_auch_tief_verschachtelt(self) -> None:
        sauber = scrub(
            {
                "kandidaten": [
                    {"name": "A", "gates": [{"wert": 1.0, "order_id": "x"}]},
                ]
            }
        )

        assert sauber["kandidaten"][0]["gates"][0] == {"wert": 1.0}

    def test_laesst_harmlose_felder_stehen(self) -> None:
        payload = {
            "sharpe": -0.41,
            "erwartung_r": -0.145,
            "trefferquote": 0.268,
            "hypothese": "Ausbruch ohne Long-Ueberhitzung",
        }

        assert scrub(payload) == payload


class TestWriteReport:
    def test_schreibt_und_filtert(self, tmp_path: Path) -> None:
        file = write_report({"sharpe": 1.0, "api_key": "x"}, root=tmp_path)

        inhalt = json.loads(file.read_text())
        assert inhalt == {"sharpe": 1.0}
        assert file.parent == tmp_path / "reports" / "zulassung"

    def test_ueberschreibt_nichts(self, tmp_path: Path) -> None:
        """Der Verlauf ueber Wochen ist der eigentliche Wert.

        Auch zwei Laeufe in derselben Sekunde muessen beide erhalten bleiben -
        sonst haengt es an der Uhr, ob ein fertig gerechneter Bericht existiert.
        """
        erste = write_report({"lauf": 1}, root=tmp_path)
        zweite = write_report({"lauf": 2}, root=tmp_path)

        assert erste != zweite
        assert json.loads(erste.read_text()) == {"lauf": 1}
        assert json.loads(zweite.read_text()) == {"lauf": 2}


# ---------------------------------------------------------------------------
#  Die Uebermittlung
# ---------------------------------------------------------------------------
class TestPublish:
    def test_sendet_den_bericht(self, repo: Path) -> None:
        file = write_report({"sharpe": 1.0}, root=repo)

        result = publish([file], root=repo, message="Bericht")

        assert result.status is PublishStatus.PUSHED, result.detail
        entfernt = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", "origin/haupt"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert "reports/zulassung/" in entfernt

    def test_nimmt_keine_fremden_aenderungen_mit(self, repo: Path) -> None:
        """Der wichtigste Test der Datei.

        Ein automatischer Commit, der ``git add -A`` benutzt, nimmt mit, was
        gerade daneben liegt - halbfertige Arbeit, private Notizen, im
        schlimmsten Fall eine Datei mit Zugangsdaten, die noch nicht in
        ``.gitignore`` steht. Hier liegt beides nebeneinander, und nur der
        Bericht darf gehen.
        """
        (repo / "README.md").write_text("halbfertige Aenderung\n")
        (repo / "geheim.txt").write_text("nicht veroeffentlichen\n")
        file = write_report({"sharpe": 1.0}, root=repo)

        publish([file], root=repo, message="Bericht")

        gesendet = subprocess.run(
            ["git", "show", "--name-only", "--format=", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert "reports/" in gesendet
        assert "README.md" not in gesendet
        assert "geheim.txt" not in gesendet

    def test_zweimal_dasselbe_ist_kein_fehler(self, repo: Path) -> None:
        file = write_report({"sharpe": 1.0}, root=repo)
        publish([file], root=repo, message="Bericht")

        nochmal = publish([file], root=repo, message="Bericht")

        assert nochmal.status is PublishStatus.NOTHING

    def test_ohne_git_identitaet_geht_es_trotzdem(self, repo: Path) -> None:
        """Auf einem frisch eingerichteten Rechner ist sie nicht gesetzt.

        ``git commit`` bricht dann mit einer Aufforderung ab, die niemand
        erwartet - und der Bericht kaeme nie an.
        """
        git(repo, "config", "--unset", "user.email")
        git(repo, "config", "--unset", "user.name")
        file = write_report({"sharpe": 1.0}, root=repo)

        result = publish([file], root=repo, message="Bericht")

        assert result.status is PublishStatus.PUSHED, result.detail

    def test_abgeschaltet_tut_nichts(self, repo: Path) -> None:
        file = write_report({"sharpe": 1.0}, root=repo)

        result = publish([file], root=repo, message="B", enabled=False)

        assert result.status is PublishStatus.DISABLED

    def test_ohne_repository_kein_absturz(self, tmp_path: Path) -> None:
        file = write_report({"sharpe": 1.0}, root=tmp_path)

        result = publish([file], root=tmp_path, message="B")

        assert result.status is PublishStatus.NO_REPO

    def test_unerreichbares_remote_bricht_nicht_ab(self, repo: Path) -> None:
        """Ohne Netz muss der Bericht wenigstens lokal festgehalten werden.

        Beim naechsten gelungenen Lauf geht er dann mit. Eine Ausnahme an
        dieser Stelle wuerde einen fertig gerechneten Zulassungslauf
        vernichten - wegen eines Verbindungsproblems.
        """
        git(repo, "remote", "set-url", "origin", "https://127.0.0.1:1/nichts.git")
        file = write_report({"sharpe": 1.0}, root=repo)

        result = publish([file], root=repo, message="Bericht")

        assert result.status is PublishStatus.COMMITTED
        assert result.detail
        # Lokal festgehalten heisst: beim naechsten Mal ist er dabei.
        stand = subprocess.run(
            ["git", "show", "--name-only", "--format=", "HEAD"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        assert "reports/" in stand

    def test_datei_ausserhalb_des_repos_wird_nicht_gesendet(
        self, repo: Path, tmp_path: Path
    ) -> None:
        fremd = tmp_path / "woanders.json"
        fremd.write_text("{}")

        result = publish([fremd], root=repo, message="B")

        assert result.status is PublishStatus.NOTHING

    def test_rebase_konflikt_laesst_kein_chaos_zurueck(
        self, repo: Path, tmp_path: Path
    ) -> None:
        """Der Zustand, aus dem sich ein Laie nicht mehr befreit.

        Beide Seiten haben dieselbe Datei geaendert. Ein Rebase bleibt dann
        mitten drin stehen und hinterlaesst Konfliktmarken im
        Arbeitsverzeichnis. Ein automatischer Vorgang, der das anrichtet, ist
        schlimmer als einer, der den Bericht einfach nicht sendet.
        """
        zweit = tmp_path / "zweit"
        subprocess.run(
            ["git", "clone", "-q", str(tmp_path / "remote.git"), str(zweit)],
            check=True,
            capture_output=True,
        )
        git(zweit, "config", "user.email", "b@example.com")
        git(zweit, "config", "user.name", "B")
        (zweit / "README.md").write_text("von der anderen Seite\n")
        git(zweit, "commit", "-am", "andere Seite")
        git(zweit, "push", "-q", "origin", "haupt")

        (repo / "README.md").write_text("von hier\n")
        git(repo, "commit", "-am", "hier")
        file = write_report({"sharpe": 1.0}, root=repo)

        result = publish([file], root=repo, message="Bericht")

        assert result.status is PublishStatus.COMMITTED
        assert not (repo / ".git" / "rebase-merge").exists()
        assert not (repo / ".git" / "rebase-apply").exists()
        assert "<<<<<<<" not in (repo / "README.md").read_text()
