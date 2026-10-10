"""Builds the garden's plants (props/plants.toml, docs/house-garden.md "The plants", art #80) with the dressing
library's build (prop_build.py): one GLB per plant, build.json, the same checks. The runner calls it through
`props-library --library props/plants.toml --build` (the mapping file's `script`); by hand, background only, with
prop_build.py's arguments.

plant_geom registers the plant builders and its build_proc and finish replace prop_geom's for this run: a plant with
`collision = "boxes"` collides with the boxes its builder made (a tree's trunk), not its whole crown.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import plant_geom  # noqa: E402
import prop_build  # noqa: E402
import prop_geom  # noqa: E402

prop_geom.build_proc = plant_geom.build_proc
prop_geom.finish = plant_geom.finish

if __name__ == "__main__":
    prop_build.main()
