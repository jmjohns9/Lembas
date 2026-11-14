"""Shared helpers for the test suite: paths, module loaders and fixture builders.

Importing this module puts squeeze.py, ithildin.py and tests/ on sys.path and points both scripts'
caches at a temporary folder that is removed when the test process exits.
"""
import atexit
import contextlib
import importlib.util
import io
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from xml.sax.saxutils import escape

TESTS = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(TESTS)
LEMBAS = os.path.join(ROOT, "skills", "lembas")
ITHILDIN = os.path.join(ROOT, "skills", "ithildin")
SQUEEZE_PY = os.path.join(LEMBAS, "scripts", "squeeze.py")
HOOK_PY = os.path.join(LEMBAS, "hooks", "squeeze_hook.py")
ITHILDIN_PY = os.path.join(ITHILDIN, "scripts", "ithildin.py")

for _p in (os.path.dirname(SQUEEZE_PY), os.path.dirname(ITHILDIN_PY), TESTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

TMP = tempfile.mkdtemp(prefix="lembas-tests-")
atexit.register(shutil.rmtree, TMP, ignore_errors=True)
os.environ["LEMBAS_SQUEEZE_DIR"] = os.path.join(TMP, "squeeze-cache")
os.environ["ITHILDIN_CACHE"] = os.path.join(TMP, "ithildin-cache")

_built = {}


def tmp(*parts):
    """A path under the suite's temporary folder; parent folders are created."""
    path = os.path.join(TMP, *parts)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return path


def write(path, text, encoding="utf-8"):
    with open(path, "w", encoding=encoding, newline="") as fh:
        fh.write(text)
    return path


def read(path, encoding="utf-8"):
    with open(path, encoding=encoding, newline="") as fh:
        return fh.read()


def load_script(name, path):
    """Import a script that is not on sys.path (the hook, scripts/, evals/) as a module."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(cmd, data=None, env=None, cwd=None):
    """Run a command; return the completed process with bytes in stdout and stderr."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return subprocess.run(cmd, input=data, capture_output=True, env=dict(os.environ, **(env or {})), cwd=cwd)


def run_py(script, *args, **kw):
    return run([sys.executable, script] + list(args), **kw)


def capture(fn, *args, **kw):
    """Call fn and return what it printed to stdout."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        fn(*args, **kw)
    return out.getvalue()


# ---------------------------------------------------------------- squeeze fixtures

def squeeze_fixtures():
    """Folder holding app.log, orders.json, events.jsonl, sales.csv and answers.json (built once)."""
    if "squeeze" not in _built:
        folder = os.path.join(TMP, "squeeze-fixtures")
        subprocess.run([sys.executable, os.path.join(TESTS, "make_fixtures.py"), folder], check=True,
                       stdout=subprocess.DEVNULL)
        _built["squeeze"] = folder
    return _built["squeeze"]


# ---------------------------------------------------------------- ithildin fixtures

def manual_docs():
    """The test manual in every format that can be built here: {file name: path}.

    Markdown is always built. The Word file needs python-docx and the PDFs need reportlab.
    """
    if "manual" not in _built:
        import ithildin_fixtures as fx
        folder = os.path.join(TMP, "manual")
        os.makedirs(folder, exist_ok=True)
        blocks = fx.build_model()
        docs = {"manual.md": os.path.join(folder, "manual.md")}
        fx.write_markdown(blocks, docs["manual.md"])
        try:
            fx.write_docx(blocks, os.path.join(folder, "manual.docx"))
            docs["manual.docx"] = os.path.join(folder, "manual.docx")
        except ImportError:
            pass
        try:
            fx.write_pdf(blocks, os.path.join(folder, "manual.pdf"), bookmarks=True)
            fx.write_pdf(blocks, os.path.join(folder, "manual-flat.pdf"), bookmarks=False)
            docs["manual.pdf"] = os.path.join(folder, "manual.pdf")
            docs["manual-flat.pdf"] = os.path.join(folder, "manual-flat.pdf")
        except ImportError:
            pass
        _built["manual"] = docs
    return _built["manual"]


def ithildin_out(*argv):
    """Run ithildin's main() in-process and return its stdout."""
    import ithildin
    return capture(ithildin.main, list(argv))


# Word and PowerPoint files are zip archives of XML. These builders write the smallest valid ones,
# with the standard library only, so tests can cover shapes the document libraries cannot produce.

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
P_NS = "http://schemas.openxmlformats.org/presentationml/2006/main"
A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"
R_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_RELS_NS = "http://schemas.openxmlformats.org/package/2006/relationships"


def w_p(text, style=None, outline=None):
    """A Word paragraph. style is a paragraph style id; outline is a zero-based outline level."""
    props = ""
    if style:
        props += f'<w:pStyle w:val="{style}"/>'
    if outline is not None:
        props += f'<w:outlineLvl w:val="{outline}"/>'
    props = f"<w:pPr>{props}</w:pPr>" if props else ""
    return f'<w:p>{props}<w:r><w:t xml:space="preserve">{escape(text)}</w:t></w:r></w:p>'


def w_tbl(rows):
    """A Word table from a list of rows of cell text."""
    return "<w:tbl>" + "".join(
        "<w:tr>" + "".join(f"<w:tc>{w_p(cell)}</w:tc>" for cell in row) + "</w:tr>" for row in rows) + "</w:tbl>"


def w_sdt(inner):
    """A Word content control wrapping block-level XML."""
    return f"<w:sdt><w:sdtPr/><w:sdtContent>{inner}</w:sdtContent></w:sdt>"


def make_docx(path, body_xml, styles_xml=None):
    document = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                f'<w:document xmlns:w="{W_NS}"><w:body>{body_xml}</w:body></w:document>')
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("word/document.xml", document)
        if styles_xml is not None:
            z.writestr("word/styles.xml", f'<?xml version="1.0" encoding="UTF-8"?>'
                                          f'<w:styles xmlns:w="{W_NS}">{styles_xml}</w:styles>')
    return path


