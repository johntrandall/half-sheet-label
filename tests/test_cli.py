"""CLI helpers: slot-name normalization (tray-2 ≈ Tray2 across drivers)."""
from __future__ import annotations

import pytest

from half_sheet_label.cli import _norm_slot, _resolve_slot


@pytest.mark.parametrize("a,b", [
    ("tray-2", "Tray2"), ("tray-2", "tray2"), ("by-pass-tray", "ByPassTray"),
    ("Tray1", "tray-1"), ("MP Tray", "mptray"),
])
def test_norm_slot_equivalences(a, b):
    assert _norm_slot(a) == _norm_slot(b)


def test_resolve_slot_matches_everywhere_driver_casing(monkeypatch):
    # default label_slot "tray-2" must resolve to a driver that exposes "Tray2"
    monkeypatch.setattr("half_sheet_label.cli._printer_slots",
                        lambda p: ["Auto", "ByPassTray", "Tray1", "Tray2"])
    assert _resolve_slot("Athena", "tray-2") == "Tray2"


def test_resolve_slot_falls_back_to_bypass(monkeypatch, capsys):
    monkeypatch.setattr("half_sheet_label.cli._printer_slots",
                        lambda p: ["auto", "by-pass-tray", "tray-1"])
    assert _resolve_slot("P", "tray-2") == "by-pass-tray"
    assert "not on P" in capsys.readouterr().out


def test_resolve_slot_unknown_printer_passthrough(monkeypatch):
    monkeypatch.setattr("half_sheet_label.cli._printer_slots", lambda p: None)
    assert _resolve_slot("P", "tray-2") == "tray-2"
