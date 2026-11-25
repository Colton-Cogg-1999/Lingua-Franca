import csv
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from simulation.run import audit

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("c++"), "native simulation requires a C++17 compiler")
class ProvincesTests(unittest.TestCase):
    def test_paired_run_replay_and_route_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            binary = root / "provinces"
            subprocess.run(
                [
                    "c++",
                    "-std=c++17",
                    "-O2",
                    str(ROOT / "simulation/provinces.cpp"),
                    "-o",
                    str(binary),
                ],
                check=True,
            )
            for name in ("first", "again"):
                directory = root / name
                directory.mkdir()
                subprocess.run(
                    [str(binary), "1", "12", "100", str(directory)], check=True
                )
                self.assertEqual(audit(directory, 12, 100), 6 * 12 * (10 + 3 * 90))
            for file in (root / "first").iterdir():
                self.assertEqual(
                    file.read_bytes(), (root / "again" / file.name).read_bytes()
                )

            path = root / "first/routes.csv"
            with path.open() as stream:
                reader = csv.DictReader(stream)
                rows = list(reader)
                columns = reader.fieldnames
            forbidden = next(
                r
                for r in rows
                if r["history"] == "sealed"
                and r["round"] == "30"
                and r["listener_town"] != r["speaker_town"]
            )
            forbidden["conversations"] = "1"
            with path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, columns)
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaisesRegex(ValueError, "outside an allowed route"):
                audit(path.parent, 12, 100)
