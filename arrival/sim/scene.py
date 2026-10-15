"""Twin JSON -> MJCF: walls, floor, counters with drawers + hinged cabinet doors, sink basin,
stove, fridge with hinged door, free-body objects, people, Panda-like arm, cameras."""

from __future__ import annotations

import math

from arrival.sim import people, robot

LIGHT = {"dim": 0.35, "neutral": 0.7, "bright": 1.0}
TOP_T = 0.04
CARCASS_H = 0.70  # cabinet body below the counter top (sink basin sits between this and the top)
DRAWER = 'contype="2" conaffinity="2"'  # moving parts collide with the robot, not with their carcass
OBJ = {"mug": ("cylinder", 0.30, "0.85 0.3 0.2 1"), "bowl": ("cylinder", 0.25, "0.9 0.9 0.8 1"),
       "sponge": ("box", 0.03, "0.95 0.85 0.2 1")}


def _box(name, pos, size, rgba, extra=""):
    return (f'<geom name="{name}" type="box" pos="{pos[0]:.4f} {pos[1]:.4f} {pos[2]:.4f}" '
            f'size="{size[0] / 2:.4f} {size[1] / 2:.4f} {size[2] / 2:.4f}" rgba="{rgba}" {extra}/>')


def _sinks_in(counter: dict, sinks: list[dict]) -> list[dict]:
    (cx, cy, _), (sx, sy, _) = counter["position"], counter["size"]
    return [s for s in sinks if abs(s["position"][0] - cx) < sx / 2 and abs(s["position"][1] - cy) < sy / 2]


def drawer_x(c: dict, fixtures: list[dict]) -> float:
    """Local x of the drawer stack: left quarter, or the middle if a tall fixture overlaps the left quarter."""
    x = c["position"][0] - c["size"][0] / 4
    tall = [f for f in fixtures if f["type"].startswith("fridge")]
    if any(abs(f["position"][0] - x) < f["size"][0] / 2 + DRAWER_W / 2 for f in tall):
        return 0.0
    return -c["size"][0] / 4


DRAWER_W = 0.5


def door_w(c: dict, fixtures: list[dict]) -> float:
    """Cabinet door width: right half of the counter, shrunk so it never covers the drawer stack."""
    sx = c["size"][0]
    left = max(0.02, drawer_x(c, fixtures) + DRAWER_W / 2 + 0.02)
    return sx / 2 - 0.02 - left


