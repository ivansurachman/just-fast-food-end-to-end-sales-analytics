from jff_gen.config import Config
from jff_gen.context import Context
from jff_gen.dimensions import DIMENSION_BUILDERS, build_dimensions
from jff_gen.seeding import make_rng


def test_same_keys_give_same_stream() -> None:
    assert make_rng(1, "a", 2, 3).random() == make_rng(1, "a", 2, 3).random()


def test_different_stream_or_key_gives_different_values() -> None:
    base = make_rng(1, "a", 2).random()
    assert base != make_rng(1, "b", 2).random()
    assert base != make_rng(1, "a", 3).random()
    assert base != make_rng(2, "a", 2).random()


def test_dimensions_are_deterministic(cfg: Config) -> None:
    first, second = build_dimensions(cfg), build_dimensions(cfg)
    assert first.branches.equals(second.branches)


def test_branch_dimension_shape(ctx: Context) -> None:
    branches = ctx.dims.branches
    assert branches["branch_id"].is_unique
    assert len(branches) == ctx.cfg.n_branches
    assert set(branches["timezone"]) <= {
        "Asia/Jakarta",
        "Asia/Pontianak",
        "Asia/Makassar",
        "Asia/Jayapura",
    }
    assert set(branches["outlet_type"]) <= {"restaurant", "cloud_kitchen"}


def test_menu_margins_are_positive(ctx: Context) -> None:
    menu = ctx.dims.menu
    assert (menu["unit_price"] > menu["unit_cost"]).all()


def test_channels_split_origin_and_platform(ctx: Context) -> None:
    channels = ctx.dims.channels.set_index("channel_id")
    assert (channels.loc[channels["order_origin"] == "offline", "commission_rate"] == 0).all()
    assert (channels.loc[channels["order_origin"] == "online", "commission_rate"] > 0).all()


def test_each_dimension_generator_runs_on_its_own(cfg: Config) -> None:
    for name, builder in DIMENSION_BUILDERS.items():
        frame = builder(cfg)
        assert not frame.empty, name
