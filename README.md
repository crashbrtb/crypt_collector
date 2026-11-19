# crypt_collector

Crypt Collector for the Total Battle game.

Since version 3.0 everything goes **through the game's own network protocol**, from inside the game tab in
Chrome (the same technique as Autoattack): no clicks, no screenshots, no calibration. The Chrome window can stay
behind other windows and your mouse and keyboard stay free.

Current version: see [VERSION](VERSION) · what changed: [CHANGELOG.md](CHANGELOG.md) · protocol notes:
[PROTOCOLO.md](PROTOCOLO.md)

## What it does

- Finds the crypts by itself, with the game's spyglass search or by scanning the map blocks around the city.
- Up to **3 captains** at the same time. Each captain does **one crypt family and level** (e.g. Epic 35) and one
  or more crypt types of that level; several captains may do the same type.
- Always sends the captain to the **closest free crypt**. Two captains never go to the same crypt, and a crypt
  with another player's march already on the way is skipped.
- Opens rare crypts with the Dragon Key, sends the right tar (rare, epic or bloody) and **speeds up** the march.
  The tar left over comes back with the captain; the app measures how much damage each captain does per tar and
  sends the right amount next time.
- Puts the captains in the 3-captain march list and dresses them with the **armour and artifact** you chose.
- Saves the whole selection (captains, crypts, armour, artifacts) with a name to repeat it later.
- If the game freezes (the Unity error that locks the page), it reloads the tab (F5); if the game does not come
  back, it closes that Chrome and opens it again, then carries on.
- Crypt pictures, names and captains come from the game's own data (downloaded once per game version into
  `data/`).

## Requirements

- Windows 10 or 11
- Google Chrome, Microsoft Edge or Brave
- A Total Battle account that you can log in to at https://totalbattle.com/

## Install and run

From source: `install.bat` (once), then `start.bat`. Or download `docrypt.zip` from Releases and run `docrypt.exe`.

## How to use

1. **1 · Open game in Chrome**: Chrome opens with its own profile. Log in to the game yourself and wait for the
   map. The login is remembered.
2. **2 · Connect**: reads the city, the captains, the tar, keys and speedups, and how many crypts there are nearby.
3. Tab **Captains and crypts**: for each lane tick it, pick the captain, the crypt family and level, click the
   crypt pictures (under each one: how many are nearby · distance of the closest) and the quantity (0 = no limit).
   **🛡 Equipment** chooses the 3 armour pieces and the artifact of that captain. **💾 Save** keeps the whole
   selection with a name; **Load** brings it back.
4. **▶ Start**. To stop: **■ Stop** or hold **Esc**.

The first time, loading the game data takes about 2 minutes.

## Parameters

| Parameter | Default | Meaning |
|---|---|---|
| How to find crypts | Spyglass | Spyglass = the game's search by type; Map scan = reads the map blocks (up to 200) |
| Search radius | 150 | Maximum distance from the city |
| Check marches on the way | on | Skips a crypt that someone's march is heading to |
| Minimum crypt time left | 180 s | A crypt that disappears sooner is not chosen |
| Speedups per march | 5 | The game stops accepting them with ~20 s left |
| Tar margin | 1.25 | Extra over the captain's measured damage; the rest comes back |
| Game frozen after | 90 s | No request from the game for this long → F5 |
| Wait after F5 / after restarting Chrome | 120 / 240 s | Then the next recovery step |
| CDP port, game address, browser, profile | 9222, totalbattle.com, auto, `browser_profile` | |

## Files

| File | Content |
|---|---|
| `config.json` | Language, lanes, saved selections, parameters, measured tar damage |
| `data/` | Game data cache (tables, translations, pictures) |
| `logs/` | Execution log |
| `browser_profile/` | The Chrome profile that keeps your game login |

`calibration.json` and `calib_refs/` from version 2.x are no longer used and can be deleted.
