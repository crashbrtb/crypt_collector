# Changelog

## 3.0.0

### New

- **Everything through the game network.** The collector talks to the game server from inside the game tab
  (the Autoattack technique): no clicks, no screen reading, no calibration.
- **Crypts found automatically**: the game's spyglass search (route 26001) or a scan of the map blocks
  around the city (route 312). The closest free crypt is always chosen.
- **Up to 3 captains at once**, each with one crypt family and level and one or more crypt types of that
  level. Several captains may do the same type. Mixing families or levels in one captain is not possible.
- **Never the same crypt twice**: crypts are reserved per captain, and a crypt with another player's march
  heading to it is skipped (map block check before sending).
- **Rare crypts opened with the Dragon Key** (route 14004), the right tar sent with the march, and **automatic
  speedups** (item 2102) until the game stops accepting them.
- **Tar learned per captain**: the tar left over comes back with the captain; the damage per tar is measured
  and the next march carries the right amount. A crypt left with health gets another march.
- **Captains put in the 3-captain march list** automatically (route 905).
- **Armour and artifact per captain** (routes 901/910/61002), chosen from the inventory, applied before the
  first crypt.
- **Saved selections**: captains, crypts, armour and artifacts saved with a name and loaded back.
- **Crypt pictures from the game** (Unity CDN), not from the `images` folder.
- **Game watchdog**: if the game stops talking to the server (frozen) or the tab stops answering, the page is
  reloaded (F5); if that is not enough, the Chrome on the CDP port is closed and opened again with the same
  profile, and the run continues.

### Removed

- Calibration wizard, screen recognition (OpenCV) and the crypt images folder.

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
