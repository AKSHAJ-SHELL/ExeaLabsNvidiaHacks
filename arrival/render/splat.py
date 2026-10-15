"""Splat composite renderer (spec step 5). Specified in docs/03-architecture.md, not implemented.
It refuses to pretend it rendered a splat."""


class SplatCompositeNotImplemented(NotImplementedError):
    pass


DEPTH_MARGIN = 0.01


def render(*args, **kwargs):
    raise SplatCompositeNotImplemented(
        "Splat composite is not built. Use arrival.render.sim_texture. See docs/09-later.md."
    )
