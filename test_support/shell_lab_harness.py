from dataclasses import dataclass
import io
import os
from pathlib import Path
import shutil
import signal
import subprocess
import tarfile
import tempfile


@dataclass(frozen=True)
class LauncherResult:
    completed: bool
    returncode: int | None
    stdout: str
    stderr: str
    create_log: str
    events: tuple[str, ...]


@dataclass(frozen=True)
class CpuStartResult:
    process: subprocess.CompletedProcess[str]
    aws_calls: tuple[str, ...]


@dataclass(frozen=True)
class EvidenceCollectorResult:
    process: subprocess.CompletedProcess[str]
    collected: dict[str, str]
    ssh_commands: tuple[str, ...]


@dataclass(frozen=True)
class SecretScanCaseResult:
    search_tool: str
    credential_form: str
    value: str
    process: subprocess.CompletedProcess[str]


EVIDENCE_FILENAMES = {
    "CPU": (
        "filesystem-denial.txt",
        "forward-unit.txt",
        "health.txt",
        "image-identity.txt",
        "listener.txt",
        "namespace-denial.txt",
        "network-denial.log",
        "policy.json",
        "probe.json",
        "process-status.txt",
        "sandbox-create.log",
    ),
    "GPU": (
        "agent-result.json",
        "gpus.txt",
        "policy.json",
        "sandbox-create.log",
    ),
}


def evidence_archive_members(
    collector: str, content: str = "current evidence\n"
) -> list[tuple[str, str, str]]:
    directory = "lab4" if collector == "CPU" else "gpu"
    return [
        (f"{directory}/{name}", content, "file")
        for name in EVIDENCE_FILENAMES[collector]
    ]


