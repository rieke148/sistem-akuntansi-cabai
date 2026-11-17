"""Pengujian pembersihan state saat sesi pengguna berakhir."""

from types import SimpleNamespace

from services import permission_service


def test_hapus_session_login_membersihkan_seluruh_state(monkeypatch):
    """Data sementara aplikasi tidak boleh terbawa ke pengguna berikutnya."""
    session_state = {
        "auth_user_id": 7,
        "auth_session_version": 2,
        "kelompok_transaksi": "Penjualan",
        "pratinjau_baris": [{"account_id": 1, "debit": 1000, "kredit": 0}],
        "konfirmasi_reset": True,
    }
    streamlit_stub = SimpleNamespace(session_state=session_state)
    monkeypatch.setattr(permission_service, "st", streamlit_stub)

    permission_service.hapus_session_login()

    assert session_state == {}