def _a_p(text):
    return f"<a:p><a:r><a:t>{escape(text)}</a:t></a:r></a:p>"


def make_pptx(path, slides, order=None, presentation=True):
    """Write a deck. slides is a list of (title, [body paragraphs], table rows or None).

    Slide i is stored as ppt/slides/slide<i+1>.xml. `order` lists those file numbers in the order
    the deck presents them (default: file order), which is how PowerPoint records a reordering.
    With presentation=False the deck has no ppt/presentation.xml at all.
    """
    order = order or list(range(1, len(slides) + 1))
    with zipfile.ZipFile(path, "w") as z:
        for i, (title, body, table) in enumerate(slides, 1):
            shapes = ""
            if title is not None:
                shapes += ('<p:sp><p:nvSpPr><p:nvPr><p:ph type="title"/></p:nvPr></p:nvSpPr>'
                           f"<p:txBody>{_a_p(title)}</p:txBody></p:sp>")
            if body:
                shapes += ('<p:sp><p:nvSpPr><p:nvPr><p:ph idx="1"/></p:nvPr></p:nvSpPr>'
                           f'<p:txBody>{"".join(_a_p(t) for t in body)}</p:txBody></p:sp>')
            if table:
                cells = "".join("<a:tr>" + "".join(f"<a:tc><a:txBody>{_a_p(c)}</a:txBody></a:tc>" for c in row)
                                + "</a:tr>" for row in table)
                shapes += f"<p:graphicFrame><a:graphic><a:graphicData><a:tbl>{cells}</a:tbl></a:graphicData></a:graphic></p:graphicFrame>"
            z.writestr(f"ppt/slides/slide{i}.xml",
                       f'<?xml version="1.0" encoding="UTF-8"?><p:sld xmlns:p="{P_NS}" xmlns:a="{A_NS}">'
                       f"<p:cSld><p:spTree>{shapes}</p:spTree></p:cSld></p:sld>")
        if presentation:
            ids = "".join(f'<p:sldId id="{255 + k}" r:id="rId{n}"/>' for k, n in enumerate(order, 1))
            z.writestr("ppt/presentation.xml",
                       f'<?xml version="1.0" encoding="UTF-8"?><p:presentation xmlns:p="{P_NS}" xmlns:r="{R_NS}">'
                       f"<p:sldIdLst>{ids}</p:sldIdLst></p:presentation>")
            rels = "".join(f'<Relationship Id="rId{n}" Type="{R_NS}/slide" Target="slides/slide{n}.xml"/>'
                           for n in range(1, len(slides) + 1))
            z.writestr("ppt/_rels/presentation.xml.rels",
                       f'<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="{PKG_RELS_NS}">{rels}</Relationships>')
    return path