def run_gpu_profile_detector(
    detector: Path, gpu_names: tuple[str, ...]
) -> subprocess.CompletedProcess:
    """Run the production GPU profile detector against a fake nvidia-smi."""
    with tempfile.TemporaryDirectory() as directory:
        fake_bin = Path(directory) / "fake-bin"
        fake_bin.mkdir()
        _write_executable(
            fake_bin / "nvidia-smi",
            """#!/usr/bin/env bash
set -euo pipefail
[[ "$*" == "--query-gpu=name --format=csv,noheader" ]]
printf '%s\\n' "${GPU_NAMES:?}"
""",
        )
        return subprocess.run(
            [str(detector)],
            text=True,
            capture_output=True,
            check=False,
            env={
                **os.environ,
                "GPU_NAMES": "\n".join(gpu_names),
                "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            },
        )


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def run_cpu_start(repository: Path, instance_type: str) -> CpuStartResult:
    """Run the real CPU start lifecycle against a deterministic AWS fake."""
    with tempfile.TemporaryDirectory() as directory:
        fixture = Path(directory)
        aws_dir = fixture / "infra" / "aws"
        aws_dir.mkdir(parents=True)
        shutil.copy2(repository / "infra" / "aws" / "lib.sh", aws_dir)
        shutil.copy2(repository / "infra" / "aws" / "start-cpu.sh", aws_dir)

        state_dir = fixture / "state"
        state_dir.mkdir()
        (state_dir / "cpu-connection.env").write_text(
            "AWS_REGION=us-east-1\n"
            "INSTANCE_ID=i-0123456789abcdef0\n"
            "PUBLIC_IP=192.0.2.10\n"
            "PRIVATE_IP=10.0.0.10\n"
            "SUBNET_ID=subnet-0123456789abcdef0\n"
            "SECURITY_GROUP_ID=sg-0123456789abcdef0\n"
            "SSH_USER=ec2-user\n"
            "SSH_KEY_PATH=/fixture/id_rsa\n",
            encoding="utf-8",
        )

        fake_bin = fixture / "fake-bin"
        fake_bin.mkdir()
        call_log = fixture / "aws-calls.log"
        _write_executable(
            fake_bin / "aws",
            """#!/usr/bin/env bash
set -euo pipefail
arguments=$*
printf '%s\n' "$arguments" >>"${AWS_CALL_LOG:?}"
if [[ "$arguments" == *" ec2 describe-tags "* \
    && "$arguments" == *"Name=key,Values=Project"* ]]; then
    printf 'openshell-four-labs\n'
elif [[ "$arguments" == *" ec2 describe-tags "* \
    && "$arguments" == *"Name=key,Values=Role"* ]]; then
    printf 'cpu\n'
elif [[ "$arguments" == *" ec2 describe-instances "* \
    && "$arguments" == *"InstanceType"* \
    && "$arguments" == *"Project"* \
    && "$arguments" == *"Role"* ]]; then
    printf '%s\topenshell-four-labs\tcpu\n' "${CPU_TEST_INSTANCE_TYPE:?}"
elif [[ "$arguments" == *" ec2 describe-instances "* \
    && "$arguments" == *"State.Name"* ]]; then
    printf 'stopped\n'
elif [[ "$arguments" == *" ec2 describe-instances "* \
    && "$arguments" == *"PublicIpAddress"* ]]; then
    printf '192.0.2.10\n'
elif [[ "$arguments" == *" ec2 describe-instances "* \
    && "$arguments" == *"PrivateIpAddress"* ]]; then
    printf '10.0.0.10\n'
elif [[ "$arguments" == *" ec2 start-instances "* ]]; then
    exit 0
elif [[ "$arguments" == *" ec2 wait "* ]]; then
    exit 0
else
    printf 'unexpected AWS invocation: %s\n' "$arguments" >&2
    exit 2
fi
""",
        )
        process = subprocess.run(
            [str(aws_dir / "start-cpu.sh")],
            cwd=fixture,
            env={
                **os.environ,
                "AWS_CALL_LOG": str(call_log),
                "CPU_TEST_INSTANCE_TYPE": instance_type,
                "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            },
            text=True,
            capture_output=True,
            timeout=5,
            check=False,
        )
        calls = tuple(
            call_log.read_text(encoding="utf-8").splitlines()
            if call_log.is_file()
            else ()
        )
        return CpuStartResult(process=process, aws_calls=calls)


def run_forwarded_launcher(
    repository: Path,
    lab: str,
    *,
    lab3_probe_mode: str = "denied",
    lab3_report_check_status: int = 1,
) -> LauncherResult:
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
elif [[ "${LAB_UNDER_TEST:-}" == lab3 \
    && "${1:-} ${2:-} ${3:-}" == "unshare test -e" ]]; then
    case "${LAB3_REPORT_CHECK_STATUS:-1}" in
        0) printf 'report-present-check\\n' >>"${FAKE_STATE:?}/events.log" ;;
        1) printf 'report-absence-check\\n' >>"${FAKE_STATE:?}/events.log" ;;
        *) printf 'report-check-error\\n' >>"${FAKE_STATE:?}/events.log" ;;
    esac
    exit "${LAB3_REPORT_CHECK_STATUS:-1}"
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
if [[ "${1:-}" == logs && "${LAB_UNDER_TEST:-}" == lab3 ]]; then
    printf 'denial-evidence-check\\n' >>"${FAKE_STATE:?}/events.log"
    if [[ "${LAB3_PROBE_MODE:-denied}" == operational-error ]]; then
        printf 'sandbox log retrieval failed\\n' >&2
        exit 2
    fi
    printf 'NET:OPEN [MED] DENIED /usr/bin/curl(36) -> api.github.com:443\\n'
    exit 0
