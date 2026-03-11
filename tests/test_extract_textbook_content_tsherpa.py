import importlib.util
import sys
import unittest
from pathlib import Path


MODULE_PATH = Path(__file__).resolve().parents[1] / "extract-textbook-content" / "tsherpa_teacher_pdf.py"
spec = importlib.util.spec_from_file_location("tsherpa_teacher_pdf", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class TsherpaTeacherPdfTests(unittest.TestCase):
    def test_extract_teacher_pdf_links_prefers_teacher_row(self) -> None:
        html = """
        <table>
          <tr><td>기타 PDF</td><td><a href='other.pdf'>x</a></td></tr>
          <tr>
            <td>지도서 PDF</td>
            <td><a href='lesson1.pdf'>L1</a></td>
            <td><a href='lesson2.pdf'>L2</a></td>
          </tr>
        </table>
        """
        links = module.extract_teacher_pdf_links(html, "https://example.com/path/index.html")
        self.assertEqual(len(links), 2)
        self.assertTrue(links[0].url.endswith("lesson1.pdf"))

    def test_infer_chapter_name(self) -> None:
        self.assertEqual(module.infer_chapter_name("https://a/b/Lesson3_teacher.pdf", 1), "Lesson3")
        self.assertEqual(module.infer_chapter_name("https://a/b/unknown.pdf", 2), "Chapter 2")


if __name__ == "__main__":
    unittest.main()
