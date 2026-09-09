"""Small, dependency-free TeX-like expression renderer backed by MathML."""
from __future__ import annotations

import html
import re


GREEK = {
    "alpha": "α", "beta": "β", "gamma": "γ", "delta": "δ",
    "epsilon": "ε", "varepsilon": "ϵ", "zeta": "ζ", "eta": "η",
    "theta": "θ", "vartheta": "ϑ", "iota": "ι", "kappa": "κ",
    "lambda": "λ", "mu": "μ", "nu": "ν", "xi": "ξ", "pi": "π",
    "rho": "ρ", "sigma": "σ", "tau": "τ", "upsilon": "υ",
    "phi": "φ", "varphi": "ϕ", "chi": "χ", "psi": "ψ", "omega": "ω",
    "Gamma": "Γ", "Delta": "Δ", "Theta": "Θ", "Lambda": "Λ",
    "Xi": "Ξ", "Pi": "Π", "Sigma": "Σ", "Upsilon": "Υ",
    "Phi": "Φ", "Psi": "Ψ", "Omega": "Ω",
}

SYMBOLS = {
    "infty": "∞", "pm": "±", "mp": "∓", "times": "×", "cdot": "·",
    "le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "neq": "≠",
    "approx": "≈", "sim": "∼", "propto": "∝", "to": "→",
    "rightarrow": "→", "leftarrow": "←", "Rightarrow": "⇒",
    "Leftarrow": "⇐", "partial": "∂", "nabla": "∇", "sum": "∑",
    "prod": "∏", "int": "∫", "hbar": "ℏ", "ell": "ℓ",
}

SUPER = str.maketrans({"⁰": "0", "¹": "1", "²": "2", "³": "3", "⁴": "4",
                       "⁵": "5", "⁶": "6", "⁷": "7", "⁸": "8", "⁹": "9"})
SUB = str.maketrans({"₀": "0", "₁": "1", "₂": "2", "₃": "3", "₄": "4",
                     "₅": "5", "₆": "6", "₇": "7", "₈": "8", "₉": "9"})


def _tag(name: str, value: str, attrs: str = "") -> str:
    return f"<{name}{attrs}>{html.escape(value)}</{name}>"


def _row(nodes: list[str]) -> str:
    if not nodes:
        return "<mrow></mrow>"
    if len(nodes) == 1:
        return nodes[0]
    return "<mrow>" + "".join(nodes) + "</mrow>"


