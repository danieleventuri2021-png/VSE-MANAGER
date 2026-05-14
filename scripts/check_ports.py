import argparse
import socket
import subprocess
import sys


def port_status(port: int, host: str = "127.0.0.1") -> dict:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        occupied = sock.connect_ex((host, port)) == 0
    status = {"port": port, "free": not occupied, "pid": None, "process_name": None}
    if occupied:
        status["pid"], status["process_name"] = process_for_port(port)
    return status


def process_for_port(port: int) -> tuple[int | None, str | None]:
    try:
        output = subprocess.check_output(["netstat", "-ano", "-p", "TCP"], text=True, stderr=subprocess.DEVNULL)
        pid = None
        for line in output.splitlines():
            if f":{port} " in line and "LISTENING" in line:
                pid = int(line.rsplit(maxsplit=1)[-1])
                break
        if not pid:
            return None, None
        tasklist = subprocess.check_output(["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"], text=True, stderr=subprocess.DEVNULL)
        name = tasklist.split(",", 1)[0].strip('" \r\n') if tasklist.strip() else None
        return pid, name
    except Exception:
        return None, None


def main() -> int:
    parser = argparse.ArgumentParser(description="Controlla le porte di gestione-vse.")
    parser.add_argument("--backend-port", type=int, default=8000)
    parser.add_argument("--frontend-port", type=int, default=5173)
    parser.add_argument("--only", choices=["backend", "frontend", "both"], default="both")
    args = parser.parse_args()
    statuses = {}
    if args.only in {"backend", "both"}:
        statuses["Backend"] = port_status(args.backend_port)
    if args.only in {"frontend", "both"}:
        statuses["Frontend"] = port_status(args.frontend_port)
    ok = True
    for label, status in statuses.items():
        if status["free"]:
            print(f"{label}: porta {status['port']} libera")
        else:
            ok = False
            details = f"PID {status['pid']}" if status["pid"] else "PID non rilevato"
            if status["process_name"]:
                details += f", processo {status['process_name']}"
            print(f"{label}: porta {status['port']} occupata ({details})")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
