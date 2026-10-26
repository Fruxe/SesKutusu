# Source and binary distribution

## This public source package

The public edition intentionally contains no Myinstants downloader, downloaded sound collection, copied third-party program binaries, analysis artifacts or personal library. API availability is not a grant to redistribute sound recordings. Reintroducing a provider integration requires its own terms and content-rights review.

Original application sources and artwork use the repository's MIT license. Dependencies are installed separately by the recipient. Their authors retain their rights. This source edition does not claim to be an authorized replacement for another product.

## Before publishing a separate EXE release

This repository does not include or automatically publish a binary release. A publisher who chooses to package one must first:

1. Build in a fresh environment using official Python and documented dependency distributions. Do not copy development-tool runtimes, unrelated DLLs, machine-specific SSL patches or existing personal application folders.
2. Inventory **every shipped binary**, including Qt/PySide6/Shiboken, Python, PortAudio, libsndfile and codecs, OpenBLAS, any TLS libraries and Microsoft runtimes. Record versions, applicable licenses, origin and modifications; include required notices and full license texts.
3. For LGPL components, provide the complete corresponding library sources through a compliant distribution mechanism, retaining exact versions and modifications. Generic upstream homepage links alone must not be treated as a complete compliance solution. Preserve the user's ability to replace/relink and run modified libraries, document the procedure and do not impose terms prohibiting reverse engineering for that purpose. Consult the applicable license for the chosen distribution method and any installation-information requirements.
4. Check Qt's third-party components and module-specific licensing. Do not assume every Qt component permits the same licensing option. App MIT licensing does not remove library obligations.
5. Keep VB-CABLE separate unless its current distribution conditions have specifically been met. Do not redistribute other paid virtual cable packages by assumption.
6. Exclude personal `data/`, downloaded audio, credentials, diagnostic logs, research outputs and third-party product files. Use only original or properly licensed material in screenshots and examples.
7. Re-test local playback, microphone routing, global hotkeys, theme changes, translations and library persistence from the **actual packaged EXE**, not just from Python source.

References:

- [Qt open-source licensing FAQ](https://www.qt.io/faq/qt-open-source-licensing)
- [Qt LGPL obligations](https://www.qt.io/development/open-source-lgpl-obligations)
- [libsndfile](https://github.com/libsndfile/libsndfile)
- [VB-Audio licensing](https://vb-audio.com/Services/licensing.htm)
- [GitHub repository licensing](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)

These are engineering release criteria, not a legal certification. Distribution scope, third-party changes and the applicable jurisdiction may require additional review.
