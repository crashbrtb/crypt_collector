# Changelog

## 2.0.0

### New

- **The game now runs in Chrome.** Crypt Collector drives the browser version of Total Battle through
  the Chrome DevTools Protocol (CDP) instead of clicking on the screen of the installed game. The game
  window no longer has to stay in front, and your mouse and keyboard stay free while it runs.
- **Open game in Chrome** button: starts Chrome (or Edge/Brave) ready for the collector, or connects
  to the one that is already open. You log in to the game yourself; the login is remembered between
  sessions.
- **Calibration wizard.** Positions are marked on a picture of the game, with a magnifier, instead of
  on the live screen:
  - after you mark a click point, the wizard clicks it in the game so the next screen opens by itself;
  - after you mark a button area, the wizard clicks the centre of that area;
  - validation areas (crypt icon, crypt list, store, march icon) are only recorded and the
    wizard moves on without clicking;
  - areas can be dragged or marked with two clicks;
  - any single step can be redone or tested on its own, and the wizard resumes at the first missing step.
- **Crypt icon check during calibration**: the wizard tells you which crypt it recognised in the
  marked icon area, so a wrong area is noticed before running.
- **Whole-list search** (optional *Crypt list* step): the selected crypts are looked for in every
  visible row at once, and Go is clicked on the row where the crypt was found.
- **Crypt located on the map by its picture**: the first time a crypt is opened, its look on the map
  is memorised (in `calib_refs/map`). From then on the crypt is found by that picture and clicked
  directly, even when the game does not centre the map on it. The nine positions around the centre
  are still tried as a fallback, and a click on empty ground is now skipped in about one click delay.
- **Store calibration** (optional), right after the Go button, where the store opens by itself: you
  mark a fixed part of the store (the Bonus Sales icon) and then its X. During a run the X is only
  clicked when the store is recognised on screen.
- **Leave the store for the end**: if the store did not open during calibration, one button moves its
  two steps to the end, to be calibrated when the store shows up.
- **Parameters tab**: speedups per march, wait after each click, scroll step, list passes, march
  timeout, match threshold, CDP port, game address and browser executable.
- **Stop button**, and holding **ESC** now stops a run from any window.
- **Live execution log** inside the main window, with a log file in the `logs` folder.
- The application version is shown in the window title and header.

### Changed

- **New interface**: dark theme with *Execution*, *Crypts* and *Parameters* tabs. Crypts are chosen
  by clicking their images; the selection, quantity and language are saved automatically.
- **Calibration steps** are now: Watchtower, Crypts and Arenas menu, Crypt icon, Crypt list
  (optional), Go button, Store open (optional), Close store (optional), Crypt on the map, Open button
  (optional), Explore button, Speed up button, March icon, Use button.
- The **Explore button** and the **march icon** are recognised by the picture taken during
  calibration, so they match your game at any window size.
- The **Open button** is used for any crypt that shows it, not only when a rare crypt image is selected.
- The search stops at the **end of the crypt list** and restarts from the top, instead of scrolling a
  fixed number of times.
- A run **stops after 5 rounds in a row without success** instead of repeating the same error.
- The game window is **resized back to the calibrated size** when a run starts; if that is not
  possible, the calibrated positions are rescaled.
- Language, crypt quantity, speedups and selection from version 1.x are imported on the first start.
  Positions are not: **a new calibration is required**.

### Removed

- Support for the installed (desktop) game client.
- The separate status window: the log is now part of the main window.
