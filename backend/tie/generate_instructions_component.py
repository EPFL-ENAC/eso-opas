#!/usr/bin/env python3
"""
Generate frontend/src/components/InstructionsCard.vue from backend/tie/ToolConfiguration.md.

This script has zero external dependencies — it only uses the Python standard library.
It performs a simple Markdown-to-HTML conversion and embeds the result in a Quasar
Vue single-file component, with every H2 section after the first wrapped in a
QExpansionItem for collapsibility.
"""

import html as html_module
import re
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent.parent  # backend/tie -> backend -> repo root

MD_PATH = REPO_ROOT / "backend" / "tie" / "ToolConfiguration.md"
VUE_PATH = REPO_ROOT / "frontend" / "src" / "components" / "InstructionsCard.vue"


def escape_html(text: str) -> str:
    return html_module.escape(text)


def escape_attr(text: str) -> str:
    """Escape a string for use inside a double-quoted HTML attribute."""
    return text.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")


def capitalize_first(text: str) -> str:
    if text:
        return text[0].upper() + text[1:]
    return text


def strip_inline_markdown(text: str) -> str:
    """Remove inline Markdown formatting and return plain text."""
    text = text.replace(r"\[", "[").replace(r"\]", "]")
    text = re.sub(r"`([^`]+)`", r"\1", text)  # inline code
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # bold
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"\1", text)  # italic
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)  # links → just text
    return text


def inline_to_html(text: str) -> str:
    """
    Convert inline Markdown elements to HTML.
    Handles: escaped brackets, inline code, bold, italic, links.
    """
    text = text.replace(r"\[", "[").replace(r"\]", "]")

    parts = []
    last_end = 0
    for m in re.finditer(r"`([^`]+)`", text):
        parts.append(escape_html(text[last_end : m.start()]))
        parts.append(f"<code>{escape_html(m.group(1))}</code>")
        last_end = m.end()
    parts.append(escape_html(text[last_end:]))
    text = "".join(parts)

    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2" target="_blank" class="text-primary">\1</a>',
        text,
    )

    return text


def parse_markdown(md_text: str) -> list[dict]:
    """
    Parse simple Markdown into a list of blocks.
    Each block is a dict with keys: type, plus relevant data.
    """
    lines = md_text.split("\n")
    blocks: list[dict] = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            lang = stripped[3:].strip()
            i += 1
            code_lines = []
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1
            blocks.append({"type": "code", "lang": lang, "content": "\n".join(code_lines)})
            continue

        m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if m:
            level = len(m.group(1))
            blocks.append({"type": "heading", "level": level, "content": m.group(2)})
            i += 1
            continue

        if re.match(r"^[-*]\s", stripped):
            items = []
            while i < n:
                l = lines[i].strip()
                if not l:
                    i += 1
                    continue
                if re.match(r"^[-*]\s", l):
                    items.append(re.sub(r"^[-*]\s+", "", l))
                    i += 1
                else:
                    break
            blocks.append({"type": "list", "items": items})
            continue

        if not stripped:
            i += 1
            continue

        para_lines = [stripped]
        i += 1
        while i < n:
            l = lines[i].strip()
            if not l or l.startswith("#") or l.startswith("```") or re.match(r"^[-*]\s", l):
                break
            para_lines.append(l)
            i += 1
        blocks.append({"type": "paragraph", "content": " ".join(para_lines)})

    return blocks


def build_sections(blocks: list[dict]) -> list[dict]:
    """
    Group blocks into sections, using H1 and H2 as section boundaries.
    H3+ headings remain inside their parent H2 section as regular blocks.
    """
    sections: list[dict] = []
    current: dict | None = None

    for block in blocks:
        if block["type"] == "heading":
            level = block["level"]
            if level == 1:
                if current is not None:
                    sections.append(current)
                current = {"level": 1, "heading": block["content"], "blocks": []}
            elif level == 2:
                if current is not None:
                    sections.append(current)
                current = {"level": 2, "heading": block["content"], "blocks": []}
            else:
                # H3+ → keep inside current H2 section
                if current is not None:
                    current["blocks"].append(block)
        else:
            if current is not None:
                current["blocks"].append(block)

    if current is not None:
        sections.append(current)

    return sections


