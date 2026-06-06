from scripts.maintenance.export_web_application import ROOT, should_copy


def test_export_includes_maintenance_scripts():
    assert should_copy(ROOT / 'scripts' / 'maintenance' / 'backup_database.py')
    assert should_copy(ROOT / 'scripts' / 'maintenance' / 'check_deploy_safety.py')


def test_export_excludes_local_uploader_scripts():
    assert not should_copy(ROOT / 'scripts' / 'local' / 'upload_live_comps.py')
    assert not should_copy(ROOT / 'scripts' / 'local' / 'refresh_live_comps.py')


def test_export_includes_refactored_server_modules():
    assert should_copy(ROOT / 'app_pages.py')
    assert should_copy(ROOT / 'admin_audit_service.py')
    assert should_copy(ROOT / 'admin_dashboard_service.py')
    assert should_copy(ROOT / 'admin_live_comp_service.py')
    assert should_copy(ROOT / 'admin_lineup_service.py')
    assert should_copy(ROOT / 'admin_pagination.py')
    assert should_copy(ROOT / 'admin_report_service.py')
    assert should_copy(ROOT / 'admin_user_service.py')
    assert should_copy(ROOT / 'live_comps_helpers.py')
    assert should_copy(ROOT / 'lineups_query.py')
    assert should_copy(ROOT / 'lineups_serialization.py')
    assert should_copy(ROOT / 'lineups_utils.py')
    assert should_copy(ROOT / 'db_migrations.py')
    assert should_copy(ROOT / 'db_schema.py')
    assert should_copy(ROOT / 'lineup_account_service.py')
    assert should_copy(ROOT / 'lineup_bridge_service.py')
    assert should_copy(ROOT / 'lineup_interaction_service.py')
    assert should_copy(ROOT / 'lineup_read_service.py')
    assert should_copy(ROOT / 'lineup_write_service.py')
    assert should_copy(ROOT / 'route_response.py')
