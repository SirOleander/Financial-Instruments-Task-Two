# Dashboard assets

## `logo.png` — the top-left logo (also the click-home target → Ranking)

Drop a **`logo.png`** here. It is auto-detected at render time (not cached), so no restart
and no code change. Until it exists, the header falls back to the `SIGNAL·DESK` wordmark
placeholder — the click-home behaviour works either way.

* **Any aspect ratio.** Transparent padding is trimmed on an alpha threshold and the mark is
  height-fitted to the holder with `object-fit:contain`, so a square mark and a wide wordmark
  both render undistorted.
* **Dark artwork is handled.** If the ink measures dark it is whitened on the navy dark theme,
  which would otherwise swallow it. Light mode always uses the original colours.
* **To keep brand colour in dark mode**, add a light-ink variant as **`logo_dark.png`**. When
  present it is used verbatim in dark mode and the whitening filter is bypassed.
