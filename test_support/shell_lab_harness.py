from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tempfile


@dataclass(frozen=True)
class LauncherResult:
    completed: bool
    returncode: int | None
    stdout: str
    stderr: str
    create_log: str


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def run_forwarded_launcher(repository: Path, lab: str) -> LauncherResult:
    """Run a real forwarded launcher against deterministic external fakes."""
    with tempfile.TemporaryDirectory() as directory:
        fixture = Path(directory)
        run_path = fixture / "labs" / lab / "run.sh"
        run_path.parent.mkdir(parents=True)
        shutil.copy2(repository / "labs" / lab / "run.sh", run_path)
        (fixture / "container").mkdir()
        (fixture / "container" / "Containerfile").write_text("", encoding="utf-8")
        (fixture / "policies").mkdir()
        (fixture / "state").mkdir()
        (fixture / "state" / "lab3-image.env").write_text(
            "IMAGE=localhost/openshell-lab-agent:abcdef1\n", encoding="utf-8"
        )

        fake_bin = fixture / "fake-bin"
        fake_bin.mkdir()
        fake_state = fixture / "fake-state"
        fake_state.mkdir()
        _write_executable(
            fake_bin / "podman",
            """#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == image && "${2:-}" == inspect ]]; then
    printf '1500:1500\\n'
fi
""",
        )
        _write_executable(
            fake_bin / "curl",
            """#!/usr/bin/env bash
exit 0
""",
        )
        _write_executable(
            fake_bin / "openshell",
            """#!/usr/bin/env bash
set -euo pipefail
case "${1:-} ${2:-}" in
    "sandbox list"|"sandbox delete"|"forward stop")
        exit 0
        ;;
    "sandbox create")
        printf 'sandbox-created\\n' >&2
        printf 'forward-ready\\n' >&2
        sleep 30 >&2 &
        exit 0
        ;;
    "sandbox exec")
        if [[ "${LAB_UNDER_TEST:-}" == lab3 \
            && "$*" == *"python3 -m openshell_lab.cli"* \
            && ! -f "${FAKE_STATE:?}/allowed" ]]; then
            exit 1
        fi
        exit 0
        ;;
    "policy get")
        printf '{}\\n'
        ;;
    "policy set")
        touch "${FAKE_STATE:?}/allowed"
        ;;
    *)
        printf 'unexpected openshell invocation: %s\\n' "$*" >&2
        exit 2
        ;;
esac
""",
        )
        environment = {
            **os.environ,
            "FAKE_STATE": str(fake_state),
            "LAB_UNDER_TEST": lab,
            "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
        }
        process = subprocess.Popen(
            [str(run_path)],
            cwd=fixture,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        completed = True
        try:
            stdout, stderr = process.communicate(timeout=2)
        except subprocess.TimeoutExpired:
            completed = False
            stdout = ""
            stderr = ""
        finally:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            if not completed:
                stdout, stderr = process.communicate(timeout=2)

        create_logs = list(fixture.glob("evidence/**/sandbox-create.log"))
        create_log = (
            create_logs[0].read_text(encoding="utf-8") if create_logs else ""
        )
        return LauncherResult(
            completed=completed,
            returncode=process.returncode,
            stdout=stdout,
            stderr=stderr,
            create_log=create_log,
        )


def run_cpu_lab_sequence(sequence_script: Path) -> list[str]:
    with tempfile.TemporaryDirectory() as directory:
        fixture = Path(directory)
        copied_script = fixture / "infra" / "remote" / "run-cpu-labs.sh"
        copied_script.parent.mkdir(parents=True)
        shutil.copy2(sequence_script, copied_script)

        event_log = fixture / "events.log"
        for lab, commands in {
            "lab1": ("run", "verify"),
            "lab2": ("configure-host", "run", "verify"),
            "lab3": ("build", "run", "verify"),
        }.items():
            lab_dir = fixture / "labs" / lab
            lab_dir.mkdir(parents=True)
            for command in commands:
                _write_executable(
                    lab_dir / f"{command}.sh",
                    "#!/usr/bin/env bash\n"
                    f"printf '{lab}-{command}\\n' >>\"${{EVENT_LOG:?}}\"\n",
                )

        fake_bin = fixture / "fake-bin"
        fake_bin.mkdir()
        _write_executable(
            fake_bin / "openshell",
            """#!/usr/bin/env bash
set -euo pipefail
printf 'forward-stop:%s:%s\\n' "${3:-}" "${4:-}" >>"${EVENT_LOG:?}"
""",
        )
        subprocess.run(
            [str(copied_script)],
            cwd=fixture,
            env={
                **os.environ,
                "EVENT_LOG": str(event_log),
                "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            },
            text=True,
            capture_output=True,
            check=True,
        )
        return event_log.read_text(encoding="utf-8").splitlines()


def restricted_search_path() -> str:
    directory = Path(tempfile.mkdtemp())
    for command in ("bash", "git", "grep", "mktemp", "rm"):
        resolved = shutil.which(command)
        if resolved is None:
            raise AssertionError(f"required test command not found: {command}")
        (directory / command).symlink_to(resolved)
    return str(directory)


def run_secret_scan_without_rg(scanner: Path) -> tuple[str, subprocess.CompletedProcess]:
    secret = "sk-" + "B" * 32
    search_path = restricted_search_path()
    try:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "unsafe.txt").write_text(
                f"OPENAI_API_KEY={secret}\n", encoding="utf-8"
            )
            result = subprocess.run(
                [str(scanner), str(root)],
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "LC_ALL": "C", "PATH": search_path},
            )
    finally:
        shutil.rmtree(search_path)
    return secret, result


def run_secret_scan_with_failing_search(scanner: Path) -> subprocess.CompletedProcess:
    search_path = restricted_search_path()
    grep_path = Path(search_path) / "grep"
    grep_path.unlink()
    _write_executable(grep_path, "#!/usr/bin/env bash\nexit 2\n")
    try:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "safe.txt").write_text("ordinary content\n", encoding="utf-8")
            return subprocess.run(
                [str(scanner), str(root)],
                text=True,
                capture_output=True,
                check=False,
                env={**os.environ, "LC_ALL": "C", "PATH": search_path},
            )
    finally:
        shutil.rmtree(search_path)
