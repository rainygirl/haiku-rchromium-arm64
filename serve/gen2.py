#!/usr/bin/env python3
"""repro2.html -- the same bundles, but kept arriving.

repro.html ran 103,840 fresh new Function()/eval() parses in 50 seconds
without crashing, while x.com dies in about thirty. The difference is where
the parsing happens: new Function() and eval() parse on the main thread, so
once the eight <script src> bundles have loaded, repro.html has no background
parse left. V8 only streams a script that is still arriving over the network,
and the crash has looked like a race since the first measurement.

So instead of parsing more on the main thread, keep scripts arriving. Each
tick appends a <script src="gN.js?v=K">, a URL the cache has not seen, so V8
opens a new streaming parse on a background thread for it while the previous
ones are still running. Several are in flight at once, which is the shape of
a real site's bundle load and the one thing repro.html did only during its
first few seconds.
"""
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
BUNDLES = 8
IN_FLIGHT = 4

DRIVER = """
var loaded = 0, started = Date.now(), v = 0, live = 0;
function note() {
  var el = document.getElementById('status');
  var s = 'streamed ' + loaded + ' live=' + live + ' t=' +
          ((Date.now() - started) / 1000).toFixed(0);
  document.title = s;
  if (el) el.textContent = s;
}
function feed() {
  while (live < %d) {
    v++;
    var s = document.createElement('script');
    s.src = 'g' + (v %% %d) + '.js?v=' + v;
    s.async = true;
    s.onload = s.onerror = function () {
      loaded++; live--;
      if (this.parentNode) this.parentNode.removeChild(this);
      note();
    };
    live++;
    document.head.appendChild(s);
  }
  setTimeout(feed, 50);
}
setTimeout(feed, 100);
setInterval(note, 1000);
""" % (IN_FLIGHT, BUNDLES)

tags = "\n".join('<script src="g%d.js"></script>' % i for i in range(BUNDLES))
html = """<!doctype html>
<html><head><meta charset="utf-8"><title>stream stress</title></head>
<body><h1>stream stress</h1><p id="status">starting</p>
%s
<script>%s</script>
</body></html>
""" % (tags, DRIVER)
open(OUT + "/repro2.html", "w").write(html)
print("repro2.html %d bytes" % len(html))
