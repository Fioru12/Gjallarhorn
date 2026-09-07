import pytest
from unittest.mock import patch, MagicMock
from core.channels.siem_syslog import SiemSyslogChannel

def test_siem_cef_formatting():
    channel = SiemSyslogChannel(host="127.0.0.1", port=514, format_type="cef")
    assert channel.is_configured() is True
    cef = channel.format_cef("SSH Brute-Force", "IP 1.2.3.4 blocked", "high")
    assert "CEF:0|Asgard|Gjallarhorn|1.0.0|SECURITY_ALERT|SSH Brute-Force|8|" in cef
    assert "msg=IP 1.2.3.4 blocked" in cef

def test_siem_syslog_formatting():
    channel = SiemSyslogChannel(host="127.0.0.1", port=514, format_type="syslog")
    syslog_msg = channel.format_syslog_rfc5424("SSH Brute-Force", "IP 1.2.3.4 blocked", "critical")
    assert "<14>1" in syslog_msg
    assert "[CRITICAL] SSH Brute-Force: IP 1.2.3.4 blocked" in syslog_msg

@patch("socket.socket")
def test_siem_send_udp(mock_socket_cls):
    mock_sock = MagicMock()
    mock_socket_cls.return_value = mock_sock

    channel = SiemSyslogChannel(host="10.0.0.10", port=514)
    success = channel.send("Alert", "Test msg", "medium")
    assert success is True
    mock_sock.sendto.assert_called_once()
