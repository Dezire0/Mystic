from __future__ import annotations

import unittest

from mystic.tools.python_runner import PythonRunner


class PythonRunnerTests(unittest.TestCase):
    def test_runner_executes_safe_code(self):
        result = PythonRunner().run("print('ok')\n")
        self.assertTrue(result.success)
        self.assertEqual(result.stdout.strip(), "ok")

    def test_runner_blocks_shellish_imports(self):
        result = PythonRunner().run("import os\nprint('bad')\n")
        self.assertTrue(result.blocked)


if __name__ == "__main__":
    unittest.main()

