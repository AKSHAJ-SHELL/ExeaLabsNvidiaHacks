# Arrival motion

Motion for the demo site, authored as HTML + GSAP compositions and rendered with
[Hyperframes](https://hyperframes.heygen.com/) (HeyGen's HTML-to-video engine, the same one the
[/brag](https://github.com/latent-spaces/brag) skill drives). Each piece exists three ways:
a rendered video, a poster, and a **live HTML export** with a small play / pause / seek / loop API,
so the site can either drop in a `<video>` or run the animation itself (looping, or scrubbed by scroll).

Everything is one drawing language: a surveyor's plan sheet, ink on warm paper, one signal colour.
The kitchen is the repo's real sample room (`scans/hero_kitchen/scan.json`, an authored sample, in
metres), so the drawings never claim more than the repo has.

## Files

| File | What | Length | Size |
|---|---|---|---|
| `intro.mp4` / `intro.webm` / `intro.jpg` | "Arrival" title sequence for the hero. A plan sheet draws itself (grid, registration marks, kitchen plan, dimension lines, title block: Sheet 01 / Exea Labs / scale 1:20) then clears to bare paper. First and last frame are the same, so it loops seamlessly. Poster is the settled sheet (5.9 s). | 7.6 s, 1920x1080, 30 fps | 0.35 MB mp4, 0.47 MB webm |
| `pipeline.mp4` / `pipeline.webm` / `pipeline.jpg` | Explainer: scan (LiDAR points settle into planes), twin (fixtures snap in with labels), simulate (arm trajectory, a person walking by, distance line), dataset (LeRobot file stack). Ends on a dashed "NEXT, NOT BUILT YET: GR00T fine-tune" box. Poster is the final settled frame. | 12.0 s | 1.97 MB mp4, 2.17 MB webm |
| `wipe-ink.webm` | Chapter wipe: ink line sweeps across, paper plate follows, signal line sweeps it away. VP9 **with alpha**. | 1.0 s | 0.04 MB |
| `wipe-fold.webm` | Chapter wipe: four paper panels unfold, then fold away. VP9 with alpha. | 1.0 s | 0.18 MB |
| `wipe-cross.webm` | Chapter wipe: registration-mark cross, paper disc blooms from it, hole opens at the same point. VP9 with alpha. | 1.0 s | 0.12 MB |
| `pitch.mp4` / `pitch.jpg` | 24.4 s launch video (tone: polished, deadpan, engineering drawing). Hook, reveal, three highlights (clips of `pipeline.mp4` re-edited inside Hyperframes), and an honest status sheet. Frame 0 is the poster (the reveal sheet) so thumbnails look right. Sparse CC0 sound effects, no music. | 24.4 s, AAC audio | 2.11 MB |
| `live/*.html` | Self-contained live exports of all six compositions (GSAP, helpers and fonts inlined). | | 80-345 KB each |
| `live/index.html` | Demo page for every embed method below (serve over http). | | |
| `motion-embed.js` | Optional ~100-line helper: scroll-linked scrubbing, play-in-view, `ArrivalMotion.wipe()`. | | 5 KB |

Total in `site/motion/`: about 10 MB.

**Wipe timing.** Each wipe peaks (page fully covered by paper) at **0.5 s**, so swap the chapter content then:
the `ArrivalMotion.wipe()` callback fires at 0.5 s. They are 1920x1080; `object-fit: cover` them.

## Embed: video

Hero loop (autoplay needs `muted` + `playsinline`; list webm first, mp4 as the Safari/older fallback):

```html
<video class="hero-motion" autoplay muted loop playsinline preload="metadata"
       poster="/motion/intro.jpg" aria-hidden="true">
  <source src="/motion/intro.webm" type="video/webm">
  <source src="/motion/intro.mp4" type="video/mp4">
</video>
```

Pipeline explainer, played when it scrolls into view:

```html
<video id="pipeline" muted playsinline preload="metadata" poster="/motion/pipeline.jpg" controls>
  <source src="/motion/pipeline.webm" type="video/webm">
  <source src="/motion/pipeline.mp4" type="video/mp4">
</video>
<script>
  new IntersectionObserver(([e]) => e.isIntersecting ? pipeline.play() : pipeline.pause(), { threshold: 0.6 })
    .observe(document.getElementById("pipeline"));
</script>
```

Chapter wipe overlay (transparent WebM above the page, swap content at the moment it covers):

```html
<script src="/motion/motion-embed.js" defer></script>
<script>
  // covers at ~0.5 s; the callback is where you scroll / swap the chapter
  ArrivalMotion.wipe("/motion/wipe-ink.webm", () => document.querySelector("#how").scrollIntoView());
</script>
```

or by hand: a `position:fixed; inset:0; pointer-events:none; z-index:9999` `<video muted playsinline>`, `.play()`,
and act when `currentTime >= 0.5`. Chrome, Edge and Firefox render the alpha channel of VP9 WebM; Safari does not,
so there the transparency may be lost. Feature-detect or user-agent-gate it and fall back to a
plain 0.5 s paper-coloured opacity fade (the wipes are opaque paper at their midpoint anyway). Not tested in Safari here.

## Embed: live HTML (iframe) and scroll-linked seek

Each `live/<name>.html` runs the exact composition in the browser. It scales its 1920x1080 stage to fit
whatever frame it is in (letterboxed on paper), and exposes one API three ways.

**Data attributes on `<html>` (or URL parameters, which win):**
`data-motion-autoplay="true|false"`, `data-motion-loop="true|false"`, `data-motion-hold="<s>"`,
`data-motion-end="<s>"` (stop there); URL form: `?autoplay=0&loop=1&t=2.5&end=5.9`.
`hold` is the time of the nicest settled frame (intro 5.9 s, pipeline 11.9 s, pitch 9.0 s), for reduced-motion
users and for "park it here" use. With `prefers-reduced-motion` the page does not play and jumps to `hold`.

**JS inside the frame:** `window.arrivalMotion` with `play() pause() seek(seconds) progress(0..1) hold() restart()`,
`loop` (get/set), `duration`, `time`, `playing`.

**postMessage from the parent:**
`{motion:"play"}`, `{motion:"pause"}`, `{motion:"seek", t:2.5}`, `{motion:"progress", value:0.4}`,
`{motion:"loop", value:true}`, `{motion:"hold"}`, `{motion:"ping"}` (frame answers with `ready` again; `motion-embed.js` sends it on iframe load, in case the first `ready` fired before the parent script ran). The frame posts `{motion:"ready", id, duration, hold}`
and `{motion:"ended", id}` back.

Scroll-linked seek, declarative (`motion-embed.js` does the math: progress is 0 as the trigger enters the
bottom of the viewport and 1 as it leaves the top; `data-motion-range` maps a slice of that travel to 0..1):

```html
<section id="how" style="height:300vh">
  <div style="position:sticky; top:0; height:100vh">
    <iframe data-motion src="/motion/live/pipeline.html?autoplay=0"
            data-motion-scrub="#how" data-motion-range="0.15,0.85"
            title="Scan, twin, simulate, dataset" style="width:100%; height:100%; border:0"></iframe>
  </div>
</section>
<script src="/motion/motion-embed.js" defer></script>
```

Scroll-linked seek, by hand (no helper):

```html
<iframe id="pipe" src="/motion/live/pipeline.html?autoplay=0" title="Pipeline"></iframe>
<script>
  const pipe = document.getElementById("pipe"), section = document.getElementById("how");
  const send = (m) => pipe.contentWindow.postMessage(m, "*");
  addEventListener("scroll", () => {
    const r = section.getBoundingClientRect();
    const p = Math.min(1, Math.max(0, -r.top / (r.height - innerHeight)));   // 0..1 across a tall sticky section
    send({ motion: "progress", value: p });
  }, { passive: true });
</script>
```

Scrubbing a `<video>` by `currentTime` works but stutters on the normal GOP. If you want that anyway, re-encode
all-intra: `ffmpeg -i pipeline.mp4 -c:v libx264 -g 1 -crf 22 -pix_fmt yuv420p -an pipeline-scrub.mp4` (about 8x bigger).
The live iframe is the better scrubber and is vector-sharp at any size.

Notes: `live/pitch.html` plays the same edit but silent (no SFX), and its clips load `../pipeline.mp4`, so keep that
file one folder up. Live pages need to be served over http(s) for that video; the others also work from `file://`.

## Design tokens

| Token | Value | Use |
|---|---|---|
| paper | `#F1EBDD` | background, plates |
| ink | `#141414` | all linework and text |
| signal | `#E5481F` | the one accent: datum, scan walk, trajectory, "NEXT" tags, progress rule |
| Display | **Fraunces** (variable, opsz + wght, roman + italic), weight 300 at large sizes | wordmark, headlines, tagline |
| Labels | **DM Mono** 400 / 500, uppercase, tracking .1-.12em, 14-17 px | dimension text, labels, captions |
| Line weights | wall 11 px, ink 3 px, hairline 1.5 px, grid 1 px at 9% (every 5th at 17%) | |
| Grid | 40 px sheet grid, frame inset 64/76 px, registration marks at the four corners | |

Signal-coloured text is avoided (3.4:1 on paper fails WCAG AA); the accent lives in strokes, fills and
tag boxes. `hyperframes check` passes contrast on every text node.
Fonts are self-hosted from `scripts/motion/shared/fonts/` (SIL OFL 1.1, licences alongside) and inlined into
the live exports, so renders do not depend on the network. GSAP 3.14.2 is vendored (GreenSock standard licence,
free to use).

## What is real in the drawings, and what is not

- Room, fixtures and objects (4.0 x 3.0 m, fridge, two counters, sink, stove, mug, bowl, sponge) are the positions
  and sizes in `scans/hero_kitchen/scan.json`. Its `geometry_source` is `authored_sample`, and the plan header says
  "authored sample". The dimension labels (750, 1450, 700, 1100, 4000, 3000) are millimetres taken from that file.
- All copy is the README's own wording or a plain label of it. The tagline "Scan a room once. Get robot training
  data for that exact room." is verbatim.
- **No result numbers appear anywhere.** `site/data/stats.json` does not exist on `main`, so nothing is quoted
  from it. The jittery "joint state" traces on the dataset card are decorative, not data.
- The scan walk, the walker, the arm path and the points are illustrative animation, not captured data.
- **The pitch status sheet is dated Oct 21 2026.** Scan, simulation, the dataset and the GR00T fine-tune are
  tagged done. The fine-tune line says 39 of 48 against 26 of 48, small samples. Real kitchen scans stay NEXT.
  `pipeline.mp4` still ends on the older dashed "NEXT, NOT BUILT YET: GR00T fine-tune" card. The pitch does not
  show that card: its clips are from 2.6 s, 5.8 s and 8.7 s of the pipeline.

## Audio

`pitch.mp4` carries 18 quiet sound effects (Kenney, CC0, copied from the brag skill's `assets/sfx` into
`scripts/motion/pitch/assets/sfx/`). **No music.** The brag skill bundles "Happy Beats / Business Moves" by
ende.app, but its README says the licence terms still need verifying and no licence text ships with it, so it is
left out rather than guessed at. To add a track later, drop an `<audio data-start="0" data-duration="24.4"
data-volume="0.3" src="assets/music/...">` into `scripts/motion/pitch/index.html` and re-render.
The pitch's overall level is deliberately low and sparse (deadpan tone).

## Re-render

Sources live in `scripts/motion/<name>/index.html` (shared GSAP, helpers, kitchen data and fonts in
`scripts/motion/shared/`). Needs Node 22+, ffmpeg and ffprobe on PATH, and network on the first run
(`npx` fetches `hyperframes@0.8.181`, which downloads its headless Chrome).

```bash
scripts/motion/render.sh              # everything (about 2 minutes on an M-series laptop)
scripts/motion/render.sh intro        # intro | pipeline | wipes (or wipe-ink | wipe-fold | wipe-cross) | pitch | live
scripts/motion/render.sh check pitch  # hyperframes lint + layout + contrast gate only
scripts/motion/render.sh snap pitch 3,9,20   # PNG stills at those seconds, for review
```

Order matters once: **`pitch` re-edits clips of `pipeline.mp4`**, so render `pipeline` before `pitch`
(`render.sh` stops with a message if it is missing). `render.sh live` rebuilds the live HTML (no browser needed).
Renders are 1080p, 30 fps, two Chrome workers (`MOTION_WORKERS=1` for less memory), one at a time; each takes
roughly 15-60 s here. Work files go to `$TMPDIR/arrival-motion` (`MOTION_WORK=...` to change).

Compositions are pure functions of time (seeded PRNG, no `Date`/`Math.random`, paused GSAP timeline registered on
`window.__timelines`), which is what lets the same file render to video and run live.
