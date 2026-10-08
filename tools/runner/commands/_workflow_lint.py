"""The checks of `workflow-check` (#56, docs/agents.md): a small JavaScript tokenizer and the cost-rule refusals.

The tokenizer knows strings, template literals (with nested `${...}`), comments, regex literals, numbers, identifiers
and punctuation; enough to find `agent(...)` calls, read their options and gather the text of their prompts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

MAX_CALLS = 60
AGENT_TYPES = ("art-reader", "art-writer")
BANNED_EFFORTS = ("xhigh", "max")
META_PREFIX = "export const meta"
BOUNDS_RE = re.compile(r"BOUNDS:\s*at most\s+(\d+)\s+tool calls")
WAIT_RE = re.compile(r"no tool call blocks? (?:for )?(?:longer than|over|more than) 180 ?(?:s\b|seconds)", re.I)
GENERAL_RE = re.compile(r"^/\*\s*general-agent:\s*(\S.*?)\s*\*/$", re.S)
NONDETERMINISTIC = (("Date", "now"), ("Math", "random"))
REGEX_AFTER = set("(,=:[!&|?{};+-*%<>~^") | {"=>", "return", "typeof", "case", "do", "else", "in", "of", "new",
                                              "delete", "void", "throw", "yield", "await"}
PUNCT3 = ("===", "!==", "...", "**=", "<<=", ">>=", "&&=", "||=", "??=")
PUNCT2 = ("=>", "==", "!=", "<=", ">=", "&&", "||", "??", "?.", "++", "--", "+=", "-=", "*=", "/=", "%=", "**",
          "<<", ">>", "&=", "|=", "^=")
REGEX_AFTER |= set(PUNCT3 + PUNCT2) - {"++", "--", "?."}


class LexError(Exception):
    def __init__(self, line: int, message: str) -> None:
        super().__init__(message)
        self.line = line


@dataclass
class Token:
    kind: str  # ident, num, str (a quoted string or one chunk of a template literal), regex, punct
    value: str
    line: int
    lead: list[str] = field(default_factory=list)  # the comments right before this token
    template: bool = False


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    comments: list[str] = []
    braces: list[str] = []  # "{" or "${" for each open brace, so a "}" can resume a template literal
    i, line, n = 0, 1, len(text)

    def add(kind: str, value: str, at_line: int, template: bool = False) -> None:
        tokens.append(Token(kind, value, at_line, list(comments), template))
        comments.clear()

    def template_chunk(start: int, start_line: int) -> int:
        """Reads template text from start up to and including "`" or "${"; returns the index after it."""
        j, ln = start, start_line
        while j < n:
            c = text[j]
            if c == "\\":
                j += 2
                continue
            if c == "`":
                add("str", text[start:j], start_line, True)
                return j + 1
            if c == "$" and text.startswith("${", j):
                add("str", text[start:j], start_line, True)
                add("punct", "${", ln)
                braces.append("${")
                return j + 2
            if c == "\n":
                ln += 1
            j += 1
        raise LexError(start_line, "unterminated template literal")

    while i < n:
        c = text[i]
        if c == "\n":
            line += 1
            i += 1
        elif c in " \t\r\f\v﻿":
            i += 1
        elif text.startswith("//", i):
            end = text.find("\n", i)
            end = n if end < 0 else end
            comments.append(text[i:end])
            i = end
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                raise LexError(line, "unterminated comment")
            comments.append(text[i:end + 2])
            line += text.count("\n", i, end)
            i = end + 2
        elif c in "'\"":
            j = i + 1
            while j < n and text[j] != c:
                if text[j] == "\n":
                    raise LexError(line, "unterminated string")
                j += 2 if text[j] == "\\" else 1
            if j >= n:
                raise LexError(line, "unterminated string")
            add("str", text[i + 1:j], line)
            i = j + 1
        elif c == "`":
            start_line = line
            j = template_chunk(i + 1, line)
            line = start_line + text.count("\n", i, j)
            i = j
        elif c.isdigit() or (c == "." and i + 1 < n and text[i + 1].isdigit()):
            m = re.compile(r"0[xXoObB][0-9a-fA-F_]+n?|(?:\d[\d_]*\.?\d*|\.\d+)(?:[eE][+-]?\d+)?n?").match(text, i)
            add("num", m.group(0), line)
            i = m.end()
        elif c.isalpha() or c in "_$":
            m = re.compile(r"[\w$]+").match(text, i)
            add("ident", m.group(0), line)
            i = m.end()
        elif c == "/" and (not tokens or tokens[-1].kind == "punct" and tokens[-1].value in REGEX_AFTER
                           or tokens[-1].kind == "ident" and tokens[-1].value in REGEX_AFTER
                           or tokens[-1].value == "${"):
            j, in_class = i + 1, False
            while j < n and (in_class or text[j] != "/"):
                if text[j] == "\n":
                    raise LexError(line, "unterminated regular expression")
                if text[j] == "\\":
                    j += 1
                elif text[j] == "[":
                    in_class = True
                elif text[j] == "]":
                    in_class = False
                j += 1
            m = re.compile(r"[a-z]*").match(text, j + 1)
            add("regex", text[i:m.end()], line)
            i = m.end()
        else:
            for size, options in ((3, PUNCT3), (2, PUNCT2)):
                if text[i:i + size] in options:
                    add("punct", text[i:i + size], line)
                    i += size
                    break
            else:
                if c == "{":
                    braces.append("{")
                elif c == "}" and braces and braces.pop() == "${":
                    add("punct", "}", line)
                    start_line = line
                    j = template_chunk(i + 1, line)
                    line = start_line + text.count("\n", i, j)
                    i = j
                    continue
                add("punct", c, line)
                i += 1
    return tokens


OPEN = {"(": ")", "[": "]", "{": "}", "${": "}"}


def matching(tokens: list[Token], start: int) -> int:
    """The index of the token closing the bracket at start."""
    depth = 0
    for k in range(start, len(tokens)):
        t = tokens[k]
        if t.kind == "punct" and t.value in OPEN:
            depth += 1
        elif t.kind == "punct" and t.value in ")]}":
            depth -= 1
            if depth == 0:
                return k
    raise LexError(tokens[start].line, f"unclosed {tokens[start].value!r}")


def split_top(tokens: list[Token], start: int, end: int) -> list[tuple[int, int]]:
    """The comma-separated parts of tokens[start:end] at bracket depth 0, as (start, end) index pairs."""
    parts, depth, begin = [], 0, start
    for k in range(start, end):
        t = tokens[k]
        if t.kind == "punct" and t.value in OPEN:
            depth += 1
        elif t.kind == "punct" and t.value in ")]}":
            depth -= 1
        elif t.kind == "punct" and t.value == "," and depth == 0:
            parts.append((begin, k))
            begin = k + 1
    if begin < end:
        parts.append((begin, end))
    return parts


class Script:
    def __init__(self, text: str) -> None:
        self.tokens = tokenize(text)
        self.decls = self._declarations()

    def _declarations(self) -> dict[str, tuple[int, int]]:
        """name -> token span of its initializer or function, for `const|let|var NAME = ...` and `function NAME`."""
        found: dict[str, tuple[int, int]] = {}
        toks = self.tokens
        for k, t in enumerate(toks[:-2]):
            if t.kind != "ident" or toks[k + 1].kind != "ident" or toks[k + 1].value in found:
                continue
            if t.value in ("const", "let", "var") and toks[k + 2].value == "=":
                start, depth, end = k + 3, 0, k + 3
                while end < len(toks):
                    v = toks[end]
                    if v.kind == "punct" and v.value in OPEN:
                        depth += 1
                    elif v.kind == "punct" and v.value in ")]}":
                        if depth == 0:
                            break
                        depth -= 1
                    elif depth == 0 and v.kind == "punct" and v.value in ";,":
                        break
                    elif depth == 0 and end > start and v.kind == "ident" and v.value in (
                            "const", "let", "var", "function", "export"):
                        break
                    end += 1
                found[toks[k + 1].value] = (start, end)
            elif t.value == "function":
                brace = next((m for m in range(k + 2, len(toks)) if toks[m].value == "{"), None)
                if brace is not None:
                    found[toks[k + 1].value] = (k + 2, matching(toks, brace) + 1)
        return found

    def text_of(self, start: int, end: int, seen: set[str] | None = None) -> str:
        """The string text of a token span, chunks joined by NUL, plus the text of every name it uses."""
        seen = set() if seen is None else seen
        pieces, names = [], []
        for t in self.tokens[start:end]:
            if t.kind == "str":
                pieces.append(t.value)
            elif t.kind == "ident" and t.value in self.decls and t.value not in seen:
                seen.add(t.value)
                names.append(t.value)
        for name in names:
            pieces.append(self.text_of(*self.decls[name], seen))
        return "\0".join(pieces)

    def object_props(self, start: int, end: int, seen: set[str] | None = None) -> dict[str, Token | None] | None:
        """The properties of an object literal span ({...} or a name bound to one): key -> its value token when the
        value is one string literal, else None. None when the span is not an object literal."""
        seen = set() if seen is None else seen
        toks = self.tokens
        if end - start == 1 and toks[start].kind == "ident" and toks[start].value in self.decls:
            name = toks[start].value
            if name in seen:
                return None
            seen.add(name)
            return self.object_props(*self.decls[name], seen)
        if not (toks[start].value == "{" and toks[start].kind == "punct" and matching(toks, start) == end - 1):
            return None
        props: dict[str, Token | None] = {}
        for a, b in split_top(toks, start + 1, end - 1):
            if toks[a].value == "...":
                inner = self.object_props(a + 1, b, seen)
                if inner is None:
                    return None
                props.update(inner)
            elif b - a >= 3 and toks[a + 1].value == ":" and toks[a].kind in ("ident", "str"):
                value = toks[a + 2] if b - a == 3 and toks[a + 2].kind == "str" and not toks[a + 2].template \
                    else None
                props[toks[a].value] = value
            elif b - a == 1 and toks[a].kind == "ident":
                props[toks[a].value] = None  # shorthand {model}: not a literal
        return props


def check_meta(script: Script, text: str) -> list[tuple[int, str]]:
    toks = script.tokens
    if not text.startswith(META_PREFIX) or [t.value for t in toks[:4]] != ["export", "const", "meta", "="] or len(toks) < 5 or toks[4].value != "{":
        return [(1, f"must start with `{META_PREFIX} = {{...}}`")]
    end = matching(toks, 4)
    for k in range(5, end):
        t = toks[k]
        if t.kind in ("num", "str") or t.kind == "punct" and t.value in ("{", "}", "[", "]", ",", ":", "-"):
            continue
        if t.kind == "ident" and (t.value in ("true", "false", "null") or toks[k + 1].value == ":"):
            continue
        return [(t.line, f"`meta` must be a pure literal; found `{t.value}`")]
    return []


def meta_end(text: str) -> int | None:
    """The character offset just after `export const meta = {...}` (and a `;` right after it), or None. Strings and
    `//` and `/* */` comments inside `meta` are skipped, so a quote or a brace in them does not end it early."""
    depth, i, n = 0, text.find("{"), len(text)
    if not text.startswith(META_PREFIX) or i < 0:
        return None
    quote = ""
    while i < n:
        c = text[i]
        if quote:
            if c == "\\":
                i += 1
            elif c == quote:
                quote = ""
        elif c in "'\"`":
            quote = c
        elif text.startswith("//", i):
            end = text.find("\n", i)
            i = n if end < 0 else end
            continue
        elif text.startswith("/*", i):
            end = text.find("*/", i + 2)
            if end < 0:
                return None
            i = end + 2
            continue
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                i += 1
                return i + 1 if text[i:i + 1] == ";" else i
        i += 1
    return None


def check_agents(script: Script) -> list[tuple[int, str]]:
    toks, found = script.tokens, []
    for k, t in enumerate(toks):
        if not (t.kind == "ident" and t.value == "agent" and k + 1 < len(toks) and toks[k + 1].value == "("):
            continue
        if k > 0 and toks[k - 1].kind == "punct" and toks[k - 1].value in (".", "?."):
            found.append((t.line, "a member call `x.agent(` is not checked; call the global agent()"))
            continue
        if k > 0 and toks[k - 1].kind == "ident" and toks[k - 1].value in ("function", "const", "let", "var"):
            continue
        close = matching(toks, k + 1)
        args = split_top(toks, k + 2, close)
        lead = t.lead or (toks[k - 1].lead if k > 0 and toks[k - 1].value == "await" else [])
        general = bool(lead) and GENERAL_RE.match(lead[-1].strip()) is not None
        if not args:
            found.append((t.line, "agent() has no prompt"))
            continue
        props = script.object_props(*args[1]) if len(args) > 1 else None
        if props is None:
            found.append((t.line, "agent() needs an options object literal (or a const bound to one)"))
            props = {}
        kind = props.get("agentType")
        if "agentType" in props and kind is None:
            found.append((t.line, "agentType must be a string literal"))
        elif kind is not None and kind.value not in AGENT_TYPES:
            found.append((t.line, f"agentType {kind.value!r} is not 'art-reader' or 'art-writer'"))
        elif kind is None and not general:
            found.append((t.line, "agent() has no agentType 'art-reader' | 'art-writer' "
                                  "(or a `/* general-agent: <reason> */` comment right before it)"))
        for key in ("model", "effort"):
            if key in props and props[key] is None:
                found.append((t.line, f"{key} must be a string literal so workflow-check can read it"))
        model = props.get("model")
        if kind is not None and kind.value == "art-reader" and model is not None and "opus" in model.value.lower():
            found.append((t.line, "an art-reader agent runs on Sonnet, not model 'opus'"))
        prompt = script.text_of(*args[0])
        bounds = [int(m.group(1)) for m in BOUNDS_RE.finditer(prompt)]
        if not bounds:
            found.append((t.line, f"the agent prompt has no `BOUNDS: at most N tool calls` (N <= {MAX_CALLS}) "
                                  "in one string literal"))
        elif max(bounds) > MAX_CALLS:
            found.append((t.line, f"the agent prompt allows {max(bounds)} tool calls; at most {MAX_CALLS}"))
    return found


def check_tokens(script: Script) -> list[tuple[int, str]]:
    toks, found = script.tokens, []
    for k, t in enumerate(toks[:-2]):
        if t.kind in ("ident", "str") and t.value == "effort" and toks[k + 1].value == ":" \
                and toks[k + 2].kind == "str" and toks[k + 2].value in BANNED_EFFORTS:
            found.append((t.line, f"effort {toks[k + 2].value!r} is not allowed; builders run at 'high'"))
        for obj, member in NONDETERMINISTIC:
            if t.value == obj and toks[k + 1].value == "." and toks[k + 2].value == member:
                found.append((t.line, f"{obj}.{member}() breaks resume; workflow scripts are deterministic"))
        if t.value == "new" and toks[k + 1].value == "Date" and k + 3 < len(toks) and toks[k + 2].value == "(" \
                and toks[k + 3].value == ")":
            found.append((t.line, "new Date() breaks resume; workflow scripts are deterministic"))
    if not any(WAIT_RE.search(" ".join(t.value.split())) for t in toks if t.kind == "str"):
        found.append((1, "the script never states the 180 s wait rule "
                         "(a string with \"no tool call blocks over 180 s\")"))
    return found


def check_text(text: str) -> list[tuple[int, str]]:
    """Every refusal of the static checks, as (line, message), sorted by line. node --check runs separately."""
    found: list[tuple[int, str]] = []
    if "\r" in text:
        found.append((text[:text.index("\r")].count("\n") + 1, "line endings are not LF (CRLF is refused at resume)"))
        text = text.replace("\r\n", "\n")
    try:
        script = Script(text)
    except LexError as exc:
        return found + [(exc.line, f"cannot read the script: {exc}")]
    try:
        found += check_meta(script, text) + check_agents(script) + check_tokens(script)
    except LexError as exc:
        found.append((exc.line, f"cannot read the script: {exc}"))
    except IndexError:
        found.append((len(script.tokens) and script.tokens[-1].line, "cannot read the script: it ends early"))
    return sorted(found)


def module_copy(text: str) -> str | None:
    """The script as an ES module node can parse: the body after `meta` wrapped in an async function (it may use
    top-level `await` and `return`), on the same line so node's line numbers match the script's; a `;` ends `meta`
    first when the script has none. None without meta."""
    end = meta_end(text)
    if end is None:
        return None
    head = text[:end] if text[:end].endswith(";") else text[:end] + ";"  # `meta = {...}` may end without one
    return head + " async function __workflow_body__() {" + text[end:] + "\n}\n"
