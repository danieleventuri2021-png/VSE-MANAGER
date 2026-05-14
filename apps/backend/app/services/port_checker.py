import socket
import subprocess
from dataclasses import asdict, dataclass


@dataclass
class PortStatus:
    port: int
    free: bool
    pid: int | None = None
    process_name: str | None = None


def check_port(port: int, host: str = "127.0.0.1") -> PortStatus:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.4)
        occupied = sock.connect_ex((host, port)) == 0
    status = PortStatus(port=port, free=not occupied)
    if occupied:
        pid, name = _windows_process_for_port(port)
        status.pid = pid
        status.process_name = name
    return status


def check_ports(backend_port: int = 8000, frontend_port: int = 5173) -> dict:
    return {
        "backend": asdict(check_port(backend_port)),
        "frontend": asdict(check_port(frontend_port)),
    }


def _windows_process_for_port(port: int) -> tuple[int | None, str | None]:
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
