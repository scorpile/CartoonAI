"""Startup must tolerate occupied/reserved ports and open the actual address."""
import errno
import socket
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from celstudio import server


def test_occupied_port_uses_free_loopback_port():
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1',0))
        occupied.listen()
        port=occupied.getsockname()[1]
        app=server.create_server(None,port)
        try:
            assert app.server_address[0]=='127.0.0.1'
            assert app.server_address[1]!=port
        finally:
            app.server_close()


def test_windows_reserved_port_falls_back(monkeypatch):
    denied=OSError('Windows reserved port')
    denied.winerror=10013
    app=SimpleNamespace(server_address=('127.0.0.1',49152))
    factory=Mock(side_effect=[denied,app])
    monkeypatch.setattr(server,'ThreadingHTTPServer',factory)
    assert server.create_server(None,8768) is app
    assert [call.args[0] for call in factory.call_args_list]==[
        ('127.0.0.1',8768),('127.0.0.1',0)]


@pytest.mark.parametrize('port,error',[
    (8768,OSError(errno.ENOBUFS,'No buffer space')),
    (0,OSError(errno.EACCES,'No available port')),
])
def test_unrelated_or_ephemeral_bind_error_is_preserved(monkeypatch,port,error):
    factory=Mock(side_effect=error)
    monkeypatch.setattr(server,'ThreadingHTTPServer',factory)
    with pytest.raises(OSError) as raised:
        server.create_server(None,port)
    assert raised.value is error
    assert factory.call_count==1


def test_browser_and_console_use_actual_port(monkeypatch,capsys,tmp_path):
    app=Mock(server_address=('127.0.0.1',49152))
    app.serve_forever.side_effect=KeyboardInterrupt
    monkeypatch.setattr(server,'Studio',lambda _:SimpleNamespace(jobs={},workers={}))
    monkeypatch.setattr(server,'create_server',lambda *_:app)
    browser=Mock()
    monkeypatch.setattr(server.webbrowser,'open',browser)
    server.serve(tmp_path,8768,True)
    browser.assert_called_once_with('http://127.0.0.1:49152')
    assert 'http://127.0.0.1:49152' in capsys.readouterr().out
    app.server_close.assert_called_once()
