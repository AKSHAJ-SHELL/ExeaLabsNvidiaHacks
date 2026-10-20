"""GR00T N1.7 modality config for the Arrival sim Panda on the mobile base (`arrival sim --base mobile`).

Same as arrival_panda_config.py plus a `base` key: state and action [8:11] are the base x, y (m) and yaw (rad) in the
room frame, and the action is the commanded base pose, absolute (the expert drives it at up to 0.3 m/s and 0.5 rad/s,
so consecutive targets are close to the state). Use it only on datasets written with `--base mobile`; a fixed-base
dataset has constant base columns, which give the normaliser a zero range, and should use arrival_panda_config.py.

Pass it to Isaac-GR00T with `--embodiment-tag NEW_EMBODIMENT --modality-config-path <this file>`; only one of the two
config files can be loaded per run (both register NEW_EMBODIMENT). tests/test_gr00t_config.py checks the keys against a
freshly written mobile dataset.
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

arrival_panda_mobile_config = {
    "video": ModalityConfig(
        delta_indices=[0],
        modality_keys=["ego_view", "wrist"],
    ),
    "state": ModalityConfig(
        delta_indices=[0],
        modality_keys=["single_arm", "gripper", "base"],
    ),
    "action": ModalityConfig(
        delta_indices=list(range(0, 16)),
        modality_keys=["single_arm", "gripper", "base"],
        action_configs=[
            ActionConfig(rep=ActionRepresentation.RELATIVE, type=ActionType.NON_EEF, format=ActionFormat.DEFAULT),
            ActionConfig(rep=ActionRepresentation.ABSOLUTE, type=ActionType.NON_EEF, format=ActionFormat.DEFAULT),
            ActionConfig(rep=ActionRepresentation.ABSOLUTE, type=ActionType.NON_EEF, format=ActionFormat.DEFAULT),
        ],
    ),
    "language": ModalityConfig(
        delta_indices=[0],
        modality_keys=["annotation.human.task_description"],
    ),
}

register_modality_config(arrival_panda_mobile_config, embodiment_tag=EmbodimentTag.NEW_EMBODIMENT)