fi
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
            && "$*" == *"/usr/bin/curl"* ]]; then
            if [[ "$*" != *"--timeout 30"* || "$*" != *"--max-time 20"* ]]; then
                printf 'unbounded-network-probe\\n' >>"${FAKE_STATE:?}/events.log"
                exit 2
            fi
            if [[ "${LAB3_PROBE_MODE:-denied}" == operational-error ]]; then
                printf 'network-probe-error\\n' >>"${FAKE_STATE:?}/events.log"
                exit 2
            elif [[ ! -f "${FAKE_STATE:?}/allowed" ]]; then
                printf 'denied-network-probe\\n' >>"${FAKE_STATE:?}/events.log"
                exit 1
            fi
            printf 'network-probe-after-allow\\n' >>"${FAKE_STATE:?}/events.log"
            exit 0
        fi
        if [[ "${LAB_UNDER_TEST:-}" == lab3 \
            && "$*" == *"python3 -m openshell_lab.cli"* ]]; then
            if [[ ! -f "${FAKE_STATE:?}/allowed" ]]; then
                printf 'report-agent-before-allow\\n' >>"${FAKE_STATE:?}/events.log"
                exit 1
            fi
            printf 'report-agent\\n' >>"${FAKE_STATE:?}/events.log"
        fi
        exit 0
        ;;
    "policy get")
        printf '{}\\n'
        ;;
    "policy set")
        if [[ "${LAB_UNDER_TEST:-}" == lab3 ]]; then
            printf 'policy-set\\n' >>"${FAKE_STATE:?}/events.log"
        fi
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
            "LAB3_PROBE_MODE": lab3_probe_mode,
            "LAB3_REPORT_CHECK_STATUS": str(lab3_report_check_status),
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
        event_log = fake_state / "events.log"
        events = tuple(
            event_log.read_text(encoding="utf-8").splitlines()
            if event_log.is_file()
            else ()
        )
        return LauncherResult(
            completed=completed,
            returncode=process.returncode,
            stdout=stdout,
            stderr=stderr,
            create_log=create_log,
            events=events,
        )


