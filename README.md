# crypt_collector

Crypt Collector for the Total Battle game.

It opens the crypt list, travels to a crypt, explores it and speeds up the march, as many times as
you ask. Since version 2.0 it works on the **browser version of the game**, driving Chrome through
the DevTools Protocol (CDP): the game window does not have to stay in front and your mouse and
keyboard stay free while it runs.

Current version: see [VERSION](VERSION) · what changed: [CHANGELOG.md](CHANGELOG.md)

## Requirements

- Windows 10 or 11
- Google Chrome, Microsoft Edge or Brave
- A Total Battle account that you can log in to at https://totalbattle.com/

The installed (desktop) game client is no longer supported.

## Install and run

From source:

- `install.bat` (once)
- `start.bat`

Or:

- Download `docrypt.zip` from Releases.
- Extract and run `docrypt.exe`.

## How to use

### 1. Open the game

Click **1 · Open game in Chrome**. Chrome opens on the game page with its own profile, separate
from your everyday browser. **Log in to the game yourself** and wait for the map to load. The login
is remembered, so next time the game opens already logged in.

If that Chrome is already open, the button just connects to it.

After clicking **Open game in Chrome** and **before calibrating**, you must:

1. **Log in to the game** and wait for the map to load.
2. Leave **only the captain Carter selected** (no other captain).
3. For calibration, leave **only rare crypts (any level)** selected in the game's Crypts and Arenas
   filter.

### 2. Calibrate (once)

Click **2 · Calibrate**. The wizard shows a picture of the game and asks you to mark each control
on it, in the order of a real run. It plays the game along with you:

| What the step asks for | What the wizard does after you mark it |
|---|---|
| A **click point** | Clicks that point in the game, so the next screen opens |
| A **button area** | Clicks the centre of the area |
| A **validation area** | Nothing is clicked; it only moves on |

To calibrate every step, set the game's filter to **rare crypts** and have at least one key: rare
crypts are the ones that show the Open button.

| # | Step | Type | Notes |
|---|---|---|---|
| 1 | Watchtower | click point | The spyglass icon |
| 2 | Crypts and Arenas menu | click point | |
| 3 | Crypt icon | validation area | Icon of the first crypt in the list. The wizard tells you which crypt it recognised |
| 4 | Crypt list | validation area, optional | The whole list. Lets the crypt be found in any visible row |
| 5 | Go button | button area | Go button of the first crypt |
| 6 | Store open | validation area, optional | A fixed part of the store, such as the Bonus Sales icon. This is how the store is recognised |
| 7 | Close store (X) | button area, optional | The X of the store. Clicked to close it |
| 8 | Neighbouring tile 1 (right) | reference point, optional | Centre of the tile immediately to the right of the crypt. Nothing is clicked |
| 9 | Neighbouring tile 2 (below) | reference point, optional | Centre of the tile immediately below the crypt. Nothing is clicked |
| 10 | Crypt on the map | click point | |
| 11 | Open button | click point, optional | Only rare crypts show it. Skip it if Explore is already on screen |
| 12 | Explore button | button area | Sends the march |
| 13 | Speed up button | click point | |
| 14 | March icon | validation area | The three marching soldiers on the speedup screen |
| 15 | Use button | click point | Uses one speedup |

**The neighbouring tiles.** After some crypts the game stops centring the map on the crypt, and it
shows up on one of the eight tiles around the centre. Steps 8 and 9 measure the map grid, so those
eight positions are calculated instead of guessed. Without them the distance between tiles is
estimated from the page size, which may miss.

**The store.** The game often opens the store by itself right after Go, but not every time. If it
did not open when you reach step 6, click **Leave the store for the end**: the two store steps move
to the end of the calibration, and the wizard goes on with the crypt. When you get to them, open the
store in the game (or wait for it to open) and click *Refresh capture*. During a run, the X is only
clicked when the store picture is on screen.

Tips:

- Mark an area by dragging over the picture, or by clicking two opposite corners. The magnifier in
  the corner shows the exact pixel.
- If the picture is out of date, click **Refresh capture**.
- If a click does not change the screen, the wizard stays on the step and says so. Use **Redo**, or
  navigate in the game yourself and refresh the capture.
- Click a step in the list to redo only that one. **Test this step** repeats its click or looks for
  its picture on the current screen.
- Calibration is tied to the size of the game window. When a run starts, the window is resized back
  to the calibrated size.

### 3. Choose the crypts

In the **Crypts** tab, pick the same type that is filtered in the game, click the images of the
crypts you want and enter the quantity. **Any** explores the first crypt of the list without
checking its image.

### 4. Start

Before starting, in the game leave **only the captain Carter selected**, and select the **same crypt
type** you chose in the app's Crypts tab.

Click **▶ Start**. The game must already be open and logged in. Progress is shown in the execution
log, and also written to the `logs` folder.

To stop, click **■ Stop** or **hold ESC** for a moment, from any window.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| Speedups per march | 5 | How many times Use is clicked on each march |
| Wait after each click | 1.5 s | Time for the game to react. Increase it on a slow connection |
| Scroll step | 100 | How far the wheel turns on each scroll of the crypt list (100 = one notch) |
| Maximum scrolls | 80 | Limit per pass over the list, if its end is not detected |
| List passes | 3 | How many times the list is searched before giving up on a crypt |
| March timeout | 1800 s | Longest wait for the speedup screen to close |
| Match threshold | 0.80 | How closely the screen must resemble a reference image. Lower it (e.g. 0.75) if crypts are not recognised |
| CDP port | 9222 | Chrome's remote debugging port |
| Game address | https://totalbattle.com/ | Page opened when Chrome starts |
| Browser executable | empty | Empty = find Chrome, Edge or Brave automatically |

## Using a Chrome you opened yourself

The collector connects to any Chromium browser that is listening on the CDP port and has a tab on
`totalbattle.com`. To start one by hand:

```
chrome.exe --remote-debugging-port=9222 --remote-allow-origins=* --user-data-dir="C:\some\folder"
```

Chrome refuses remote debugging on its default profile, so `--user-data-dir` is required. Keep the
game tab selected and the window not minimized: a hidden tab stops drawing.

## Files

Created next to the program, and safe to delete to start over:

| File | Content |
|---|---|
| `config.json` | Language, selection, quantity and parameters |
| `calibration.json`, `calib_refs/` | Calibrated positions and reference pictures |
| `logs/` | Execution log |
| `browser_profile/` | The Chrome profile that keeps your game login |

## Troubleshooting

- **"The game was not found"**: open it with *1 · Open game in Chrome* and log in before starting.
- **Clicks land in the wrong place**: the game window has a different size from the calibration and
  could not be resized. Calibrate again at the current size.
- **Crypts are not recognised**: redo the *Crypt icon* step and check that the wizard reports a
  recognised icon; lower the *Match threshold* a little; make sure the type selected in the app is
  the one filtered in the game.
- **The list does not scroll, or skips crypts**: change the *Scroll step*, and calibrate the
  optional *Crypt list* step.

## Video tutorial (version 1.x)

https://youtu.be/xB7leLdwmT8

The video shows the old desktop-client version; the crypt selection is the same, the calibration is not.
