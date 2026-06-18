#
# This file is part of Adiuvo Forgix LiteX Test.
#
# Copyright (c) 2026 Enjoy-Digital
# SPDX-License-Identifier: BSD-2-Clause

import tempfile
import unittest
from pathlib import Path

from tools import csr2py

# Tests --------------------------------------------------------------------------------------------


class CSR2PyTest(unittest.TestCase):
    def test_convert_and_render(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            csr_csv = Path(tmp_dir) / "csr.csv"
            csr_csv.write_text(
                "\n".join([
                    "# kind,name,value",
                    "csr_base,ctrl,0x00000000",
                    "csr_register,ctrl_scratch,0x00000004",
                    "csr_register,leds_out,0x00001000",
                    "constant,config_identifier,LiteX SoC",
                    "constant,config_clock_frequency,32000000",
                    "constant,config_cpu_type_none,None",
                    "memory_region,csr,0x00000000",
                    "",
                ]),
                encoding="utf-8",
            )

            constants = csr2py.convert(csr_csv)
            self.assertIn(("CSR_BASE_CTRL", 0x00000000), constants)
            self.assertIn(("CSR_CTRL_SCRATCH", 0x00000004), constants)
            self.assertIn(("CSR_LEDS_OUT", 0x00001000), constants)
            self.assertIn(("CONFIG_CLOCK_FREQUENCY", 32000000), constants)
            self.assertIn(("CONFIG_CPU_TYPE_NONE", "None"), constants)
            self.assertIn(("MEMORY_CSR", 0x00000000), constants)

            names = [name for name, _ in constants]
            self.assertNotIn("CONFIG_IDENTIFIER", names)

            rendered = csr2py.render(constants, csr_csv)
            self.assertIn("CSR_CTRL_SCRATCH", rendered)
            self.assertIn("CONFIG_CLOCK_FREQUENCY", rendered)
            self.assertIn("CONFIG_CPU_TYPE_NONE", rendered)
            self.assertNotIn("LiteX SoC", rendered)


if __name__ == "__main__":
    unittest.main()
