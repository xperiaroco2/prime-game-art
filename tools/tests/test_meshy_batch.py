"""Batch files: the schema, the estimate and the approval check (no network)."""

from __future__ import annotations

import contextlib
import io
import tomllib
import unittest
from pathlib import Path
from typing import Any

from runner import cli, common
from runner.commands import _meshy_batch as batches

APPROVAL = {
    "approved_by": "xperiaroco2 (the engineer)",
    "approved_at": "2026-10-02",
    "approval_ref": "https://github.com/xperiaroco2/prime-game/issues/165#issuecomment-1",
    "plan": "Meshy Pro (monthly)",
    "terms_url": "https://www.meshy.ai/terms-of-use",
    "licence": "owned by the customer on a paid plan (Meshy terms 3.2)",
}


def batch_data(**overrides: Any) -> dict[str, Any]:
    """A batch with every kind: two bodies, a rig of the first and an animation of the rig."""
    data: dict[str, Any] = {
        "id": "t-batch",
        "purpose": "tests",
        "credit_cap": 100,
        **APPROVAL,
        "variants": {"a": {"prompt": "a cartoon human"}},
        "defaults": {"text_to_3d": {"preview": {"ai_model": "meshy-7.1", "topology": "triangle"},
                                    "refine": {"enable_pbr": False}}},
        "items": [
            {"id": "a-1", "variant": "a", "kind": "text_to_3d"},
            {"id": "b-1", "variant": "b", "kind": "text_to_3d", "prompt": "a cartoon robot",
             "preview": {"ai_model": "meshy-6-lite"}},
            {"id": "a-1-rig", "kind": "rig", "source": "a-1", "params": {"height_meters": 1.8}},
            {"id": "a-1-walk", "kind": "animate", "source": "a-1-rig", "params": {"action_ids": [1, 2]}},
        ],
    }
    data.update(overrides)
    return data


def parse(data: dict[str, Any]) -> batches.Batch:
    return batches.parse(data, Path(f"{data.get('id', 'x')}.toml"))


class EstimateTest(unittest.TestCase):
    def test_credits_per_stage_and_total(self) -> None:
        batch = parse(batch_data())
        per_item = {i.id: [(s.name, s.credits) for s in i.stages] for i in batch.items}
        self.assertEqual(per_item["a-1"], [("preview", 20), ("refine", 10)])
        self.assertEqual(per_item["b-1"], [("preview", 5), ("refine", 10)])
        self.assertEqual(per_item["a-1-rig"], [("rig", 5)])
        self.assertEqual(per_item["a-1-walk"], [("animate", 6)])
        self.assertEqual(batch.credits, 56)
        self.assertEqual(batch.item("a-1-rig").variant, "a")

    def test_prices(self) -> None:
        self.assertEqual(batches.preview_credits({}), 20)  # "latest" is meshy-7.1
        self.assertEqual(batches.preview_credits({"model_type": "smart-topology"}), 5)
        self.assertEqual(batches.preview_credits({"ai_model": "meshy-7.1", "geometry_resolution": "4k"}), 25)
        self.assertEqual(batches.refine_credits({"texture_resolution": "8k"}), 15)

    def test_untextured_item_skips_refine(self) -> None:
        data = batch_data(items=[{"id": "a-1", "variant": "a", "kind": "text_to_3d", "texture": False}])
        self.assertEqual([s.name for s in parse(data).items[0].stages], ["preview"])

    def test_merging_puts_the_item_over_the_defaults(self) -> None:
        item = parse(batch_data()).item("b-1")
        self.assertEqual(item.stages[0].params, {"ai_model": "meshy-6-lite", "topology": "triangle"})
        self.assertEqual(item.prompt, "a cartoon robot")


