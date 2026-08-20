from __future__ import annotations

import unittest

from app.parser import decode_text, parse_proxy_text


class ParserTests(unittest.TestCase):
    def test_mixed_formats_and_deduplication(self) -> None:
        parsed = parse_proxy_text(
            """# comment
            1.2.3.4:8080
            http://1.2.3.4:8080
            socks5://user:p%40ss@5.6.7.8:1080
            [2001:db8::1]:8080
            bad entry
            """
        )
        self.assertEqual(parsed.received_lines, 5)
        self.assertEqual(parsed.invalid_lines, 1)
        self.assertEqual(parsed.duplicate_lines, 0)
        self.assertEqual(len(parsed.valid_entries), 4)
        self.assertEqual(parsed.valid_entries[2].password, "p@ss")

    def test_auth_and_comments(self) -> None:
        parsed = parse_proxy_text("user:password@proxy.example:3128  # note\n")
        self.assertEqual(len(parsed.valid_entries), 1)
        proxy = parsed.valid_entries[0]
        self.assertEqual(proxy.username, "user")
        self.assertEqual(proxy.password, "password")
        self.assertEqual(proxy.url(), "http://user:password@proxy.example:3128")

    def test_text_decoding(self) -> None:
        self.assertEqual(decode_text("1.2.3.4:80\n".encode()), "1.2.3.4:80\n")
        with self.assertRaises(ValueError):
            decode_text(b"\x00\x00\x00\x00")


if __name__ == "__main__":
    unittest.main()
