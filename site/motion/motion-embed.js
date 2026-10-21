/* motion-embed.js: tiny, dependency-free helper for the Arrival motion pieces.
   Drop it in with <script src="/motion/motion-embed.js" defer></script>.

   1) Drive a live frame from the page (iframes exported to /motion/live/*.html)
        const m = ArrivalMotion.frame(document.querySelector("#hero-motion"));
        m.play(); m.pause(); m.seek(2.5); m.progress(0.4); m.loop(true); m.hold();

   2) Declare it in HTML, no JS needed
        <iframe data-motion src="/motion/live/pipeline.html?autoplay=0"
                data-motion-scrub="#how-it-works"        scroll-link: progress follows how far that element has travelled through the viewport
                data-motion-range="0.1,0.9"              optional: only map this slice of the travel to 0..1
                data-motion-play-in-view                 alternative: play while on screen, pause when off screen
                title="..." loading="lazy"></iframe>

   3) Chapter wipes (transparent WebM laid over the page)
        ArrivalMotion.wipe("/motion/wipe-ink.webm", () => goToNextChapter());   // callback fires when the plate fully covers the page (~0.5 s) */
(function (g) {
  var clamp = function (v, a, b) { return Math.max(a, Math.min(b, v)); };

  function frame(iframe) {
    var info = { duration: null, hold: null, ready: false };
    var queue = [];
    function post(msg) {
      if (!info.ready) { queue.push(msg); return; }
      iframe.contentWindow && iframe.contentWindow.postMessage(msg, "*");
    }
    addEventListener("message", function (e) {
      if (e.source !== iframe.contentWindow || !e.data || !e.data.motion) return;
      if (e.data.motion === "ready") {
        info.ready = true; info.duration = e.data.duration; info.hold = e.data.hold;
        queue.splice(0).forEach(function (m) { iframe.contentWindow.postMessage(m, "*"); });
      }
    });
    // the frame announces itself once on load; if that message came before this script ran, ask again
    var ping = function () { if (!info.ready && iframe.contentWindow) iframe.contentWindow.postMessage({ motion: "ping" }, "*"); };
    iframe.addEventListener("load", ping); ping();
    return {
      play: function () { post({ motion: "play" }); },
      pause: function () { post({ motion: "pause" }); },
      seek: function (t) { post({ motion: "seek", t: t }); },
      progress: function (p) { post({ motion: "progress", value: clamp(p, 0, 1) }); },
      loop: function (v) { post({ motion: "loop", value: !!v }); },
      hold: function () { post({ motion: "hold" }); },
      restart: function () { post({ motion: "restart" }); },
      info: info
    };
  }

  function wipe(src, onCover, onDone) {
    var v = document.createElement("video");
    v.src = src; v.muted = true; v.playsInline = true; v.setAttribute("aria-hidden", "true");
    v.style.cssText = "position:fixed;inset:0;width:100vw;height:100vh;object-fit:cover;pointer-events:none;z-index:2147483000";
    var covered = false;
    v.addEventListener("timeupdate", function () {
      if (!covered && v.currentTime >= 0.5) { covered = true; onCover && onCover(); }
    });
    v.addEventListener("ended", function () { v.remove(); onDone && onDone(); });
    v.addEventListener("error", function () { v.remove(); if (!covered) onCover && onCover(); onDone && onDone(); });
    document.body.appendChild(v);
    v.play().catch(function () { v.remove(); onCover && onCover(); onDone && onDone(); });
    return v;
  }

  function wire(iframe) {
    var m = frame(iframe);
    var sel = iframe.getAttribute("data-motion-scrub");
    var range = (iframe.getAttribute("data-motion-range") || "0,1").split(",").map(parseFloat);
    if (sel) {
      var trigger = sel === "self" ? iframe : document.querySelector(sel);
      if (trigger) {
        var tick = function () {
          var r = trigger.getBoundingClientRect(), vh = innerHeight;
          var p = (vh - r.top) / (vh + r.height);                    // 0 as it enters at the bottom, 1 as it leaves at the top
          m.progress(clamp((clamp(p, 0, 1) - range[0]) / Math.max(range[1] - range[0], 1e-6), 0, 1));
        };
        var raf = 0;
        addEventListener("scroll", function () { cancelAnimationFrame(raf); raf = requestAnimationFrame(tick); }, { passive: true });
        addEventListener("resize", tick);
        m.pause(); tick();
      }
    } else if (iframe.hasAttribute("data-motion-play-in-view") && "IntersectionObserver" in g) {
      new IntersectionObserver(function (es) {
        es.forEach(function (e) { e.isIntersecting ? m.play() : m.pause(); });
      }, { threshold: 0.5 }).observe(iframe);
    }
    iframe._motion = m;
  }

  function init() { Array.prototype.forEach.call(document.querySelectorAll("iframe[data-motion]"), wire); }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init); else init();

  g.ArrivalMotion = { frame: frame, wipe: wipe, init: init };
})(window);
