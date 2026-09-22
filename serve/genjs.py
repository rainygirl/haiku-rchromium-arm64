#!/usr/bin/env python3
"""Generate a local page that puts V8's parser under the same kind of load a
real site does, without the network deciding how much of it arrives.

The arm64 crash is a live AstRawString whose bytes belong to some other
string, and every measurement of it so far has been taken on x.com, where the
crash rate moved between 3/6 and 10/10 from one day to the next because the
site does not serve the same bundles twice. Nothing can be bisected against a
control that moves. This builds a page that is byte-identical every run:

  - eight large <script src> bundles, so several of them are streamed and
    parsed on background threads at once while the main thread parses inline
    script;
  - tens of thousands of distinct identifiers per bundle, which is what makes
    AstValueFactory allocate and rehash rather than hit the constants;
  - a majority of function bodies never called, so they are lazily skipped on
    the first parse and reparsed later, which is when GetString runs again;
  - a driver that keeps calling new Function() and eval() after load, so
    parsing continues for the whole measurement window rather than stopping a
    second in.
"""
import os
import random
import sys

OUT = sys.argv[1] if len(sys.argv) > 1 else "."
BUNDLES = 8
FUNCS_PER_BUNDLE = 1400

rnd = random.Random(20260922)
WORDS = ["alpha", "bravo", "delta", "echo", "flux", "gamma", "hydra", "ionic",
         "jolt", "kilo", "lumen", "mica", "nova", "omega", "pulse", "quartz",
         "rune", "sigma", "tau", "umbra", "vertex", "wisp", "xeno", "yield",
         "zenith", "atlas", "beacon", "cinder", "drift", "ember"]


def ident(n):
    return "%s_%s_%d" % (rnd.choice(WORDS), rnd.choice(WORDS), n)


def body(fn, depth):
    """A function body with unique locals, unique object keys and a nested
    inner function. The inner one is never referenced from outside, so V8
    skips it on the first pass and parses it again on demand."""
    a, b, c = ident(fn * 4), ident(fn * 4 + 1), ident(fn * 4 + 2)
    key1, key2 = ident(fn * 4 + 3), ident(fn * 7)
    lines = [
        "  var %s = %d, %s = '%s';" % (a, fn, b, ident(fn * 11)),
        "  var %s = { %s: %s, %s: %s.length, nested_%d: { %s: [%d, %d] } };"
        % (c, key1, a, key2, b, fn, ident(fn * 13), fn, fn * 3),
        "  function inner_%d(%s, %s) {" % (fn, ident(fn * 17), ident(fn * 19)),
        "    var %s = %s.%s + %s.%s;" % (ident(fn * 23), c, key1, c, key2),
        "    return %s * %d;" % (ident(fn * 23), depth + 1),
        "  }",
        "  return %s.%s + inner_%d(%s, %d);" % (c, key2, fn, a, fn),
    ]
    return "\n".join(lines)


def bundle(index):
    out = ["// bundle %d -- generated, do not edit" % index,
           "(function () {",
           "'use strict';",
           "var sink_%d = 0;" % index]
    for i in range(FUNCS_PER_BUNDLE):
        fn = index * 100000 + i
        out.append("function fn_%d_%d() {" % (index, i))
        out.append(body(fn, i % 7))
        out.append("}")
        # Call one in eight. The rest stay lazy.
        if i % 8 == 0:
            out.append("sink_%d += fn_%d_%d();" % (index, index, i))
    out.append("window.bundle_%d_done = sink_%d;" % (index, index))
    out.append("})();")
    return "\n".join(out)


SOURCE_TEMPLATE = """(function () {
  var %s = { %s: %d };
  function step_%d(%s) { return %s.%s + %s; }
  return step_%d(%d);
})()"""


def driver():
    """Keeps the parser busy after load. Each new Function() call is a fresh
    parse with identifiers this process has not seen before, so it allocates
    new AstRawStrings rather than finding them in the table."""
    return """
var evalCount = 0, evalSink = 0, started = Date.now();
function freshSource(n) {
  var a = 'v_' + n + '_' + (n * 7 % 9973);
  var k = 'k_' + n + '_' + (n * 13 % 9967);
  var p = 'p_' + n + '_' + (n * 17 % 9949);
  return '(function(){ var ' + a + ' = { ' + k + ': ' + n + ' };' +
         ' function s_' + n + '(' + p + '){ return ' + a + '.' + k + ' + ' + p + '; }' +
         ' return s_' + n + '(' + (n % 100) + '); })()';
}
function churn() {
  for (var i = 0; i < 40; i++) {
    evalCount++;
    try {
      evalSink += (new Function('return ' + freshSource(evalCount)))();
      evalSink += eval(freshSource(evalCount + 500000));
    } catch (e) { }
  }
  document.title = 'churn ' + evalCount + ' t=' +
                   ((Date.now() - started) / 1000).toFixed(0);
  var el = document.getElementById('status');
  if (el) el.textContent = document.title + ' sink=' + evalSink;
  setTimeout(churn, 15);
}
setTimeout(churn, 200);
"""


def main():
    os.makedirs(OUT, exist_ok=True)
    total = 0
    for i in range(BUNDLES):
        text = bundle(i)
        path = os.path.join(OUT, "g%d.js" % i)
        with open(path, "w") as fh:
            fh.write(text)
        total += len(text)
        print("%s  %d bytes" % (path, len(text)))

    tags = "\n".join('<script src="g%d.js"></script>' % i for i in range(BUNDLES))
    html = """<!doctype html>
<html><head><meta charset="utf-8"><title>parser stress</title></head>
<body><h1>parser stress</h1><p id="status">starting</p>
%s
<script>%s</script>
</body></html>
""" % (tags, driver())
    with open(os.path.join(OUT, "repro.html"), "w") as fh:
        fh.write(html)
    print("repro.html  %d bytes, bundles total %d bytes" % (len(html), total))


main()
