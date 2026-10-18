"""GR00T N1.7 modality config for the Arrival sim Panda (7-DoF arm + 1 gripper).

Pass it to Isaac-GR00T with `--embodiment-tag NEW_EMBODIMENT --modality-config-path <this file>`.
Keys must match meta/modality.json of datasets written by `python -m arrival sim`
(tests/test_gr00t_config.py checks this). Dataset actions are absolute joint targets at 20 fps;
the arm is trained as deltas from the current state and the gripper as an absolute target.
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

arrival_panda_config = {
    "video": ModalityConfig(
        delta_indices=[0],
        modality_keys=["ego_view", "wrist"],
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

register_modality_config(arrival_panda_config, embodiment_tag=EmbodimentTag.NEW_EMBODIMENT)
