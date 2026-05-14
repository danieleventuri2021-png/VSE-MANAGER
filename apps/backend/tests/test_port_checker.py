import socket

from app.services.port_checker import check_port


def test_check_port_detects_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    status = check_port(port)
    assert status.free is True
