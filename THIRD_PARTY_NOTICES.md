# Third-party notices

This repository distributes SesKutusu source code and its original icon artwork. It does not vendor dependency source, dependency binaries, system fonts, audio drivers or third-party sound files. Installing the requirements obtains dependencies from their publishers; their licenses remain applicable.

| Dependency | Selected licensing information | Upstream |
| --- | --- | --- |
| PySide6 Essentials / Shiboken | Community packages offer LGPL-3.0 / GPL alternatives; use and distribution must follow the applicable option and module licenses. | https://doc.qt.io/qtforpython-6/ |
| NumPy | BSD-3-Clause; packaged numerical libraries have additional notices. | https://numpy.org/doc/stable/license.html |
| python-sounddevice | MIT; PortAudio has its own permissive license. | https://python-sounddevice.readthedocs.io/ |
| python-soundfile | BSD-3-Clause; libsndfile and bundled codecs have separate licenses, including LGPL. | https://github.com/bastibe/python-soundfile |
| CPython | Python Software Foundation license and included third-party notices. | https://docs.python.org/3/license.html |

The exact versions directly required by this source edition are pinned in `requirements.txt`. Transitive dependencies are supplied by those distributions and retain their own notices. Refer to the installed distribution's metadata and license files for the exact applicable terms.

VB-CABLE is a separate VB-Audio product. It is not included, installed or sublicensed by this repository. Obtain it from https://vb-audio.com/Cable/ and follow https://vb-audio.com/Services/licensing.htm .

The MIT license for SesKutusu does not override dependency licenses or grant rights to third-party recordings, trademarks or sound effects.