def block_to_html(block: dict, indent: str = "") -> str:
    """Convert a single parsed block into an HTML string."""
    btype = block["type"]

    if btype == "heading":
        level = block["level"]
        content = inline_to_html(capitalize_first(block["content"]))
        if level == 1:
            cls = "text-h5"
        elif level == 2:
            cls = "text-h6"
        else:
            cls = "text-subtitle1"
        return f'{indent}<h{level} class="{cls} q-mt-md q-mb-sm">{content}</h{level}>'

    if btype == "paragraph":
        content = inline_to_html(block["content"])
        return f'{indent}<p class="q-mb-sm">{content}</p>'

    if btype == "list":
        items_html = "".join(f'<li class="q-mb-xs">{inline_to_html(item)}</li>' for item in block["items"])
        return f'{indent}<ul class="q-mb-md">{items_html}</ul>'

    if btype == "code":
        lang = block["lang"]
        code = escape_html(block["content"])
        lang_cls = f" language-{escape_html(lang)}" if lang else ""
        return (
            f'{indent}<pre class="q-mb-md">'
            f'<code class="bg-grey-2 q-pa-sm rounded-borders block{lang_cls}">{code}</code>'
            f"</pre>"
        )

    return ""


def generate_vue_component(sections: list[dict]) -> str:
    """Build the Quasar Vue SFC from parsed sections."""
    if len(sections) < 2:
        raise ValueError("Expected at least an H1 and one H2 section in the markdown")

    lines: list[str] = []
    lines.append("<template>")
    lines.append('  <q-card flat bordered style="max-width: 800px; margin: 0 auto">')
    lines.append("    <q-card-section>")

    # H1 title
    h1 = sections[0]
    h1_html = inline_to_html(capitalize_first(h1["heading"]))
    lines.append(f'      <h1 class="text-h5 q-mt-md q-mb-sm">{h1_html}</h1>')

    # First H2 — rendered directly (non-collapsible)
    first_h2 = sections[1]
    h2_html = inline_to_html(capitalize_first(first_h2["heading"]))
    lines.append(f'      <h2 class="text-h6 q-mt-md q-mb-sm">{h2_html}</h2>')
    for block in first_h2["blocks"]:
        lines.append("      " + block_to_html(block))

    lines.append("    </q-card-section>")

    # Subsequent H2 sections — collapsible via QExpansionItem
    for section in sections[2:]:
        label = capitalize_first(strip_inline_markdown(section["heading"]))
        lines.append(
            f'    <q-expansion-item expand-separator label="{escape_attr(label)}" header-class="text-h6 text-weight-medium">'
        )
        lines.append("      <q-card-section>")
        for block in section["blocks"]:
            lines.append("        " + block_to_html(block))
        lines.append("      </q-card-section>")
        lines.append("    </q-expansion-item>")

    lines.append("  </q-card>")
    lines.append("</template>")

    lines.append("")
    lines.append('<script setup lang="ts">')
    lines.append("// No script logic required — everything is static template markup.")
    lines.append("</script>")
    lines.append("")
    lines.append("<style scoped>")
    lines.append(":deep(pre) { margin: 0; }")
    lines.append(":deep(ul) { padding-left: 1.25rem; }")
    lines.append(":deep(a) { text-decoration: none; }")
    lines.append("</style>")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    md_text = MD_PATH.read_text(encoding="utf-8")
    blocks = parse_markdown(md_text)
    sections = build_sections(blocks)
    vue_source = generate_vue_component(sections)

    VUE_PATH.parent.mkdir(parents=True, exist_ok=True)
    VUE_PATH.write_text(vue_source, encoding="utf-8")
    print(f"Generated {VUE_PATH}")


if __name__ == "__main__":
    main()
