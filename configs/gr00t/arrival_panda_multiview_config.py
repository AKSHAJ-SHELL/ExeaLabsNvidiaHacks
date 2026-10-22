"""Optional three-view GR00T config for fixed-base `arrival sim --exocentric` datasets.

Reads synchronized ego, wrist and external overview frames at the same observation index.
Same state/action layout as arrival_panda_config.py (arm deltas, absolute gripper).
Load this file instead of the default config: both register NEW_EMBODIMENT.
Offline key/schema checks only; no three-view GR00T training or inference has been measured.
"""

from gr00t.configs.data.embodiment_configs import register_modality_config
from gr00t.data.embodiment_tags import EmbodimentTag
from gr00t.data.types import (
    ActionConfig,
    ActionFormat,
    ActionRepresentation,
    ActionType,
    ModalityConfig,
)

arrival_panda_multiview_config = {
    "video": ModalityConfig(
        delta_indices=[0],
        modality_keys=["ego_view", "wrist", "overview"],
    ),
    "state": ModalityConfig(
        delta_indices=[0],
        modality_keys=["single_arm", "gripper"],
    ),
    "action": ModalityConfig(
        delta_indices=list(range(0, 16)),
        modality_keys=["single_arm", "gripper"],
        action_configs=[
            ActionConfig(rep=ActionRepresentation.RELATIVE, type=ActionType.NON_EEF, format=ActionFormat.DEFAULT),
            ActionConfig(rep=ActionRepresentation.ABSOLUTE, type=ActionType.NON_EEF, format=ActionFormat.DEFAULT),
        ],
    ),
    "language": ModalityConfig(
        delta_indices=[0],
        modality_keys=["annotation.human.task_description"],
    ),
}

register_modality_config(arrival_panda_multiview_config, embodiment_tag=EmbodimentTag.NEW_EMBODIMENT)