def run_lab4_launcher(repository: Path) -> LauncherResult:
    """Run the real Lab 4 launcher against deterministic lifecycle fakes."""
    source = repository / "labs" / "lab4" / "run.sh"
    if not source.is_file():
        return LauncherResult(
            completed=False,
            returncode=None,
            stdout="",
            stderr="Lab 4 launcher is missing",
            create_log="",
            events=(),
        )

    with tempfile.TemporaryDirectory() as directory:
        fixture = Path(directory)
        run_path = fixture / "labs" / "lab4" / "run.sh"
        run_path.parent.mkdir(parents=True)
        shutil.copy2(source, run_path)
        (fixture / "policies").mkdir()
        (fixture / "policies" / "lab4-streamlit.yaml").write_text(
            "version: 1\nnetwork_policies: {}\n", encoding="utf-8"
        )
        (fixture / "state").mkdir()
        (fixture / "state" / "lab4-image.env").write_text(
            "IMAGE=localhost/openshell-lab-streamlit:abcdef1\n",
            encoding="utf-8",
        )

        fake_bin = fixture / "fake-bin"
        fake_bin.mkdir()
        fake_state = fixture / "fake-state"
        fake_state.mkdir()
        _write_executable(
            fake_bin / "podman",
            """#!/usr/bin/env bash
set -euo pipefail
exit 0
""",
        )
        _write_executable(
            fake_bin / "openshell",
            """#!/usr/bin/env bash
set -euo pipefail
case "${1:-} ${2:-}" in
    "sandbox list")
        exit 0
        ;;
    "sandbox delete")
        printf 'sandbox-delete\n' >>"${FAKE_STATE:?}/events.log"
        exit 0
        ;;
    "sandbox create")
        printf 'sandbox-create\n' >>"${FAKE_STATE:?}/events.log"
        printf 'sandbox-created\n' >&2
        exit 0
        ;;
    "sandbox exec")
        if [[ "$*" == *"nohup streamlit run app.py"* ]]; then
            printf 'streamlit-start\n' >>"${FAKE_STATE:?}/events.log"
        elif [[ "$*" == *"127.0.0.1:8501/_stcore/health"* ]]; then
            printf 'internal-health\n' >>"${FAKE_STATE:?}/events.log"
        else
            printf 'unexpected sandbox exec: %s\n' "$*" >&2
            exit 2
        fi
        exit 0
        ;;
    *)
        printf 'unexpected openshell invocation: %s\n' "$*" >&2
        exit 2
        ;;
esac
""",
        )
        _write_executable(
            fake_bin / "systemctl",
            """#!/usr/bin/env bash
set -euo pipefail
exit 0
""",
        )
        _write_executable(
            fake_bin / "systemd-run",
            """#!/usr/bin/env bash
set -euo pipefail
[[ "$*" == *"openshell forward service openshell-lab4"* ]]
[[ "$*" == *"--target-port 8501"* ]]
[[ "$*" == *"--local 127.0.0.1:18401"* ]]
printf 'forward-start\n' >>"${FAKE_STATE:?}/events.log"
""",
        )
        _write_executable(
            fake_bin / "curl",
            """#!/usr/bin/env bash
set -euo pipefail
[[ "$*" == *"127.0.0.1:18401/_stcore/health"* ]]
printf 'host-health\n' >>"${FAKE_STATE:?}/events.log"
""",
        )
        _write_executable(
            fake_bin / "sleep",
            """#!/usr/bin/env bash
exit 0
""",
        )

        try:
            process = subprocess.run(
                [str(run_path)],
                cwd=fixture,
                env={
                    **os.environ,
                    "FAKE_STATE": str(fake_state),
                    "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                },
                text=True,
                capture_output=True,
                timeout=2,
                check=False,
            )
        except subprocess.TimeoutExpired as error:
            return LauncherResult(
                completed=False,
                returncode=None,
                stdout=error.stdout or "",
                stderr=error.stderr or "Lab 4 launcher timed out",
                create_log="",
                events=(),
            )
        event_log = fake_state / "events.log"
        events = tuple(
            event_log.read_text(encoding="utf-8").splitlines()
            if event_log.is_file()
            else ()
        )
        create_log_path = fixture / "evidence" / "cpu" / "lab4" / "sandbox-create.log"
        return LauncherResult(
            completed=True,
            returncode=process.returncode,
            stdout=process.stdout,
            stderr=process.stderr,
            create_log=(
                create_log_path.read_text(encoding="utf-8")
                if create_log_path.is_file()
                else ""
            ),
            events=events,
        )


def run_lab4_verifier(
    repository: Path,
    *,
    filesystem_mode: str = "denied",
    namespace_mode: str = "denied",
    unit_bind: str = "127.0.0.1:18401",
    listener_bind: str = "127.0.0.1:18401",
) -> subprocess.CompletedProcess:
    """Run the real Lab 4 verifier against fault-injectable command fakes."""
    with tempfile.TemporaryDirectory() as directory:
        fixture = Path(directory)
        run_path = fixture / "labs" / "lab4" / "verify.sh"
        run_path.parent.mkdir(parents=True)
        shutil.copy2(repository / "labs" / "lab4" / "verify.sh", run_path)
        module_dir = fixture / "src" / "openshell_lab"
        module_dir.mkdir(parents=True)
        shutil.copy2(
            repository / "src" / "openshell_lab" / "lab4_policy.py",
            module_dir / "lab4_policy.py",
        )
        (module_dir / "__init__.py").write_text("", encoding="utf-8")
        (fixture / "state").mkdir()
        (fixture / "state" / "lab4-image.env").write_text(
            "IMAGE=localhost/openshell-lab-streamlit:abcdef1\n",
            encoding="utf-8",
        )

        fake_bin = fixture / "fake-bin"
        fake_bin.mkdir()
        _write_executable(
            fake_bin / "podman",
            """#!/usr/bin/env bash
set -euo pipefail
printf '1500:1500\n'
""",
        )
        _write_executable(
            fake_bin / "systemctl",
            """#!/usr/bin/env bash
set -euo pipefail
if [[ "$*" == *" is-active "* ]]; then
    exit 0
fi
if [[ "$*" == *" show "* ]]; then
    printf '{ path=/usr/local/bin/openshell ; argv[]=/usr/local/bin/openshell forward service openshell-lab4 --target-port 8501 --local %s ; }\n' "${UNIT_BIND:?}"
    exit 0
fi
exit 2
""",
        )
        _write_executable(
            fake_bin / "ss",
            """#!/usr/bin/env bash
set -euo pipefail
printf 'LISTEN 0 4096 %s 0.0.0.0:*\n' "${LISTENER_BIND:?}"
""",
        )
        _write_executable(
            fake_bin / "curl",
            """#!/usr/bin/env bash
set -euo pipefail
printf 'ok'
""",
        )
        _write_executable(
            fake_bin / "openshell",
            """#!/usr/bin/env bash
set -euo pipefail
case "${1:-} ${2:-}" in
    "policy get")
        printf '%s\n' '{"status":"effective","policy":{"filesystem_policy":{"include_workdir":false,"read_only":["/usr","/lib64","/etc","/proc","/dev/urandom","/opt/openshell-lab"],"read_write":["/tmp","/dev/null"]},"landlock":{"compatibility":"hard_requirement"},"process":{"run_as_user":"1500","run_as_group":"1500"}}}'
        ;;
    "sandbox exec")
        if [[ "$*" == *"probe.py"* ]]; then
            printf '%s\n' '{"status":"ok","response":"managed inference works"}'
        elif [[ "$*" == *"filesystem-write-denied"* ]]; then
            [[ "${FILESYSTEM_MODE:?}" == denied ]] || exit 2
            printf 'filesystem-write-denied\n'
        elif [[ "$*" == *"example.com"* ]]; then
            exit 1
        elif [[ "$*" == *"/proc/self/status"* ]]; then
            printf 'Uid:\t1500\t1500\t1500\t1500\nGid:\t1500\t1500\t1500\t1500\nCapBnd:\t0000000000000000\nNoNewPrivs:\t1\n'
        elif [[ "$*" == *"/usr/bin/test -x /usr/bin/unshare"* ]]; then
            exit 0
        elif [[ "$*" == *"namespace-denied"* ]]; then
            [[ "${NAMESPACE_MODE:?}" == denied ]] || exit 2
            printf 'namespace-denied\n'
        elif [[ "$*" == *"OPENAI_API_KEY"* ]]; then
            exit 0
        else
            printf 'unexpected sandbox exec: %s\n' "$*" >&2
            exit 2
        fi
        ;;
    *)
        if [[ "${1:-}" == logs ]]; then
            printf 'NET:OPEN [MED] DENIED /usr/bin/python3.12(154) -> example.com:443\n'
        else
            printf 'unexpected openshell invocation: %s\n' "$*" >&2
            exit 2
        fi
        ;;
esac
""",
        )
        _write_executable(fake_bin / "sleep", "#!/usr/bin/env bash\nexit 0\n")

        return subprocess.run(
            [str(run_path)],
            cwd=fixture,
            env={
                **os.environ,
                "FILESYSTEM_MODE": filesystem_mode,
                "NAMESPACE_MODE": namespace_mode,
                "UNIT_BIND": unit_bind,
                "LISTENER_BIND": listener_bind,
                "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            },
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
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
            "lab4": ("build", "run", "verify"),
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


def generated_runner_default_lab(installer: Path) -> str:
    """Run the installer with active vLLM and return the generated default."""
    with tempfile.TemporaryDirectory() as directory:
        home = Path(directory) / "home"
        lab_root = home / "git" / "openshell-lab" / "labs"
        for lab in ("lab1", "lab2", "lab3", "lab4", "lab5"):
            runner = lab_root / lab / "run.sh"
            runner.parent.mkdir(parents=True)
            _write_executable(
                runner,
                "#!/usr/bin/env bash\n"
                f"printf '{lab}\\n' >\"${{RUNNER_EVENT:?}}\"\n",
            )

        fake_bin = Path(directory) / "fake-bin"
        fake_bin.mkdir()
        _write_executable(
            fake_bin / "systemctl",
            "#!/usr/bin/env bash\n"
            '[[ "$*" == "--user is-active --quiet vllm.service" ]]\n',
        )
        event_log = Path(directory) / "runner-event.log"
        subprocess.run(
            [str(installer)],
            env={
                **os.environ,
                "HOME": str(home),
                "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            },
            text=True,
            capture_output=True,
            check=True,
        )
        runner = (home / "run-openshell-agent.sh").read_text(encoding="utf-8")
        if not runner:
            raise AssertionError("installer generated an empty runner")
        subprocess.run(
            [str(home / "run-openshell-agent.sh")],
            env={
                **os.environ,
                "HOME": str(home),
                "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
                "RUNNER_EVENT": str(event_log),
            },
            text=True,
            capture_output=True,
            check=True,
        )
        return event_log.read_text(encoding="utf-8").strip()


def run_evidence_collector(
    repository: Path,
    collector: str,
    members: list[tuple[str, str, str]],
    *,
    existing_files: dict[str, str] | None = None,
    lock_held: bool = False,
    remote_directory_missing: bool = False,
) -> EvidenceCollectorResult:
    """Run a production evidence collector against deterministic SSH fixtures."""
    if collector not in EVIDENCE_FILENAMES:
        raise AssertionError(f"unsupported evidence collector: {collector}")

    script_name = (
        "collect-evidence.sh" if collector == "CPU" else "collect-gpu-evidence.sh"
    )
    library_name = "lib.sh" if collector == "CPU" else "gpu-lib.sh"
    destination_parts = ("cpu", "lab4") if collector == "CPU" else ("gpu",)
    existing_files = existing_files or {"stale.txt": "prior evidence\n"}

    with tempfile.TemporaryDirectory() as directory:
        fixture = Path(directory)
        fixture_repository = fixture / "repository"
        scripts_dir = fixture_repository / "scripts"
        aws_dir = fixture_repository / "infra" / "aws"
        state_dir = fixture_repository / "state"
        evidence_root = fixture_repository / "evidence"
        destination = evidence_root.joinpath(*destination_parts)
        scripts_dir.mkdir(parents=True)
        aws_dir.mkdir(parents=True)
        state_dir.mkdir()
        destination.mkdir(parents=True)

        shutil.copy2(repository / "scripts" / script_name, scripts_dir / script_name)
        pattern_source = repository / "scripts" / "credential-patterns.sh"
        if pattern_source.is_file():
            shutil.copy2(pattern_source, scripts_dir / pattern_source.name)
        shutil.copy2(repository / "infra" / "aws" / library_name, aws_dir)

        if collector == "CPU":
            (state_dir / "cpu-connection.env").write_text(
                "AWS_REGION=us-east-1\n"
                "INSTANCE_ID=i-0123456789abcdef0\n"
                "PUBLIC_IP=192.0.2.10\n"
                "PRIVATE_IP=10.0.0.10\n"
                "SUBNET_ID=subnet-0123456789abcdef0\n"
                "SECURITY_GROUP_ID=sg-0123456789abcdef0\n"
                "SSH_USER=ec2-user\n"
                "SSH_KEY_PATH=/fixture/id_rsa\n",
                encoding="utf-8",
            )
            (state_dir / "known_hosts").write_text(
                "fixture host key\n", encoding="utf-8"
            )
        else:
            (state_dir / "gpu-connection.env").write_text(
                "PUBLIC_IP=192.0.2.10\n"
                "SSH_USER=ec2-user\n"
                "SSH_KEY_PATH=/fixture/id_rsa\n",
                encoding="utf-8",
            )
            (state_dir / "gpu-known_hosts").write_text(
                "fixture host key\n", encoding="utf-8"
            )

        for name, content in existing_files.items():
            path = destination / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        if lock_held:
            lock_name = ".cpu-collect.lock" if collector == "CPU" else ".gpu-collect.lock"
            (evidence_root / lock_name).mkdir()

        archive = fixture / "evidence.tar"
        with tarfile.open(archive, "w") as output:
            for name, content, kind in members:
                info = tarfile.TarInfo(name)
                info.mode = 0o600
                if kind == "file":
                    payload = content.encode("utf-8")
                    info.size = len(payload)
                    output.addfile(info, io.BytesIO(payload))
                elif kind == "symlink":
                    info.type = tarfile.SYMTYPE
                    info.linkname = content
                    output.addfile(info)
                elif kind == "fifo":
                    info.type = tarfile.FIFOTYPE
                    output.addfile(info)
                elif kind == "directory":
                    info.type = tarfile.DIRTYPE
                    info.mode = 0o755
                    output.addfile(info)
                else:
                    raise AssertionError(f"unsupported member type: {kind}")

        lab3_archive = fixture / "lab3.tar"
        with tarfile.open(lab3_archive, "w") as output:
            payload = b"lab3 evidence\n"
            info = tarfile.TarInfo("lab3/policy.json")
            info.mode = 0o600
            info.size = len(payload)
            output.addfile(info, io.BytesIO(payload))

        remote_home = fixture / "remote-home"
        remote_home.mkdir()
        if remote_directory_missing:
            decoy_parts = (
                ("evidence", "cpu", "lab4")
                if collector == "CPU"
                else ("evidence", "gpu")
            )
            decoy = remote_home.joinpath(*decoy_parts)
            decoy.mkdir(parents=True)
            for name in EVIDENCE_FILENAMES[collector]:
                (decoy / name).write_text("decoy evidence\n", encoding="utf-8")

        fake_bin = fixture / "fake-bin"
        fake_bin.mkdir()
        ssh_log = fixture / "ssh-commands.log"
        _write_executable(
            fake_bin / "ssh",
            """#!/usr/bin/env bash
set -euo pipefail
command=${!#}
printf '%s\n' "$command" >>"${SSH_COMMAND_LOG:?}"
if [[ "$command" == *"tar "* && "$command" == *"lab3"* ]]; then
    cat -- "${FAKE_LAB3_ARCHIVE:?}"
elif [[ "$command" == *"tar "* ]]; then
    if [[ "${REMOTE_DIRECTORY_MISSING:-false}" == true ]]; then
        (
            cd -- "${FAKE_REMOTE_HOME:?}"
            HOME=${FAKE_REMOTE_HOME:?} /bin/bash -c "$command"
        )
    else
        cat -- "${FAKE_EVIDENCE_ARCHIVE:?}"
    fi
else
    printf 'fixture remote output\n'
fi
""",
        )
        _write_executable(
            fake_bin / "curl",
            """#!/usr/bin/env bash
set -euo pipefail
printf '# fixture report\n'
""",
        )

        process = subprocess.run(
            ["bash", str(scripts_dir / script_name)],
            cwd=fixture_repository,
            env={
                **os.environ,
                "FAKE_EVIDENCE_ARCHIVE": str(archive),
                "FAKE_LAB3_ARCHIVE": str(lab3_archive),
                "FAKE_REMOTE_HOME": str(remote_home),
                "REMOTE_DIRECTORY_MISSING": (
                    "true" if remote_directory_missing else "false"
                ),
                "SSH_COMMAND_LOG": str(ssh_log),
                "PATH": f"{fake_bin}{os.pathsep}{os.environ['PATH']}",
            },
            text=True,
            capture_output=True,
            timeout=15,
            check=False,
        )
        collected = {
            path.relative_to(destination).as_posix(): path.read_text(
                encoding="utf-8"
            )
            for path in destination.rglob("*")
            if path.is_file()
        }
        ssh_commands = tuple(
            ssh_log.read_text(encoding="utf-8").splitlines()
            if ssh_log.is_file()
            else ()
        )
        return EvidenceCollectorResult(
            process=process,
            collected=collected,
            ssh_commands=ssh_commands,
        )


def restricted_search_path(search_tool: str = "grep") -> str:
    directory = Path(tempfile.mkdtemp())
    if search_tool not in {"grep", "rg"}:
        raise AssertionError(f"unsupported search tool: {search_tool}")
    for command in ("bash", "git", search_tool, "dirname", "mktemp", "rm"):
        resolved = shutil.which(command)
        if resolved is None:
            raise AssertionError(f"required test command not found: {command}")
        (directory / command).symlink_to(resolved)
    return str(directory)


def run_aws_secret_scan_matrix(scanner: Path) -> tuple[SecretScanCaseResult, ...]:
    """Exercise both scanner implementations against synthetic AWS forms."""
    credential_cases = (
        ("temporary access identifier", "AS" + "IA" + "T" * 16),
        (
            "labeled secret access key",
            ("AWS_" + "SECRET_ACCESS_KEY") + "=" + "synthetic-" + "S" * 32,
        ),
        (
            "labeled session token",
            ("AWS_" + "SESSION_TOKEN") + ": " + "synthetic-" + "T" * 64,
        ),
    )
    results = []
    for search_tool in ("rg", "grep"):
        search_path = restricted_search_path(search_tool)
        try:
            for credential_form, content in credential_cases:
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    subprocess.run(["git", "init", "-q", str(root)], check=True)
                    (root / "unsafe.txt").write_text(content + "\n", encoding="utf-8")
                    process = subprocess.run(
                        [str(scanner), str(root)],
                        text=True,
                        capture_output=True,
                        check=False,
                        env={
                            **os.environ,
                            "LC_ALL": "C",
                            "PATH": search_path,
                        },
                    )
                    value = content.split("=", 1)[-1].split(": ", 1)[-1]
                    results.append(
                        SecretScanCaseResult(
                            search_tool=search_tool,
                            credential_form=credential_form,
                            value=value,
                            process=process,
                        )
                    )
        finally:
            shutil.rmtree(search_path)
    return tuple(results)


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
