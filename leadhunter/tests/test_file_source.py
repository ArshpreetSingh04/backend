import json
import os
import sys
import tempfile
import unittest

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, os.pardir))
)

from leadhunter.ingestion.sources.file_source import (
    FileSource,
    UnsupportedFileFormatError,
)


class FileSourceTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def _path(self, name):
        return os.path.join(self.tmp.name, name)

    def _write(self, name, text):
        path = self._path(name)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(text)
        return path

    def test_requires_network_is_false(self):
        src = FileSource(self._write("a.csv", "email\nx@y.com\n"))
        self.assertFalse(src.requires_network)

    def test_csv_parses_rows(self):
        path = self._write(
            "leads.csv",
            "email,name,company\n"
            "jane@example.com,Jane,Example Inc\n"
            "john@acme.io,John,Acme\n",
        )
        rows = list(FileSource(path).records())
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["email"], "jane@example.com")
        self.assertEqual(rows[1]["company"], "Acme")

    def test_csv_skips_blank_rows(self):
        path = self._write(
            "leads.csv",
            "email,name\njane@example.com,Jane\n,\n\njohn@acme.io,John\n",
        )
        rows = list(FileSource(path).records())
        self.assertEqual(len(rows), 2)

    def test_json_array(self):
        path = self._write(
            "leads.json",
            json.dumps(
                [
                    {"email": "jane@example.com", "company": "Example"},
                    {"email": "john@acme.io", "company": "Acme"},
                ]
            ),
        )
        rows = list(FileSource(path).records())
        self.assertEqual([r["email"] for r in rows], ["jane@example.com", "john@acme.io"])

    def test_json_single_object(self):
        path = self._write("one.json", json.dumps({"email": "solo@example.com"}))
        rows = list(FileSource(path).records())
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["email"], "solo@example.com")

    def test_jsonl(self):
        path = self._write(
            "leads.jsonl",
            '{"email": "a@x.com"}\n'
            "\n"
            '{"email": "b@x.com"}\n',
        )
        rows = list(FileSource(path).records())
        self.assertEqual([r["email"] for r in rows], ["a@x.com", "b@x.com"])

    def test_empty_file_yields_nothing(self):
        self.assertEqual(list(FileSource(self._write("empty.json", "")).records()), [])
        self.assertEqual(list(FileSource(self._write("empty.csv", "")).records()), [])
        self.assertEqual(list(FileSource(self._write("empty.jsonl", "")).records()), [])

    def test_unsupported_extension_raises(self):
        path = self._write("leads.txt", "whatever")
        with self.assertRaises(UnsupportedFileFormatError):
            list(FileSource(path).records())

    def test_custom_name(self):
        src = FileSource(self._path("x.csv"), name="my-source")
        self.assertEqual(src.name, "my-source")


if __name__ == "__main__":
    unittest.main()