def counter_xml(c: dict, sinks: list[dict], fixtures: list[dict] = ()) -> str:
    """Counter in its local frame (+y local = front). Top slab is split around any sink hole."""
    (cx, cy, _), (sx, sy, h) = c["position"], c["size"]
    cid, yaw = c["id"], c.get("yaw", 0.0)
    g = [_box(f"{cid}_carcass", (0, 0, CARCASS_H / 2), (sx, sy - 0.04, CARCASS_H), "0.55 0.42 0.3 1")]
    holes = [(s["position"][0] - cx, s["size"][0], s["size"][1], s) for s in _sinks_in(c, sinks)]
    zt = h - TOP_T / 2
    top = "0.82 0.82 0.8 1"
    if not holes:
        g.append(_box(f"{cid}_top", (0, 0, zt), (sx, sy, TOP_T), top))
    for hx, hw, hd, s in holes[:1]:
        lx0, lx1 = -sx / 2, hx - hw / 2
        rx0, rx1 = hx + hw / 2, sx / 2
        g.append(_box(f"{cid}_top_l", ((lx0 + lx1) / 2, 0, zt), (lx1 - lx0, sy, TOP_T), top))
        g.append(_box(f"{cid}_top_r", ((rx0 + rx1) / 2, 0, zt), (rx1 - rx0, sy, TOP_T), top))
        rim = (sy - hd) / 2
        g.append(_box(f"{cid}_top_f", (hx, sy / 2 - rim / 2, zt), (hw, rim, TOP_T), top))
        g.append(_box(f"{cid}_top_b", (hx, -sy / 2 + rim / 2, zt), (hw, rim, TOP_T), top))
        # basin: bottom + 4 thin walls, from carcass top to counter top
        bz0, bt = CARCASS_H + 0.01, 0.01
        wall_h = h - bz0
        steel = "0.6 0.62 0.65 1"
        sid = s["id"]
        g.append(_box(f"{sid}_bottom", (hx, 0, bz0), (hw, hd, 0.02), steel))
        for k, (px, py, wx, wy) in enumerate([(hx - hw / 2 + bt / 2, 0, bt, hd), (hx + hw / 2 - bt / 2, 0, bt, hd),
                                              (hx, hd / 2 - bt / 2, hw, bt), (hx, -hd / 2 + bt / 2, hw, bt)]):
            g.append(_box(f"{sid}_wall{k}", (px, py, bz0 + wall_h / 2), (wx, wy, wall_h), steel))
    body = [f'<body name="{cid}" pos="{cx} {cy} 0" euler="0 0 {yaw}">' + "".join(g)]
    # drawers (slide along local +y) in the left half; hinged door cabinets in the right half
    front = sy / 2 - 0.02
    n_dr = 2
    for k in range(n_dr):
        dx = drawer_x(c, list(fixtures))
        dz = CARCASS_H - 0.01 - k * 0.24  # top drawer sits in the band just under the counter top
        body.append(
            f'<body name="{cid}_drawer{k}" pos="{dx:.3f} {front:.3f} {dz:.3f}">'
            f'<joint name="{cid}_drawer{k}" type="slide" axis="0 1 0" range="0 0.4" damping="5" frictionloss="0.5"/>'
            f'<inertial pos="0 -0.2 0" mass="1.5" diaginertia="0.02 0.02 0.02"/>'
            + _box(f"{cid}_drawer{k}_front", (0, 0.01, 0), (DRAWER_W, 0.02, 0.18), "0.65 0.5 0.36 1", DRAWER)
            + _box(f"{cid}_drawer{k}_tray", (0, -0.2, -0.07), (DRAWER_W - 0.04, 0.38, 0.02), "0.6 0.46 0.33 1", DRAWER)
            + f'<geom name="{cid}_drawer{k}_handle" type="capsule" size="0.012" fromto="0 0.07 -0.05 0 0.07 0.05" '
              f'rgba="0.3 0.3 0.3 1" {DRAWER}/>'
            + f'<geom type="box" size="0.01 0.035 0.01" pos="0 0.035 0.04" rgba="0.3 0.3 0.3 1" {DRAWER}/>'
            + f'<geom type="box" size="0.01 0.035 0.01" pos="0 0.035 -0.04" rgba="0.3 0.3 0.3 1" {DRAWER}/>'
            + f'<site name="{cid}_drawer{k}_handle" pos="0 0.07 0.0" size="0.01"/></body>')
    dw = door_w(c, list(fixtures))
    body.append(
        f'<body name="{cid}_door" pos="{sx / 2 - 0.02:.3f} {front + 0.01:.3f} 0.36">'
        f'<joint name="{cid}_door" type="hinge" axis="0 0 -1" range="0 1.9" damping="2" frictionloss="0.2"/>'
        f'<inertial pos="{-dw / 2:.3f} 0 0" mass="2" diaginertia="0.05 0.05 0.05"/>'
        + _box(f"{cid}_door_panel", (-dw / 2, 0.01, 0), (dw, 0.02, 0.6), "0.65 0.5 0.36 1", DRAWER)
        + f'<geom name="{cid}_door_handle" type="capsule" size="0.012" fromto="{-dw + 0.06:.3f} 0.05 0.1 '
          f'{-dw + 0.06:.3f} 0.05 0.25" rgba="0.3 0.3 0.3 1" {DRAWER}/>'
        + f'<site name="{cid}_door_handle" pos="{-dw + 0.06:.3f} 0.05 0.17" size="0.01"/></body>')
    return "".join(body) + "</body>"


def fridge_xml(f: dict) -> str:
    (cx, cy, _), (sx, sy, h) = f["position"], f["size"]
    fid, yaw = f["id"], f.get("yaw", 0.0)
    return (f'<body name="{fid}" pos="{cx} {cy} 0" euler="0 0 {yaw}">'
            + _box(f"{fid}_box", (0, -0.03, h / 2), (sx, sy - 0.06, h), "0.85 0.86 0.88 1")
            + f'<body name="{fid}_door" pos="{-sx / 2:.3f} {sy / 2 - 0.03:.3f} 0">'
              f'<joint name="{fid}_door" type="hinge" axis="0 0 1" range="0 2.0" damping="3" frictionloss="0.3"/>'
              f'<inertial pos="{sx / 2:.3f} 0.02 {h * 0.6:.3f}" mass="4" diaginertia="0.3 0.3 0.3"/>'
            + _box(f"{fid}_door_panel", (sx / 2, 0.025, h * 0.62), (sx - 0.01, 0.05, h * 0.74), "0.9 0.9 0.92 1", DRAWER)
            + _box(f"{fid}_freezer_panel", (sx / 2, 0.025, h * 0.12), (sx - 0.01, 0.05, h * 0.22), "0.9 0.9 0.92 1", DRAWER)
            + f'<geom name="{fid}_door_handle" type="capsule" size="0.015" fromto="{sx - 0.07:.3f} 0.09 {h * 0.45:.3f} '
              f'{sx - 0.07:.3f} 0.09 {h * 0.7:.3f}" rgba="0.4 0.4 0.4 1" {DRAWER}/>'
            + f'<site name="{fid}_door_handle" pos="{sx - 0.07:.3f} 0.09 {h * 0.57:.3f}" size="0.01"/>'
            + "</body></body>")


