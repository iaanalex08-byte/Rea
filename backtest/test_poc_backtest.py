"""Pruebas de escenarios del motor: python3 -m pytest backtest/ (o python3 backtest/test_poc_backtest.py)"""
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import poc_backtest as pb  # noqa: E402

TZ = "Etc/GMT+6"


def make_day(after, trend_up=True, date="2025-03-04"):
    """Día sintético de velas de 3 min. Perfil 9:00-9:12 en 99.75-100.25 -> POC 100.00.
    `after` = lista de (high, low) desde la vela de 9:15 en adelante."""
    rows = []
    t = pd.Timestamp(f"{date} 00:00", tz=TZ)
    first_open = 90 if trend_up else 110
    while t.hour < 9:  # tendencia previa
        rows.append((t, first_open, 100, 100, 100, 10))
        t += pd.Timedelta(minutes=3)
    for _ in range(4):  # perfil
        rows.append((t, 100, 100.25, 99.75, 100, 1000))
        t += pd.Timedelta(minutes=3)
    rows.append((t, 100, 100.25, 99.75, 100, 10))  # 9:12 (calcula POC)
    t += pd.Timedelta(minutes=3)
    for h, l in after:
        rows.append((t, (h + l) / 2, h, l, (h + l) / 2, 10))
        t += pd.Timedelta(minutes=3)
    # vela del día siguiente para cerrar el día
    rows.append((pd.Timestamp(date, tz=TZ) + pd.Timedelta(days=1), 100, 100, 100, 100, 1))
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close", "volume"]).set_index("ts")
    return df


def result(after, trend_up=True):
    a = pb.parse_args(["x.csv", "--sl", "9", "--rr", "2.5"])
    tr, _ = pb.run(make_day(after, trend_up), a)
    return tr


# Compra: ruptura (mínimo > 100), retroceso (toca 100), luego escenarios. SL 91, TP1 109, TP2 122.5
BRK_RETEST = [(102, 101), (101, 99.5)]


def test_poc_and_levels():
    tr = result(BRK_RETEST + [(101, 100.5)])
    t = tr.iloc[0]
    assert (t.entry, t.sl, t.tp1, t.tp2) == (100.0, 91.0, 109.0, 122.5)
    assert t.dir == "COMPRA"


def test_loss():
    tr = result(BRK_RETEST + [(101, 90)])
    assert tr.iloc[0].result == "PERDIDA" and tr.iloc[0].pts == -9


def test_win():
    tr = result(BRK_RETEST + [(110, 101), (123, 105)])
    assert tr.iloc[0].result == "GANADA" and tr.iloc[0].pts == 4.5 + 11.25


def test_partial_then_be():
    tr = result(BRK_RETEST + [(110, 101), (105, 99.75)])
    assert tr.iloc[0].result == "PARCIAL + BE" and tr.iloc[0].pts == 4.5


def test_same_bar_sl_and_tp1_is_loss():
    tr = result(BRK_RETEST + [(110, 90)])
    assert tr.iloc[0].result == "PERDIDA"


def test_same_bar_be_and_tp2_after_partial_is_be():
    tr = result(BRK_RETEST + [(110, 101), (123, 99)])
    assert tr.iloc[0].result == "PARCIAL + BE"


def test_unresolved_keeps_partial():
    tr = result(BRK_RETEST + [(110, 101)])
    assert tr.iloc[0].result == "SIN RESOLVER" and tr.iloc[0].pts == 4.5


def test_entry_bar_not_evaluated():
    # La vela de entrada toca el SL, pero no se evalúa; la siguiente gana
    tr = result([(102, 101), (101, 90), (110, 101), (123, 105)])
    assert tr.iloc[0].result == "GANADA"


def test_sell_side():
    tr = result([(99, 98), (100.5, 99)] + [(99, 91), (95, 77)], trend_up=False)
    t = tr.iloc[0]
    assert t.dir == "VENTA" and (t.sl, t.tp1, t.tp2) == (109.0, 91.0, 77.5) and t.result == "GANADA"


def test_no_breakout_no_trade():
    tr = result([(100.5, 99.5)] * 5)
    assert tr.empty


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
