import unittest

from app.extractor import clean_html, extract_relevant_info


class ExtractorTest(unittest.TestCase):
    def test_clean_html_keeps_wikipedia_content_and_collapses_infobox_rows(self):
        html = """
        <html>
          <body>
            <nav>Поиск 23 языка</nav>
            <main>
              <div id="mw-content-text">
                <table class="infobox">
                  <tr><th>Дата рождения</th><td>19 ноября 1900 <sup class="reference">[1]</sup></td></tr>
                  <tr><th>Место рождения</th><td>Казань, Российская империя</td></tr>
                  <tr><th>Дата смерти</th><td>15 октября 1980</td></tr>
                </table>
                <p>Михаи\u0301л Алексе\u0301евич Лавре\u0301нтьев - советский математик и механик.</p>
                <h2>Биография</h2>
                <p>Родился в 1900 году в Казани в семье преподавателя математики.</p>
                <h2>Примечания</h2>
                <p>Михаил Алексеевич Лаврентьев (к 60-летию со дня рождения).</p>
              </div>
            </main>
          </body>
        </html>
        """

        text = clean_html(html)

        self.assertIn("Дата рождения: 19 ноября 1900", text)
        self.assertIn("Место рождения: Казань, Российская империя", text)
        self.assertIn("Михаи\u0301л Алексе\u0301евич Лавре\u0301нтьев - советский математик", text)
        self.assertNotIn("к 60-летию", text)

    def test_extract_relevant_info_matches_accented_name_and_biography_dates(self):
        text = "\n".join(
            [
                "Дата рождения: 19 ноября 1900",
                "Место рождения: Казань, Российская империя",
                "Дата смерти: 15 октября 1980",
                "Михаи\u0301л Алексе\u0301евич Лавре\u0301нтьев - советский математик и механик.",
                "Биография",
                "Родился в 1900 году в Казани в семье преподавателя математики.",
                "В 1927 году защитил диссертацию.",
                "Примечания",
                "Михаил Алексеевич Лаврентьев (к 60-летию со дня рождения).",
            ]
        )

        relevant = extract_relevant_info(text, "Лаврентьев Михаил Алексеевич")

        self.assertIn("Дата рождения: 19 ноября 1900", relevant)
        self.assertIn("Михаи\u0301л Алексе\u0301евич Лавре\u0301нтьев - советский математик", relevant)
        self.assertIn("В 1927 году защитил диссертацию.", relevant)
        self.assertNotIn("к 60-летию", relevant)


if __name__ == "__main__":
    unittest.main()