def object_xml(o: dict, pos) -> str:
    kind, mass, rgba = OBJ.get(o["catalog_id"], ("box", 0.2, "0.5 0.5 0.9 1"))
    sx, sy, sz = o["size"]
    if kind == "cylinder":
        geom = f'type="cylinder" size="{min(sx, 0.07) / 2:.4f} {sz / 2:.4f}"'
    else:
        geom = f'type="box" size="{sx / 2:.4f} {min(sy, 0.06) / 2:.4f} {sz / 2:.4f}"'
    return (f'<body name="{o["id"]}" pos="{pos[0]:.4f} {pos[1]:.4f} {pos[2]:.4f}">'
            f'<freejoint name="{o["id"]}"/>'
            f'<geom name="{o["id"]}" {geom} mass="{mass}" rgba="{rgba}" friction="1.2 0.02 0.001" condim="4"/></body>')


def build_mjcf(twin: dict, base_pos, base_yaw_deg: float = -90.0, object_pos: dict | None = None,
               lighting: str = "neutral", n_people: int = 0) -> str:
    """Returns an MJCF string. object_pos overrides {object_id: [x, y, z]} start positions."""
    object_pos = object_pos or {}
    fx = twin["fixtures"]
    sinks = [f for f in fx if f["type"] == "sink"]
    world = []
    for w in twin["walls"]:
        (x0, y0), (x1, y1) = w["start"], w["end"]
        L = math.hypot(x1 - x0, y1 - y0)
        yaw = math.atan2(y1 - y0, x1 - x0)
        world.append(f'<geom name="{w["id"]}" type="box" pos="{(x0 + x1) / 2} {(y0 + y1) / 2} {w["height"] / 2}" '
                     f'size="{L / 2} {max(w["thickness"], 0.05) / 2} {w["height"] / 2}" euler="0 0 {yaw}" '
                     f'rgba="0.93 0.91 0.86 1"/>')
    for f in fx:
        t = f["type"]
        if t == "counter":
            world.append(counter_xml(f, sinks, fx))
        elif t.startswith("fridge"):
            world.append(fridge_xml(f))
        elif t == "stove":
            (cx, cy, cz), (sx, sy, sz) = f["position"], f["size"]
            world.append(f'<body name="{f["id"]}" pos="{cx} {cy} 0" euler="0 0 {f.get("yaw", 0)}">'
                         + _box(f'{f["id"]}_box', (0, 0, sz / 2), (sx, sy, sz), "0.15 0.15 0.16 1")
                         + "".join(_box(f'{f["id"]}_burner{k}', (dx, dy, sz + 0.003), (0.16, 0.16, 0.006),
                                        "0.35 0.1 0.08 1")
                                   for k, (dx, dy) in enumerate([(-0.17, -0.13), (0.17, -0.13), (-0.17, 0.13), (0.17, 0.13)]))
                         + "</body>")
    for o in twin["objects"]:
        world.append(object_xml(o, object_pos.get(o["id"], o["position"])))
    world += [people.person_xml(i) for i in range(n_people)]
    world.append(robot.arm_xml(tuple(base_pos), base_yaw_deg))
    xs = [p for w in twin["walls"] for p in (w["start"][0], w["end"][0])]
    ys = [p for w in twin["walls"] for p in (w["start"][1], w["end"][1])]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    li = LIGHT[lighting]
    return f"""<mujoco model="{twin['room_id']}_sim">
<compiler angle="radian" autolimits="true"/>
<option timestep="0.002" cone="elliptic" impratio="10" integrator="implicitfast"/>
<visual><global offwidth="640" offheight="480"/><headlight ambient="{0.25 * li} {0.25 * li} {0.25 * li}" diffuse="{0.3 * li} {0.3 * li} {0.3 * li}"/><quality shadowsize="2048"/></visual>
<asset><texture name="floor" type="2d" builtin="checker" rgb1="0.62 0.55 0.47" rgb2="0.56 0.5 0.43" width="256" height="256"/>
<material name="floor" texture="floor" texrepeat="8 8"/></asset>
<default><geom friction="1.0 0.01 0.001"/></default>
<worldbody>
<light name="ceiling" pos="{cx} {cy} 2.35" dir="0 0 -1" diffuse="{li} {li} {0.95 * li}" castshadow="true"/>
<light name="fill" pos="{cx} {max(ys) - 0.3} 2.0" dir="0 -1 -1" diffuse="{0.4 * li} {0.4 * li} {0.4 * li}"/>
<geom name="floor" type="plane" pos="{cx} {cy} 0" size="{max(xs)} {max(ys)} 0.1" material="floor"/>
<camera name="overview" pos="{cx} {max(ys) - 0.1} 2.2" xyaxes="-1 0 0 0 -0.6 0.8" fovy="80"/>
{''.join(world)}
</worldbody>
<actuator>{robot.actuators_xml()}</actuator>
</mujoco>"""
