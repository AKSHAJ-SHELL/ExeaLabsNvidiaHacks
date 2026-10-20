"""GR00T N1.7 modality config for the Arrival sim Panda (7-DoF arm + 1 gripper), fixed base.

Pass it to Isaac-GR00T with `--embodiment-tag NEW_EMBODIMENT --modality-config-path <this file>`.
Keys must be a subset of meta/modality.json of datasets written by `python -m arrival sim`
(tests/test_gr00t_config.py checks this). Dataset actions are absolute joint targets at 20 fps;
the arm is trained as deltas from the current state and the gripper as an absolute target.

8 vs 11 floats (L13): every `sim` dataset has 11-float state and action rows, [0:7] arm, [7:8] gripper and
[8:11] the base x, y, yaw in the room frame. This config reads only the first 8 and leaves the base slice out, which
is what you want for the default fixed base (its three columns are the parked pose, constant, so a model has
nothing to learn from them) and for 8-float datasets written before the base slice existed or by `demo`.
To train a mobile base use arrival_panda_mobile_config.py, which adds the `base` key.
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
