import unittest

from streamlit.testing.v1 import AppTest


class StreamlitSmokeTest(unittest.TestCase):
    def test_every_page_opens_without_an_error(self) -> None:
        app = AppTest.from_file("prompt_ui.py", default_timeout=10).run()
        self.assertEqual(len(app.exception), 0)

        for page in (
            "Meetings",
            "Intelligence",
            "Action tracker",
            "Notifications",
            "Integrations",
        ):
            app.sidebar.radio[0].set_value(page).run()
            self.assertEqual(len(app.exception), 0, f"The {page} page has an error.")


if __name__ == "__main__":
    unittest.main()
