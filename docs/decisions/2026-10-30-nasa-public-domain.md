# NASA public-domain imagery on the licence allowlist (art #356)

Date: 2026-10-30. Status: accepted (the engineer's yes on art #356, 2026-10-30, after step 3 stopped on the licence).

## Context
The lobby hall's window looks onto the night Earth from low orbit (`docs/lobby.md`). The usual source for a real night
Earth is NASA's imagery: Black Marble (the city lights at night) and Blue Marble (land, oceans and clouds). The
licence allowlist in `docs/manifest.md` had `CC0-1.0`, `CC-BY-4.0`, `owned-paid-output`, `own-work` and `restricted`,
with no public-domain entry, and CLAUDE.md puts licences outside the allowlist with the engineer, so step 3 stopped and
asked.

NASA's terms (https://www.nasa.gov/nasa-brand-center/images-and-media/): NASA content is "generally not subject to
copyright in the United States"; NASA asks to be acknowledged as the source; its use must not state or imply NASA's
endorsement; the NASA insignia, logotype and other emblems are protected and are not covered; NASA does not want its
imagery used in NFTs. Third-party content on NASA sites (marked with its own credit or copyright) stays protected.

## Decision
- A new licence id **`NASA-PD`**: US government public-domain imagery made by NASA, downloaded only from nasa.gov sites
  (earthobservatory.nasa.gov, visibleearth.nasa.gov, svs.gsfc.nasa.gov, science.nasa.gov and the like). It is a public
  licence: `public_repo_ok = true` is allowed.
- Conditions, kept in every record and every use:
  - `credit` is required (as for `CC-BY-4.0`); the game's credit line is **"Earth imagery: NASA"**;
  - no NASA logo, insignia, meatball, worm or mission patch in any asset;
  - nothing that states or implies NASA's endorsement of the game (no "in partnership with NASA", no NASA name in
    marketing beyond the credit line);
  - only images NASA made itself: an image a NASA page marks as a third party's work is not `NASA-PD`;
  - `licence_url` points to NASA's media terms page above.
- `tools/runner/commands/_manifest.py`: `NASA-PD` in `PUBLIC_LICENCES`, and in `CREDIT_LICENCES`, the licences whose
  records need `credit`; `docs/manifest.md`'s licence row names it.

## Consequences
- The lobby's Earth textures (`sources/nasa_earth_lobby.toml`) can ship in the public game repo with their credit.
- The game's credits list gains the line "Earth imagery: NASA" when the lobby's Earth lands there.
- Other public-domain sources (other agencies, expired copyright) are not covered; each needs its own yes.
