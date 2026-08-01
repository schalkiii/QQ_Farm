from core.strategies.base import BaseStrategy
from core.strategies.popup import PopupStrategy
from core.strategies.harvest import HarvestStrategy
from core.strategies.maintain import MaintainStrategy
from core.strategies.plant import PlantStrategy
from core.strategies.expand import ExpandStrategy
from core.strategies.task import TaskStrategy
from core.strategies.friend import FriendStrategy
from core.strategies.gift import GiftStrategy
from core.strategies.targeted_steal import TargetedStealStrategy
from core.strategies.targeted_prank import TargetedPrankStrategy

# 包级公开 API：供 `from core.strategies import X` 使用，避免被 lint 误判为未用导入
__all__ = [
    "BaseStrategy",
    "PopupStrategy",
    "HarvestStrategy",
    "MaintainStrategy",
    "PlantStrategy",
    "ExpandStrategy",
    "TaskStrategy",
    "FriendStrategy",
    "GiftStrategy",
    "TargetedStealStrategy",
    "TargetedPrankStrategy",
]
