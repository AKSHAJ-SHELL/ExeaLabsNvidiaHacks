"""Kinematic walking people (mocap capsules) on seeded waypoint loops through free floor."""

from __future__ import annotations

import numpy as np


def person_xml(i: int) -> str:
    shirt = ["0.7 0.2 0.2 1", "0.2 0.4 0.7 1", "0.3 0.6 0.3 1"][i % 3]
    nc = 'contype="0" conaffinity="0"'
    return (f'<body name="person_{i}" mocap="true" pos="0 0 0">'
            f'<geom type="capsule" size="0.06" fromto="0.0 0.08 0.05 0.0 0.08 0.85" rgba="0.2 0.2 0.3 1" {nc}/>'
            f'<geom type="capsule" size="0.06" fromto="0.0 -0.08 0.05 0.0 -0.08 0.85" rgba="0.2 0.2 0.3 1" {nc}/>'
            f'<geom type="capsule" size="0.17" fromto="0 0 1.0 0 0 1.4" rgba="{shirt}" {nc}/>'
            f'<geom type="capsule" size="0.045" fromto="0 0.22 1.45 0 0.24 0.95" rgba="{shirt}" {nc}/>'
            f'<geom type="capsule" size="0.045" fromto="0 -0.22 1.45 0 -0.24 0.95" rgba="{shirt}" {nc}/>'
            f'<geom type="sphere" size="0.11" pos="0 0 1.7" rgba="0.85 0.68 0.55 1" {nc}/></body>')


class Walkers:
    """Each person loops through random waypoints in a free-floor rectangle at ~0.8 m/s."""

    def __init__(self, n: int, floor: tuple[float, float, float, float], seed: int = 0, speed: float = 0.8):
        rng = np.random.default_rng(seed)
        x0, y0, x1, y1 = floor
        self.paths = [rng.uniform([x0, y0], [x1, y1], size=(4, 2)) for _ in range(n)]
        self.pos = [p[0].copy() for p in self.paths]
        self.idx = [1] * n
        self.speed = speed

    def step(self, model, data, dt: float) -> list[list[float]]:
        out = []
        for i, path in enumerate(self.paths):
            goal = path[self.idx[i] % len(path)]
            d = goal - self.pos[i]
            dist = float(np.linalg.norm(d))
            if dist < 0.05:
                self.idx[i] += 1
            else:
                self.pos[i] += d / dist * min(dist, self.speed * dt)
            yaw = np.arctan2(d[1], d[0])
            mid = model.body(f"person_{i}").mocapid[0]
            data.mocap_pos[mid] = [self.pos[i][0], self.pos[i][1], 0.0]
            data.mocap_quat[mid] = [np.cos(yaw / 2), 0, 0, np.sin(yaw / 2)]
            out.append([float(self.pos[i][0]), float(self.pos[i][1])])
        return out
