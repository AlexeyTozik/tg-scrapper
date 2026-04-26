import io
import unittest
from contextlib import redirect_stdout
from unittest.mock import Mock, patch

from tg_scrapper.cli import format_commands_help, main


class CLITests(unittest.TestCase):
    def test_root_help_lists_commands(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            main(["--help"])

        rendered = stdout.getvalue()
        self.assertIn("Available commands:", rendered)
        self.assertIn("export", rendered)
        self.assertIn("query", rendered)

    def test_dispatches_to_subcommand_entrypoint(self) -> None:
        handler = Mock()
        with patch("tg_scrapper.cli.resolve_entrypoint", return_value=handler):
            main(["query", "--question", "Talos?"])

        handler.assert_called_once_with(["--question", "Talos?"])

    def test_dispatches_from_sys_argv_when_called_as_console_script(self) -> None:
        handler = Mock()
        with (
            patch("sys.argv", ["tg-scrapper", "channels", "--session", "./session_name.session"]),
            patch("tg_scrapper.cli.resolve_entrypoint", return_value=handler),
        ):
            main()

        handler.assert_called_once_with(["--session", "./session_name.session"])

    def test_format_commands_help_mentions_all_public_commands(self) -> None:
        rendered = format_commands_help()
        for command in ("channels", "export", "embed", "index", "query"):
            with self.subTest(command=command):
                self.assertIn(command, rendered)


if __name__ == "__main__":
    unittest.main()
