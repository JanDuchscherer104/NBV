"""Mermaid backslash transport must not corrupt KaTeX line breaks or operators."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools/mermaid/scripts'))
import aria_mermaid_owners as owner


class TransportTests(unittest.TestCase):
    def test_commands_and_linebreaks_roundtrip(self) -> None:
        tex = r'\begin{cases}x&h>1\\0&\text{otherwise}\end{cases}'
        records = {'equations.demo.eq': tex}
        owners = {'#eqs.demo.eq': 'equations.demo.eq'}
        text = f'flowchart TB\n{owner.OWNERS}\n{owner.ARCHITECTURE}\nA["<b>Cases</b>$$#eqs.demo.eq$$"]:::compute\n'
        compiled, _ = owner.compile_source(text, records, owners)
        self.assertIn(r'\\\\0', compiled)
        self.assertIn(r'\\text{otherwise}', compiled)
        self.assertEqual(owner.check_math(compiled, records), [])
        self.assertEqual(owner.check_architecture(compiled, records), [])
        corrupted = compiled.replace(r'\\\\0', r'\\0')
        self.assertTrue(owner.check_math(corrupted, records))

    def test_transport_directive_cannot_be_injected_into_owner_source(self) -> None:
        text = f'flowchart TB\n{owner.OWNERS}\n{owner.ARCHITECTURE}\n{owner.TRANSPORT}'
        with self.assertRaises(ValueError):
            owner.compile_source(text, {}, {})


if __name__ == '__main__':
    unittest.main()
