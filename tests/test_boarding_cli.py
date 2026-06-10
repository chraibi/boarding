from boarding.cli import build_parser


def test_cli_defaults_to_full_method_set():
    args = build_parser().parse_args([])
    assert "steffen_perfect" in args.methods
    assert "back_to_front" in args.methods
    assert args.seeds == 20


def test_cli_rejects_unknown_method():
    import pytest
    with pytest.raises(SystemExit):
        build_parser().parse_args(["--methods", "not_a_method"])
