"""Small offline tests; no browser, AI API, backend, network or external image assets."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image

SKILL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "scripts"))
import render_figure as mod  # noqa: E402


class FigureRendererTests(unittest.TestCase):
    def test_all_example_specs_validate_and_render(self):
        tokens = json.loads((SKILL / "assets/design-tokens.json").read_text(encoding="utf-8"))
        specs=list((SKILL / "examples").glob("*.json"))
        self.assertGreaterEqual(len(specs),4)
        for p in specs:
            with self.subTest(p=p.name):
                obj=json.loads(p.read_text(encoding="utf-8"))
                arts=mod.check_spec(obj,p)
                out=mod.render(obj,arts,tokens)
                self.assertEqual(out.width,1680)
                self.assertEqual(out.height,1690 if len(obj["cards"])>3 else 1100)
                mobile=mod.render_mobile(obj,arts,tokens)
                self.assertEqual(mobile.width,720)
                self.assertGreater(mobile.height,1300)
                with tempfile.TemporaryDirectory() as td:
                    target=Path(td)/"sample.webp"
                    out.save(target,quality=90)
                    with Image.open(target) as verify:
                        verify.verify()

    def test_missing_art_fails_closed(self):
        p=SKILL/"examples/01_case_setup.json"
        obj=json.loads(p.read_text(encoding="utf-8"))
        obj["cards"][0]["illustration"]="art/does-not-exist.png"
        with self.assertRaises(ValueError):
            mod.check_spec(obj,p)

    def test_art_cannot_escape_example_root(self):
        p=SKILL/"examples/01_case_setup.json"
        obj=json.loads(p.read_text(encoding="utf-8"))
        obj["cards"][0]["illustration"]="../assets/approved-bottle-case-pallet-setup.png"
        with self.assertRaises(ValueError):
            mod.check_spec(obj,p)

    def test_evidence_figures_need_provenance(self):
        p=SKILL/"examples/01_case_setup.json"
        obj=json.loads(p.read_text(encoding="utf-8"))
        obj["role"]="evidence_derived"
        obj.pop("source_notes",None)
        with self.assertRaises(ValueError):
            mod.check_spec(obj,p)

    def test_one_or_five_card_layouts_supported(self):
        p=SKILL/"examples/01_case_setup.json"
        obj=json.loads(p.read_text(encoding="utf-8"))
        tokens=json.loads((SKILL/"assets/design-tokens.json").read_text(encoding="utf-8"))
        one={**obj,"cards":obj["cards"][:1],"layout":"single_explainer"}
        self.assertEqual(mod.render(one,mod.check_spec(one,p),tokens).size,(1680,1100))
        five={**obj,"cards":obj["cards"]+obj["cards"][:2],"layout":"summary"}
        self.assertEqual(mod.render(five,mod.check_spec(five,p),tokens).size,(1680,1690))


if __name__=="__main__":
    unittest.main()
