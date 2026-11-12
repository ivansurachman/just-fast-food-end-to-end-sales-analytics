from datetime import date
from importlib import resources
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, Field, model_validator

Probability = Annotated[float, Field(ge=0, le=1)]
PositiveFloat = Annotated[float, Field(gt=0)]


class City(BaseModel):
    name: str
    region: str
    timezone: str
    weight: float


class Region(BaseModel):
    volume_mult: float
    online_share: Probability


class Channel(BaseModel):
    channel_id: str
    order_origin: Literal["offline", "online"]
    platform: str
    service_type: Literal["dine_in", "takeaway", "delivery"]
    mix_weight: float
    commission_rate: float = 0.0
    platform_ref_prefix: str = ""


class MenuItem(BaseModel):
    menu_item_id: str
    item_name: str
    category: Literal["main", "side", "dessert", "beverage"]
    unit_price: int
    unit_cost: int
    popularity: float


class Promo(BaseModel):
    promo_id: str
    promo_name: str
    discount_type: Literal["percent", "fixed"]
    discount_value: int
    min_order_amount: int
    max_discount_amount: int
    valid_from: date
    valid_to: date
    channels: list[str]
    weekdays: list[int]
    use_probability: Probability


class Peak(BaseModel):
    center: float
    sigma: float
    weight: float


class VolumeConfig(BaseModel):
    base_orders_per_branch_day: Annotated[int, Field(gt=0)]
    weekday_factors: list[float]
    noise_sigma: float
    size_tiers: dict[str, float]
    size_tier_probs: dict[str, float]
    cloud_kitchen_share: float
    cloud_kitchen_mult: float


class TimeConfig(BaseModel):
    open_hour: int
    close_hour: int
    peaks: dict[str, list[Peak]]


class BasketConfig(BaseModel):
    food_extra_lines_lambda: float
    max_food_lines: int
    beverage_attach_offline: Probability
    beverage_attach_online: Probability
    qty_probs: list[float]


class LifecycleConfig(BaseModel):
    cancel_prob_online: Probability
    cancel_prob_offline: Probability
    refund_prob_online: Probability
    refund_prob_offline: Probability
    refund_lag_geometric_p: float
    refund_max_lag_days: int
    refund_extra_minutes_min: int
    refund_extra_minutes_max: int


class DefectConfig(BaseModel):
    enabled: bool
    duplicate_row_rate: Probability
    late_sync_branch_day_rate: Probability
    late_sync_cutoff_hour_min: int
    late_sync_cutoff_hour_max: int
    branch_dropout_rate: Probability
    dirty_payment_rate: Probability
    null_platform_ref_rate: Probability
    total_mismatch_rate: Probability
    unknown_menu_rate: Probability


class Config(BaseModel):
    seed: Annotated[int, Field(ge=0)]
    scale: PositiveFloat
    n_branches: Annotated[int, Field(ge=1)]
    branch_open_start: date
    branch_open_end: date
    cities: list[City]
    regions: dict[str, Region]
    channels: list[Channel]
    payment_mix_offline: dict[str, float]
    menu: list[MenuItem]
    promos: list[Promo]
    volume: VolumeConfig
    time: TimeConfig
    basket: BasketConfig
    lifecycle: LifecycleConfig
    defects: DefectConfig

    @model_validator(mode="after")
    def _check_consistency(self) -> "Config":
        if len(self.volume.weekday_factors) != 7:
            raise ValueError("weekday_factors needs 7 values (Mon..Sun)")
        channel_ids = {c.channel_id for c in self.channels}
        for promo in self.promos:
            unknown = set(promo.channels) - channel_ids
            if unknown:
                raise ValueError(f"{promo.promo_id} references unknown channels {unknown}")
        if {c.region for c in self.cities} - set(self.regions):
            raise ValueError("every city region needs an entry in 'regions'")
        for key in ("offline_weekday", "offline_weekend", "online_weekday", "online_weekend"):
            if key not in self.time.peaks:
                raise ValueError(f"time.peaks missing '{key}'")
        if not {"main", "beverage"} <= {m.category for m in self.menu}:
            raise ValueError("menu needs at least one main and one beverage item")
        return self


def load_config(path: Path | None = None) -> Config:
    """Load the packaged default config, or a user file that replaces it entirely."""
    if path is None:
        text = resources.files("jff_gen").joinpath("default_config.yaml").read_text("utf-8")
    else:
        text = path.read_text("utf-8")
    return Config.model_validate(yaml.safe_load(text))
