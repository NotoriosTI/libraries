"""Visual smoke test — 4 main ConfigManager loading scenarios.

GCP cases use real credentials when .env.smoke is present at the project root:
    SMOKE_GCP_PROJECT_ID=your-project-id
    (GCP Secret Manager must have secrets named JUAN_DB_NAME, JUAN_DB_HOST,
     JUAN_DB_PORT, JUAN_DB_USER)

Without .env.smoke the GCP cases fall back to a mock loader (no network, no creds).
All resolved values are always masked — real secrets are never printed.

Run with:
    uv run python tests/smoke/smoke_visual.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from dotenv import dotenv_values
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

import env_manager.manager as manager_module
from env_manager import ConfigManager
from env_manager.loaders import DotEnvLoader
from env_manager.utils import mask_secret

console = Console()
FIXTURES = Path(__file__).parent / "fixtures"

# ---------------------------------------------------------------------------
# Load smoke config (.env.smoke is gitignored — never committed)
# ---------------------------------------------------------------------------

_SMOKE_ENV = PROJECT_ROOT / ".env.smoke"
_smoke_cfg: dict[str, str] = {}
if _SMOKE_ENV.exists():
    _smoke_cfg = {k: v for k, v in dotenv_values(str(_SMOKE_ENV)).items() if v}

REAL_GCP = bool(_smoke_cfg.get("SMOKE_GCP_PROJECT_ID"))
GCP_PROJECT_ID: str = _smoke_cfg.get("SMOKE_GCP_PROJECT_ID", "mock-project")

# ---------------------------------------------------------------------------
# Env-var isolation
# ---------------------------------------------------------------------------

# Vars to scrub at case START so the case doesn't inherit caller shell state.
_SCRUB_ON_ENTRY = (
    "JUAN_DB_NAME", "JUAN_DB_HOST", "JUAN_DB_PORT", "JUAN_DB_USER",
    "GCP_PROJECT_ID", "SECRET_ORIGIN", "ENVIRONMENT",
)


@contextmanager
def isolated_env(label: str):
    """Full os.environ snapshot/restore + singleton reset.

    On enter:
      - Scrub known test vars so each case starts from a clean slate.
      - Assert that ConfigManager singleton is clear.
    On exit:
      - Restore os.environ byte-for-byte to its pre-case state, regardless of
        what ConfigManager.load() or any loader wrote to it during the case.
      - Reset singleton again.

    This prevents both directions of leakage:
      * Shell state → test case  (handled by _SCRUB_ON_ENTRY)
      * Test case  → next case   (handled by full snapshot restore)
    """
    full_snapshot = dict(os.environ)
    manager_module._SINGLETON = None

    # Verify singleton is truly cleared
    assert manager_module._SINGLETON is None, "Singleton not cleared before case"

    scrubbed: list[str] = []
    for k in _SCRUB_ON_ENTRY:
        if k in os.environ:
            os.environ.pop(k)
            scrubbed.append(k)

    console.print(
        f"  [dim]env isolation:[/dim] scrubbed {scrubbed or ['(none)']}, "
        f"snapshot of {len(full_snapshot)} vars saved"
    )

    try:
        yield
    finally:
        # Capture what the case wrote before restoring
        added = [k for k in os.environ if k not in full_snapshot]
        modified = [k for k in os.environ if k in full_snapshot and os.environ[k] != full_snapshot[k]]

        os.environ.clear()
        os.environ.update(full_snapshot)
        manager_module._SINGLETON = None

        console.print(
            f"  [dim]env restore:[/dim] reverted {len(added)} added, "
            f"{len(modified)} modified var(s) → os.environ back to pre-case state"
        )


# ---------------------------------------------------------------------------
# Loader interception — confirms a fresh loader is created per case
# ---------------------------------------------------------------------------

def _make_loader_spy(real_gcp: bool):
    """Return a create_loader wrapper that logs each instantiation."""
    loader_log: list[str] = []

    _original = manager_module.create_loader

    def _mock_gcp_loader(origin, *, gcp_project_id=None, dotenv_path=None):
        if origin == "gcp":
            loader_log.append(f"GCP(mock, project={gcp_project_id})")
            return _MockGCPLoader()
        loader_log.append(f"DotEnv(path={Path(dotenv_path).name if dotenv_path else None})")
        return DotEnvLoader(dotenv_path=dotenv_path)

    def _spy_real_loader(origin, *, gcp_project_id=None, dotenv_path=None):
        if origin == "gcp":
            loader_log.append(f"GCP(real, project={gcp_project_id})")
        else:
            loader_log.append(f"DotEnv(path={Path(dotenv_path).name if dotenv_path else None})")
        return _original(origin, gcp_project_id=gcp_project_id, dotenv_path=dotenv_path)

    wrapper = _spy_real_loader if real_gcp else _mock_gcp_loader
    return wrapper, loader_log


class _MockGCPLoader:
    _SECRETS = {
        "JUAN_DB_NAME":  "juandb",
        "JUAN_DB_HOST":  "127.0.0.1",
        "JUAN_DB_PORT":  "5432",
        "JUAN_DB_USER":  "automation_admin",
    }

    def get_many(self, keys: list[str]) -> dict[str, str | None]:
        return {k: self._SECRETS.get(k) for k in keys}

    def get(self, key: str) -> str | None:
        return self._SECRETS.get(key)


# ---------------------------------------------------------------------------
# The 4 cases
# ---------------------------------------------------------------------------

_VARS = ("JUAN_DB_NAME", "JUAN_DB_HOST", "JUAN_DB_PORT", "JUAN_DB_USER")

_DOTENV_CONTENT = (
    "JUAN_DB_NAME=juandb\n"
    "JUAN_DB_HOST=127.0.0.1\n"
    "JUAN_DB_PORT=5432\n"
    "JUAN_DB_USER=automation_admin\n"
)


def case_1_old_dotenv(tmp: Path) -> dict[str, Any]:
    cfg = tmp / "config.yaml"
    env = tmp / ".env"
    cfg.write_text((FIXTURES / "old_dotenv.yaml").read_text(), encoding="utf-8")
    env.write_text(_DOTENV_CONTENT, encoding="utf-8")
    mgr = ConfigManager(str(cfg), secret_origin="local", dotenv_path=str(env), debug=False)
    return {k: mgr.get(k) for k in _VARS}


def case_2_old_gcp(tmp: Path) -> dict[str, Any]:
    cfg = tmp / "config.yaml"
    cfg.write_text((FIXTURES / "old_gcp.yaml").read_text(), encoding="utf-8")
    mgr = ConfigManager(str(cfg), secret_origin="gcp", gcp_project_id=GCP_PROJECT_ID, debug=False)
    return {k: mgr.get(k) for k in _VARS}


def case_3_new_gcp(tmp: Path) -> dict[str, Any]:
    cfg = tmp / "config.yaml"
    cfg.write_text((FIXTURES / "new_format.yaml").read_text(), encoding="utf-8")
    os.environ["ENVIRONMENT"] = "gcp"
    mgr = ConfigManager(str(cfg), secret_origin="gcp", gcp_project_id=GCP_PROJECT_ID, debug=False)
    return {k: mgr.get(k) for k in _VARS}


def case_4_new_dotenv(tmp: Path) -> dict[str, Any]:
    cfg = tmp / "config.yaml"
    env = tmp / ".env"
    cfg.write_text((FIXTURES / "new_format.yaml").read_text(), encoding="utf-8")
    env.write_text(_DOTENV_CONTENT, encoding="utf-8")
    os.environ["ENVIRONMENT"] = "local"
    mgr = ConfigManager(str(cfg), secret_origin="local", dotenv_path=str(env), debug=False)
    return {k: mgr.get(k) for k in _VARS}


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _safe_display(value: Any) -> Text:
    if value is None:
        return Text("None", style="dim red")
    return Text(mask_secret(str(value)), style="bold white")


def _values_table(values: dict[str, Any], loader_log: list[str], elapsed: float) -> Table:
    tbl = Table(box=box.SIMPLE, show_header=True, header_style="bold dim", padding=(0, 1))
    tbl.add_column("variable", style="dim")
    tbl.add_column("value (masked)")
    tbl.add_column("loaded", justify="center")
    for k, v in values.items():
        loaded = Text("✓", style="green") if v is not None else Text("✗", style="red")
        tbl.add_row(k, _safe_display(v), loaded)
    tbl.add_section()
    tbl.add_row(
        "[dim]loaders created[/dim]",
        Text(", ".join(loader_log) if loader_log else "none", style="dim cyan"),
        "",
    )
    tbl.add_row("[dim]elapsed[/dim]", Text(f"{elapsed:.2f}s", style="dim"), "")
    return tbl


CASES = [
    ("1", "Old format — .env", "old", "local", False, case_1_old_dotenv, "old_dotenv.yaml"),
    ("2", "Old format — GCP",  "old", "gcp",   True,  case_2_old_gcp,    "old_gcp.yaml"),
    ("3", "New format — GCP",  "new", "gcp",   True,  case_3_new_gcp,    "new_format.yaml"),
    ("4", "New format — .env", "new", "local", False, case_4_new_dotenv, "new_format.yaml"),
]


def _case_title(num: str, label: str, fmt: str, origin: str, uses_gcp: bool, fixture: str) -> Text:
    fmt_color = "cyan" if fmt == "new" else "yellow"
    origin_color = "magenta" if origin == "gcp" else "green"
    t = Text()
    t.append(f"Case {num}: ", style="bold")
    t.append(label)
    t.append(f"  [{fmt}]", style=f"bold {fmt_color}")
    t.append(f" [{origin}]", style=f"bold {origin_color}")
    if uses_gcp:
        badge, style = ("real GCP", "bold bright_magenta") if REAL_GCP else ("mocked", "dim")
        t.append(f"  [{badge}]", style=style)
    t.append(f"  [dim]{fixture}[/dim]")
    return t


def run_all() -> None:
    console.print(Rule("[bold white]env-manager smoke test[/bold white]"))
    gcp_line = (
        Text(f"  GCP project: {GCP_PROJECT_ID}  (secrets: JUAN_DB_*)", style="bright_magenta")
        if REAL_GCP
        else Text("  GCP: .env.smoke not found — GCP cases use mock loader", style="dim yellow")
    )
    console.print(gcp_line)
    console.print()

    results: list[tuple[str, bool, float]] = []

    for num, label, fmt, origin, uses_gcp, fn, fixture in CASES:
        console.print(Rule(f"[dim]Case {num}[/dim]", style="dim"))

        spy, loader_log = _make_loader_spy(REAL_GCP and uses_gcp)

        with isolated_env(label):
            with tempfile.TemporaryDirectory() as tmpdir:
                tmp = Path(tmpdir)
                t0 = time.perf_counter()
                try:
                    with patch("env_manager.manager.create_loader", side_effect=spy):
                        values = fn(tmp)
                    elapsed = time.perf_counter() - t0
                    passed = all(v is not None for v in values.values())
                    status = Text("✓ PASS", style="bold green") if passed else Text("⚠ PARTIAL", style="bold yellow")
                    content = _values_table(values, loader_log, elapsed)
                except Exception as exc:
                    elapsed = time.perf_counter() - t0
                    passed = False
                    status = Text("✗ FAIL", style="bold red")
                    content = Text(str(exc), style="red")

        title = _case_title(num, label, fmt, origin, uses_gcp, fixture)
        title.append("  ")
        title.append_text(status)
        console.print(Panel(content, title=title, border_style="dim"))
        console.print()
        results.append((label, passed, elapsed))

    # Summary
    console.print(Rule("[bold white]summary[/bold white]"))
    summary = Table(box=box.ROUNDED, show_header=True, header_style="bold")
    summary.add_column("#", justify="center", width=3)
    summary.add_column("Case")
    summary.add_column("Time", justify="right")
    summary.add_column("Result", justify="center")

    for i, (label, passed, elapsed) in enumerate(results, 1):
        result_text = Text("✓ PASS", style="bold green") if passed else Text("✗ FAIL", style="bold red")
        summary.add_row(str(i), label, f"{elapsed:.2f}s", result_text)

    console.print(summary)

    total = len(results)
    passed_count = sum(1 for _, p, _ in results if p)
    if passed_count == total:
        console.print(f"\n[bold green]All {total} cases passed.[/bold green]\n")
    else:
        console.print(f"\n[bold red]{total - passed_count}/{total} cases failed.[/bold red]\n")
        sys.exit(1)


if __name__ == "__main__":
    run_all()
