# vendor/: pinned third-party code (no build step, works offline)

| file | version | source | licence |
|---|---|---|---|
| three/three.module.js, three/OrbitControls.js | three 0.170.0 | cdn.jsdelivr.net/npm/three@0.170.0 | MIT (three/LICENSE) |
| lenis/lenis.min.js | lenis 1.1.20 | cdn.jsdelivr.net/npm/lenis@1.1.20 | MIT (lenis/LICENSE) |
| gsap/gsap.min.js, gsap/ScrollTrigger.min.js | gsap 3.12.5 | cdn.jsdelivr.net/npm/gsap@3.12.5 | GreenSock "Standard No Charge" licence, **not MIT** (see gsap/LICENSE.md) |
| ../fonts/fraunces-opsz*.woff2 | @fontsource-variable/fraunces 5.2.6 | jsdelivr | SIL OFL 1.1 (../fonts/LICENSE-fraunces.txt) |
| ../fonts/dm-mono-*.woff2 | @fontsource/dm-mono 5.2.5 | jsdelivr | SIL OFL 1.1 (../fonts/LICENSE-dm-mono.txt) |

GSAP is the one component that is free to use but not MIT-compatible in the strict sense: it may not be used to
build a product that competes with GSAP-style visual animation tooling, and the licence is not OSI-approved. It is
isolated to `js/scroll.js` (ScrollTrigger and the shared ticker) so it can be swapped for plain IntersectionObserver
plus requestAnimationFrame if the project needs a pure-MIT tree. The 3D scene and every other module do not import it.
