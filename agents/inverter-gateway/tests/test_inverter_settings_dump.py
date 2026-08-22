from inverter_settings_dump import SETTINGS_COUNT, render

# Nilai sebenarnya yang terbaca dari inverter pada 2026-08-23.
OBSERVED = [
    3, 100, 500, 1000, 50, 220, 2, 120,
    141, 139, 170, 154, 149, 119, 124, 129,
    124, 0, 129, 125, 3876, 3930, 6229, 1990,
    0, 1, 2, 0, 0, 2560, 25605, 21775,
]


def test_observed_snapshot_has_expected_width() -> None:
    assert len(OBSERVED) == SETTINGS_COUNT


def test_confirmed_registers_are_marked(capsys) -> None:
    render(OBSERVED)
    output = capsys.readouterr().out
    # 0x4003=1000 W, 0x4004=50 Hz, 0x4005=220 V sudah cocok dengan data kita.
    assert "1000 W" in output
    assert "50 Hz" in output
    assert "220 V" in output
    assert output.count("cocok dengan data kita") == 3


def test_menu_confirmed_registers_cite_their_menu_code(capsys) -> None:
    """A2 dan A7 dicocokkan langsung ke menu inverter, jadi ditandai terbukti."""
    render(OBSERVED)
    output = capsys.readouterr().out
    assert "28.2 V  <- TERBUKTI: A2" in output  # 0x4008 = 141
    assert "25.0 V  <- TERBUKTI: A7" in output  # 0x4013 = 125


def test_ambiguous_a6_is_not_claimed_on_either_register(capsys) -> None:
    """Dua register bernilai 129; tak satu pun boleh diklaim sebagai A6."""
    render(OBSERVED)
    output = capsys.readouterr().out
    assert output.count("A6?") == 2
    assert "TERBUKTI: A6" not in output


def test_unmatched_registers_keep_scale_but_not_meaning(capsys) -> None:
    """Skala sudah terbukti; artinya belum, dan itu harus terbaca jelas."""
    render(OBSERVED)
    output = capsys.readouterr().out
    assert "23.8 V  (skala terbukti, arti belum)" in output  # 0x400D = 119


def test_zero_registers_render_without_bogus_scaling(capsys) -> None:
    render(OBSERVED)
    output = capsys.readouterr().out
    for line in output.splitlines():
        if line.strip().startswith("0x4018"):
            assert line.rstrip().endswith("-")


def test_zero_inside_battery_range_is_not_called_a_threshold(capsys) -> None:
    """0x4011 bernilai 0; nol bukan ambang tegangan yang masuk akal."""
    render(OBSERVED)
    output = capsys.readouterr().out
    for line in output.splitlines():
        if line.strip().startswith("0x4011"):
            assert "DUGAAN" not in line
            assert line.rstrip().endswith("-")
    assert "0.0 V" not in output


def test_render_covers_every_register(capsys) -> None:
    render(OBSERVED)
    output = capsys.readouterr().out
    for index in range(SETTINGS_COUNT):
        assert f"0x{0x4000 + index:04X}" in output
