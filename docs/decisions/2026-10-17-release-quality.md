# Release quality, one piece at a time

- Status: accepted (the engineer, 2026-10-17, in chat with the art manager)
- Issue: [#196](https://github.com/xperiaroco2/prime-game-art/issues/196); the work it stops:
  [#195](https://github.com/xperiaroco2/prime-game-art/issues/195) (the alien rounds).

## Context

Rounds 1 to 3 of the alien characters (#195) built 24 whole aliens at once from a shared kit, each with an invented
name, persona and hit gag, and showed them in a 3D showroom. The engineer looked at them on 2026-10-17 and found every
one ugly: nobody would want to play them. His diagnosis: we made too much at once, so the quality dropped, and the
names, stories and gags were never asked for. The earlier character work (the skeleton, the animation set, the
ragdoll) was a try-out of the foundation; what goes on it now must impress players and bring them back: beautiful,
attractive, stylish.

## Decision

1. **Everything made from now on is meant for the final release**, or close to it. A lab may test a method or tune a
   parameter, but it does not produce throwaway breadth.
2. **One piece at a time.** Characters start from one base character (the male body first, the female after it), then
   interchangeable parts: eyes, mouths, noses, hairstyles, skin colours, outfits. Each part is polished until nothing
   about it looks dumb or ugly, and judged alone before the next one starts.
3. **No invented lore.** No names, personas, backstories or per-character gags unless the engineer asks for them.
4. **Variant grids stay for tuning** one parameter on one sheet (`docs/agents.md`, rule 6), never for making many whole
   characters at once.
5. **The look stays his call**: nothing about the look merges without his yes on the pictures (the trust model keeps
   the per-asset yes for characters and faces, `docs/decisions/2026-10-03-trust-model.md`).

His answers of the same day set the first target: beautiful aliens (the alien-ness in the skin colour, the eyes, the
ears or head shapes; attractive proportions), premium plasticine (an expensive stop-motion feature's clean forms and
fine handmade surface), and the method decided on one head (built in Blender by agents versus generated with Meshy and
cleaned up), shown side by side.

## Consequences

- #195's round plan (round 4, the roster pick from 24) is dropped; round 4 was stopped mid-run.
- Briefs ask for one head or one part at a release bar, with an honest list of what still looks weak, and critics
  judge against that bar rather than ranking many variants.
- A tools research (#196) looks for the best way to make many organic parts, since parts built by code in Blender came
  out crude.