class _Parser:
    def __init__(self, source: str):
        self.source = source
        self.index = 0

    def parse(self, stop: str | None = None) -> str:
        nodes: list[str] = []
        while self.index < len(self.source):
            char = self.source[self.index]
            if stop and char == stop:
                self.index += 1
                break
            if char.isspace():
                self.index += 1
                continue
            node = self.atom()
            subscript = superscript = None
            while self.index < len(self.source) and self.source[self.index] in "_^":
                operator = self.source[self.index]
                self.index += 1
                script = self.script_argument()
                if operator == "_":
                    subscript = script
                else:
                    superscript = script
            if subscript is not None and superscript is not None:
                node = f"<msubsup>{node}{subscript}{superscript}</msubsup>"
            elif subscript is not None:
                node = f"<msub>{node}{subscript}</msub>"
            elif superscript is not None:
                node = f"<msup>{node}{superscript}</msup>"
            nodes.append(node)
        return _row(nodes)

    def atom(self) -> str:
        char = self.source[self.index]
        if char == "{":
            self.index += 1
            return self.parse("}")
        if char == "\\":
            return self.command()
        if char.isdigit() or (char == "." and self._peek(1).isdigit()):
            start = self.index
            self.index += 1
            while self.index < len(self.source) and (
                self.source[self.index].isdigit() or self.source[self.index] == "."
            ):
                self.index += 1
            return _tag("mn", self.source[start:self.index])
        if char.isalpha() or char in "αβγδεζηθικλμνξπρστυφχψωΓΔΘΛΞΠΣΥΦΨΩ":
            self.index += 1
            return _tag("mi", char)
        self.index += 1
        return _tag("mo", {"-": "−", "*": "×"}.get(char, char))

    def command(self) -> str:
        self.index += 1
        start = self.index
        while self.index < len(self.source) and self.source[self.index].isalpha():
            self.index += 1
        name = self.source[start:self.index]
        if not name and self.index < len(self.source):
            name = self.source[self.index]
            self.index += 1
        if name == "frac":
            numerator = self.required_group()
            denominator = self.required_group()
            return f"<mfrac>{numerator}{denominator}</mfrac>"
        if name == "sqrt":
            return f"<msqrt>{self.required_group()}</msqrt>"
        if name in {"mathrm", "operatorname"}:
            return f'<mstyle mathvariant="normal">{self.required_group()}</mstyle>'
        if name == "text":
            return _tag("mtext", self.raw_group())
        if name in GREEK:
            return _tag("mi", GREEK[name])
        if name in SYMBOLS:
            return _tag("mo", SYMBOLS[name])
        if name in {",", ";", "quad", "qquad"}:
            width = {",": ".17em", ";": ".28em", "quad": "1em", "qquad": "2em"}[name]
            return f'<mspace width="{width}"></mspace>'
        if name in {"left", "right"}:
            return self.atom() if self.index < len(self.source) else ""
        return _tag("mi", name)

    def required_group(self) -> str:
        while self.index < len(self.source) and self.source[self.index].isspace():
            self.index += 1
        if self.index >= len(self.source) or self.source[self.index] != "{":
            return self.atom() if self.index < len(self.source) else "<mrow></mrow>"
        self.index += 1
        return self.parse("}")

    def raw_group(self) -> str:
        while self.index < len(self.source) and self.source[self.index].isspace():
            self.index += 1
        if self.index >= len(self.source) or self.source[self.index] != "{":
            return ""
        self.index += 1
        start, depth = self.index, 1
        while self.index < len(self.source) and depth:
            if self.source[self.index] == "{":
                depth += 1
            elif self.source[self.index] == "}":
                depth -= 1
            self.index += 1
        return self.source[start:self.index - 1]

    def script_argument(self) -> str:
        while self.index < len(self.source) and self.source[self.index].isspace():
            self.index += 1
        if self.index < len(self.source) and self.source[self.index] == "{":
            self.index += 1
            return self.parse("}")
        return self.atom() if self.index < len(self.source) else "<mrow></mrow>"

    def _peek(self, offset: int) -> str:
        index = self.index + offset
        return self.source[index] if index < len(self.source) else ""


def _normalise_unicode_scripts(source: str) -> str:
    out: list[str] = []
    for char in source:
        if char in "⁰¹²³⁴⁵⁶⁷⁸⁹":
            out.append("^{" + char.translate(SUPER) + "}")
        elif char in "₀₁₂₃₄₅₆₇₈₉":
            out.append("_{" + char.translate(SUB) + "}")
        else:
            out.append(char)
    return "".join(out)


def render_math(source: str, *, display: bool = False) -> str:
    tex = source.strip()
    body = _Parser(_normalise_unicode_scripts(tex)).parse()
    display_attr = ' display="block"' if display else ""
    css_class = "math-display" if display else "math-inline"
    return (
        f'<math class="{css_class}"{display_attr} aria-label="{html.escape(tex, quote=True)}">'
        f'<semantics>{body}<annotation encoding="application/x-tex">'
        f'{html.escape(tex)}</annotation></semantics></math>'
    )


INLINE_MATH_RE = re.compile(r"\\\((.+?)\\\)|(?<!\\)\$(?!\$)(.+?)(?<!\\)\$")


def render_inline_math(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        return render_math(match.group(1) or match.group(2), display=False)

    return INLINE_MATH_RE.sub(replace, text)
