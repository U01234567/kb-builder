"""start.py: set up and update kb-builder, in the terminal. Standard library only.

Built around our university's setup: a shared Linux server with NVIDIA GPUs and no administrator
rights for generating, and Windows or macOS laptops for reviewing. Adapt it freely to yours:
kb-builder itself only needs Python, the packages in requirements.txt and, for generating, Ollama.

Started by start_kb-builder_Linux.sh, start_kb-builder_Mac.command or start_kb-builder_Windows.bat,
which only find a Python that is new enough. The steps:

1. Check Python and Git.
2. Offer a newer version from GitHub ("Update now?"). /project/ is never touched.
3. Create .venv and install requirements.txt.
4. Create /project/ from /project-example/ the first time.
5. On Linux with NVIDIA GPUs: put the pinned Ollama in tools/ollama/.
6. Say what to do next, or open the review app.

Every line is also written to start_kb-builder.log in the repository folder.
"""

import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "start_kb-builder.log"
OLLAMA_VERSION = "0.12.6"  # pinned on purpose; a newer one is a decision (docs/decisions.md)
OLLAMA_DIR = ROOT / "tools" / "ollama"
WINDOWS = os.name == "nt"
VENV_PYTHON = ROOT / ".venv" / ("Scripts/python.exe" if WINDOWS else "bin/python")


def say(line: str = "") -> None:
    """Print a line and add it to the log."""
    print(line)
    with LOG.open("a", encoding="utf-8") as log:
        log.write(line + "\n")


def run(command: list[str]) -> subprocess.CompletedProcess:
    """Run a command in the repository folder; its output goes to the log, not the screen."""
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    with LOG.open("a", encoding="utf-8") as log:
        log.write(f"$ {' '.join(command)}\n{result.stdout}{result.stderr}\n")
    return result


def ask(question: str) -> bool:
    """A yes/no question; no means no, and so does having no terminal to ask in."""
    return sys.stdin.isatty() and input(f"{question} [y/N] ").strip().lower() == "y"


def version_in(settings_text: str) -> str:
    """The KB_BUILDER_VERSION written in a config/settings.py text."""
    found = re.search(r'KB_BUILDER_VERSION[^"\']*["\']([^"\']+)["\']', settings_text)
    return found.group(1) if found else "unknown"


def check_python_and_git() -> str:
    """Stop when Python is too old or Git is missing; otherwise report their versions."""
    if sys.version_info < (3, 12):
        raise SystemExit(f"Python 3.12 or newer is needed; this is {platform.python_version()}.")
    if not shutil.which("git"):
        raise SystemExit("Git is missing. Install it from https://git-scm.com and start again.")
    return f"Python {platform.python_version()}, {run(['git', '--version']).stdout.strip()}"


def offer_update() -> str:
    """Compare the version here with the one on GitHub, and update after a yes (then start again)."""
    if not (ROOT / ".git").is_dir():
        return "Not a Git copy (unpacked ZIP?): update check skipped."
    if run(["git", "fetch", "origin"]).returncode != 0:
        return "GitHub could not be reached: continuing with the version on this computer."
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    local = version_in((ROOT / "config" / "settings.py").read_text(encoding="utf-8"))
    newest = version_in(run(["git", "show", f"origin/{branch}:config/settings.py"]).stdout)
    if newest in (local, "unknown"):
        return f"kb-builder {local} is the newest version."
    if not ask(f"kb-builder {newest} is available; you have {local}. Update now? Your /project/ folder is kept either way."):
        return f"Staying on {local}; {newest} is available."
    if run(["git", "pull", "--ff-only"]).returncode != 0:
        raise SystemExit("The update failed, probably because files of kb-builder itself were changed here. See the log.")
    say(f"Updated to {newest}. Start again to continue with the new version.")
    raise SystemExit(0)


def install_packages() -> str:
    """Create .venv when it is missing, and install requirements.txt into it."""
    if not VENV_PYTHON.exists() and run([sys.executable, "-m", "venv", str(ROOT / ".venv")]).returncode != 0:
        raise SystemExit("Could not create .venv. See the log.")
    result = run([str(VENV_PYTHON), "-m", "pip", "install", "--disable-pip-version-check", "-q", "-r", "requirements.txt"])
    if result.returncode != 0:
        raise SystemExit(f"Installing the packages failed:\n{result.stderr.strip()[-600:]}")
    return "All packages are installed in .venv."


def create_project() -> str:
    """Copy project-example/ to project/ the first time; an existing project/ is never touched."""
    if (ROOT / "project").exists():
        return "project/ is there."
    shutil.copytree(ROOT / "project-example", ROOT / "project")
    return "Created project/ from project-example/. Put your own project.toml, prompts, materials and kb.xlsx there."


def install_ollama() -> str:
    """The pinned Ollama release, unpacked into tools/ollama (no administrator rights needed).

    Asked once: a computer with GPUs may still be used for reviewing only.
    """
    marker = OLLAMA_DIR / "VERSION"
    if marker.is_file() and marker.read_text().strip() == OLLAMA_VERSION:
        return f"Ollama {OLLAMA_VERSION} is there."
    if not marker.is_file() and not ask("This computer has GPUs. Set it up for generating (downloads Ollama, about 2 GB)?"):
        return "Ollama skipped: this computer will only review."
    shutil.rmtree(OLLAMA_DIR, ignore_errors=True)
    OLLAMA_DIR.mkdir(parents=True)
    for name in ("ollama-linux-amd64.tgz", "ollama-linux-amd64.tar.zst"):  # the archive name differs per release
        url = f"https://github.com/ollama/ollama/releases/download/v{OLLAMA_VERSION}/{name}"
        archive = OLLAMA_DIR.parent / name
        try:
            say(f"      Downloading {url} …")
            urllib.request.urlretrieve(url, archive)
        except urllib.error.HTTPError:
            continue
        result = run(["tar", "-xf", str(archive), "-C", str(OLLAMA_DIR)])
        archive.unlink()
        if result.returncode != 0:
            raise SystemExit(f"Unpacking {name} failed: {result.stderr.strip()}")
        marker.write_text(OLLAMA_VERSION)
        return f"Ollama {OLLAMA_VERSION} installed in tools/ollama."
    raise SystemExit(f"Ollama {OLLAMA_VERSION} could not be downloaded. Check https://github.com/ollama/ollama/releases.")


def main() -> None:
    """Run the steps in order, then point to what comes next on this kind of computer."""
    LOG.write_text("", encoding="utf-8")
    say(f"kb-builder start · {platform.platform()} · {ROOT}")
    gpu_server = platform.system() == "Linux" and shutil.which("nvidia-smi")
    steps = [("Python and Git", check_python_and_git), ("Updates", offer_update),
             ("Packages", install_packages), ("Project folder", create_project)]
    steps += [("Ollama", install_ollama)] if gpu_server else []
    for number, (title, step) in enumerate(steps, start=1):
        say(f"[{number}/{len(steps)}] {title}")
        say(f"      {step()}")
    python = VENV_PYTHON.relative_to(ROOT)
    if gpu_server:
        say(f"\nReady. Next, in this folder:\n  {python} manage.py preflight\n  {python} manage.py generate")
    elif ask("\nReady. Open the review app now?"):
        subprocess.run([str(VENV_PYTHON), "manage.py", "review"], cwd=ROOT)
    else:
        say(f"\nReady. To review later, in this folder:\n  {python} manage.py review")


if __name__ == "__main__":
    main()