class ValidationTest(unittest.TestCase):
    def assert_invalid(self, data: dict[str, Any], message: str) -> None:
        with self.assertRaisesRegex(common.Failure, message):
            parse(data)

    def test_rejects_broken_batches(self) -> None:
        good = batch_data()
        cases = [
            (dict(good, credit_cap=0), "credit_cap"),
            (dict(good, id="Bad Id"), "lower-case"),
            (dict(good, items=[]), "no \\[\\[items\\]\\]"),
            (dict(good, items=[{"id": "x", "variant": "a", "kind": "image_to_3d"}]), "not one of"),
            (dict(good, items=[{"id": "x", "variant": "zz", "kind": "text_to_3d"}]), "no prompt"),
            (dict(good, items=[{"id": "x", "variant": "a", "kind": "text_to_3d", "prompt": "p" * 801}]), "at most 800"),
            (dict(good, items=[{"id": "x", "variant": "a", "kind": "text_to_3d", "preview": {"mode": "refine"}}]),
             "filled in by the runner"),
            (dict(good, items=[{"id": "r", "kind": "rig", "source": "nope"}]), "not an earlier item"),
            (dict(good, items=good["items"][:1] + [{"id": "w", "kind": "animate", "source": "a-1",
                                                     "params": {"action_ids": [1]}}]), "needs a rig item"),
            (dict(good, items=good["items"][:3] + [{"id": "w", "kind": "animate", "source": "a-1-rig"}]),
             "action_ids"),
            (dict(good, items=good["items"][:3] + [{"id": "w", "kind": "animate", "source": "a-1-rig",
                                                     "params": {"action_id": 1, "action_ids": [2]}}]),
             "set only one of action_id, action_ids"),
            (dict(good, items=[{"id": "x", "variant": "a", "kind": "text_to_3d", "texture": False},
                               {"id": "r", "kind": "rig", "source": "x"}]), "textured models only"),
            (dict(good, items=good["items"][:1] * 2), "used twice"),
            (dict(good, items=[{"id": "x", "variant": "a", "kind": "text_to_3d", "preview": {"ai_model": "meshy-99"}}]),
             "no known price"),
        ]
        for data, message in cases:
            with self.subTest(message=message):
                self.assert_invalid(data, message)

    def test_id_must_match_the_file_name(self) -> None:
        with self.assertRaisesRegex(common.Failure, "differs from the file name"):
            batches.parse(batch_data(), Path("other.toml"))


class ApprovalTest(unittest.TestCase):
    def test_complete_approval_passes(self) -> None:
        self.assertEqual(batches.approval_problems(parse(batch_data())), [])

    def test_missing_approval_fields(self) -> None:
        for name in ("approved_by", "approved_at", "approval_ref"):
            with self.subTest(name=name):
                problems = batches.approval_problems(parse(batch_data(**{name: ""})))
                self.assertIn(f"'{name}' is missing", problems)

    def test_approval_ref_and_date_shapes(self) -> None:
        problems = batches.approval_problems(parse(batch_data(approval_ref="said yes in chat", approved_at="today")))
        self.assertTrue(any("GitHub" in p for p in problems))
        self.assertTrue(any("not a date" in p for p in problems))

    def test_needs_a_licence(self) -> None:
        problems = batches.approval_problems(parse(batch_data(licence="")))
        self.assertIn("'licence' is missing (it goes into every generation.json)", problems)

    def test_estimate_over_the_cap(self) -> None:
        problems = batches.approval_problems(parse(batch_data(credit_cap=55)))
        self.assertTrue(any("exceeds the approved cap of 55" in p for p in problems))


class RepositoryBatchesTest(unittest.TestCase):
    def test_every_committed_batch_is_valid_and_approved(self) -> None:
        files = sorted(batches.BATCHES.glob("*.toml"))
        self.assertTrue(files, "batches/ has no batch")
        for path in files:
            with self.subTest(batch=path.name):
                batch = batches.load(path)
                self.assertEqual(batches.approval_problems(batch), [])

    def test_first_bodies_batch(self) -> None:
        batch = batches.load("2026-10-b1-bodies")
        self.assertEqual([i.id for i in batch.items],
                         [f"v{v}-{n}" for v in (1, 2, 3) for n in (1, 2, 3, 4)])
        self.assertEqual(batch.credits, 360)
        self.assertLessEqual(batch.credits, batch.credit_cap)
        for item in batch.items:
            preview, refine = item.stages
            self.assertEqual(preview.params["pose_mode"], "t-pose")
            self.assertEqual(preview.params["topology"], "triangle")
            self.assertEqual(preview.params["target_polycount"], 7000)
            self.assertFalse(refine.params["enable_pbr"])
            self.assertIn("T-pose", item.prompt)

    def test_raw_toml_has_no_secrets(self) -> None:
        for path in batches.BATCHES.glob("*.toml"):
            data = tomllib.loads(path.read_text(encoding="utf-8"))
            self.assertNotIn("api_key", str(data).lower())

    def test_estimate_command(self) -> None:
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            code = cli.main(["meshy", "estimate", "batches/2026-10-b1-bodies.toml"])
        self.assertEqual(code, 0)
        self.assertIn("total 360 credits; approved cap 360", out.getvalue())
        self.assertIn("approval: complete", out.getvalue())


if __name__ == "__main__":
    unittest.main()
