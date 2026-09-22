# Test harness for the arm64 VM

The VM has no ssh, no curl and no python, and USB hot-plug does not enumerate,
so there are exactly two ways in: QMP keyboard events, and HTTP from the host.
`~/rtwitter-test/` on `rainygirl@MacMiniM4` is the working copy of this
directory; a plain `python3 -m http.server 8000` serves it, and the guest
reaches it at `10.0.2.2:8000`.

To run one of these:

    /xfer2/hget 10.0.2.2 8000 /xbrp.sh /boot/home/xbrp.sh
    sh /boot/home/xbrp.sh 70 MMDDhhmmYYYY > /boot/home/brp.log 2>&1 &

and read the result with `clear; cat /boot/home/brp.txt` plus a QMP screendump,
because there is no other way to get text back out. The second argument sets
the guest clock, which resets on every boot and otherwise fails TLS with
`ERR_CERT_DATE_INVALID`.

| script | what it measures |
| --- | --- |
| `xurl.sh` | which sites crash at all, three runs each |
| `xten.sh` | baseline vs `--js-flags=--single-threaded`, ten runs each |
| `xv8.sh` | jitless / predictable / no-lazy, six runs each |
| `xwiki.sh` | ko.wikipedia.org, ten runs |
| `xbrp.sh` | baseline vs `--disable-features=PartitionAllocBackupRefPtr` |
| `xrep.sh` | the local `repro.html` against x.com, interleaved |
| `genjs.py` | generates `repro.html` and its eight bundles, fixed seed |
| `gen2.py` | generates `repro2.html`, which keeps scripts streaming |

Every one of them interleaves or runs ten per arm, and that is not caution for
its own sake: at roughly two crashes in three runs, three runs cannot tell
100% from 66%, and the file above this one records a day spent on a "fix" that
was one run of noise.
