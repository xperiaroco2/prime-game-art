"""The Ultimate Modular assembler: builds characters from Quaternius' Ultimate Modular Men and Women packs (CC0) on one
rig, adds our scripted eyes, brows and mouths, poses, measures, renders and saves them (docs/assembly.md).

Ported from the final character test (D:/prime-art-raw/research/2026-10-03-art-research/final-character-test/) with
the behaviour unchanged. Modules by concern:

- glb, zones, recipe: pure Python (no bpy): the GLB table of contents, the rest-pose world-space zones, recipes;
- util, packs, rebind, heads, fit, poses, materials, facekit, render, assemble, blendfile: inside Blender.

The runner imports the pure-Python modules too (to validate a recipe before Blender starts), so this file imports
nothing.
"""
