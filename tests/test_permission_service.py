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



def test_session_kedaluwarsa_mencatat_logout_dan_membersihkan_state(monkeypatch):
    """Session idle lebih dari batas waktu langsung ditutup."""
    session_state = {
        "auth_user_id": 7,
        "auth_session_version": 2,
        "auth_last_activity": 100.0,
        "form_sementara": "data",
    }
    streamlit_stub = SimpleNamespace(session_state=session_state)
    monkeypatch.setattr(permission_service, "st", streamlit_stub)
    monkeypatch.setattr(permission_service.time, "time", lambda: 200.0)
    monkeypatch.setattr(permission_service, "SESSION_IDLE_SECONDS", 60)
    logout_ids = []
    monkeypatch.setattr(
        permission_service.auth_service, "catat_logout",
        lambda user_id: logout_ids.append(user_id),
    )

    assert permission_service.pengguna_aktif() is None
    assert logout_ids == [7]
    assert session_state == {}


def test_session_tanpa_waktu_aktivitas_ditolak(monkeypatch):
    """Session state yang tidak lengkap tidak boleh melewati pemeriksaan."""
    session_state = {"auth_user_id": 7, "auth_session_version": 2}
    monkeypatch.setattr(
        permission_service, "st",
        SimpleNamespace(session_state=session_state),
    )

    assert permission_service.pengguna_aktif() is None
    assert session_state == {}


def test_perubahan_session_version_membatalkan_session(monkeypatch):
    """Versi sesi yang tidak sama dengan database memaksa login ulang."""
    session_state = {
        "auth_user_id": 7,
        "auth_session_version": 1,
        "auth_last_activity": 100.0,
    }
    monkeypatch.setattr(
        permission_service, "st",
        SimpleNamespace(session_state=session_state),
    )
    monkeypatch.setattr(permission_service.time, "time", lambda: 110.0)
    monkeypatch.setattr(
        permission_service.auth_service, "ambil_pengguna",
        lambda user_id: {"id": 7, "session_version": 2, "role_id": 1, "role_code": "accountant"},
    )

    assert permission_service.pengguna_aktif() is None
    assert session_state == {}


def test_akun_nonaktif_membatalkan_session(monkeypatch):
    """Akun yang dinonaktifkan saat login tidak boleh tetap memakai sesi lama."""
    session_state = {
        "auth_user_id": 7,
        "auth_session_version": 1,
        "auth_last_activity": 100.0,
    }
    monkeypatch.setattr(
        permission_service, "st",
        SimpleNamespace(session_state=session_state),
    )
    monkeypatch.setattr(permission_service.time, "time", lambda: 110.0)
    monkeypatch.setattr(
        permission_service.auth_service, "ambil_pengguna",
        lambda user_id: None,
    )

    assert permission_service.pengguna_aktif() is None
    assert session_state == {}


def test_logout_tetap_membersihkan_session_jika_audit_gagal(monkeypatch):
    """Kegagalan database audit tidak boleh membatalkan logout pengguna."""
    session_state = {"auth_user_id": 7, "form_rahasia": "sementara"}
    monkeypatch.setattr(
        permission_service, "st",
        SimpleNamespace(session_state=session_state),
    )

    def audit_gagal(user_id):
        raise RuntimeError("database audit tidak tersedia")

    monkeypatch.setattr(
        permission_service.auth_service, "catat_logout", audit_gagal
    )

    assert permission_service.keluar_pengguna(7) is False
    assert session_state == {}
