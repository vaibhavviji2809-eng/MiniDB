from __future__ import annotations

from dataclasses import dataclass

from .errors import LexerError


KEYWORDS = {
    "SELECT",
    "FROM",
    "WHERE",
    "INSERT",
    "INTO",
    "VALUES",
    "CREATE",
    "TABLE",
    "DROP",
    "UPDATE",
    "SET",
    "DELETE",
    "BEGIN",
    "COMMIT",
    "ROLLBACK",
    "INT",
    "STRING",
    "AND",
    "OR",
    "EXPLAIN",
    "ANALYZE",
    "JOIN",
    "INNER",
    "LEFT",
    "RIGHT",
    "OUTER",
    "ON",
    "AS",
    "STORAGE",
    "COLUMN",
    "ROW",
}


@dataclass(frozen=True)
class Token:
    type: str
    value: object
    position: int


class Lexer:
    def tokenize(self, text: str) -> list[Token]:
        tokens: list[Token] = []
        i = 0
        while i < len(text):
            ch = text[i]
            if ch.isspace():
                i += 1
                continue
            if ch == ",":
                tokens.append(Token("COMMA", ",", i))
                i += 1
                continue
            if ch == ".":
                tokens.append(Token("DOT", ".", i))
                i += 1
                continue
            if ch == ";":
                tokens.append(Token("SEMICOLON", ";", i))
                i += 1
                continue
            if ch == "(":
                tokens.append(Token("LPAREN", "(", i))
                i += 1
                continue
            if ch == ")":
                tokens.append(Token("RPAREN", ")", i))
                i += 1
                continue
            if ch == "*":
                tokens.append(Token("STAR", "*", i))
                i += 1
                continue
            if ch in "=!<>":
                start = i
                if i + 1 < len(text) and text[i + 1] == "=":
                    tokens.append(Token("OPERATOR", text[i : i + 2], start))
                    i += 2
                else:
                    tokens.append(Token("OPERATOR", ch, start))
                    i += 1
                continue
            if ch in ('"', "'"):
                quote = ch
                start = i
                i += 1
                value = []
                while i < len(text) and text[i] != quote:
                    if text[i] == "\\" and i + 1 < len(text):
                        i += 1
                    value.append(text[i])
                    i += 1
                if i >= len(text):
                    raise LexerError(f"Unterminated string at {start}")
                i += 1
                tokens.append(Token("STRING_LITERAL", "".join(value), start))
                continue
            if ch.isdigit():
                start = i
                while i < len(text) and (text[i].isdigit() or text[i] == "."):
                    i += 1
                literal = text[start:i]
                tokens.append(Token("NUMBER", int(literal) if "." not in literal else float(literal), start))
                continue
            if ch.isalpha() or ch == "_":
                start = i
                while i < len(text) and (text[i].isalnum() or text[i] == "_"):
                    i += 1
                value = text[start:i]
                upper = value.upper()
                if upper in KEYWORDS:
                    tokens.append(Token(upper, upper, start))
                else:
                    tokens.append(Token("IDENTIFIER", value, start))
                continue
            raise LexerError(f"Unexpected character {ch!r} at {i}")
        tokens.append(Token("EOF", None, len(text)))
        return tokens
