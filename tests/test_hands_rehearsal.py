"""Driver authorization and cleanup with command fakes; never starts the demo."""
import pytest
from scripts import hands_rehearsal as driver


def test_live_driver_requires_explicit_switch_before_any_command(monkeypatch):
    monkeypatch.setattr(driver,'command',lambda *a,**k:pytest.fail('must not run'))
    with pytest.raises(SystemExit):
        driver.main(['payment-failure','--report-id','new','--operator','Tester'])


def test_existing_bundle_refused_before_any_command(tmp_path,monkeypatch):
    monkeypatch.setattr(driver,'ROOT',tmp_path)
    (tmp_path/'reports/existing').mkdir(parents=True)
    monkeypatch.setattr(driver,'command',lambda *a,**k:pytest.fail('must not run'))
    with pytest.raises(SystemExit):
        driver.main(['payment-failure','--live','--report-id','existing','--operator','Tester'])


def test_live_driver_never_allows_test_environment(tmp_path,monkeypatch):
    monkeypatch.setattr(driver,'ROOT',tmp_path)
    monkeypatch.setenv('INCIDENT_ZERO_TEST','1')
    monkeypatch.setattr(driver,'command',lambda *a,**k:pytest.fail('must not run'))
    with pytest.raises(SystemExit):
        driver.main(['payment-failure','--live','--report-id','new','--operator','Tester'])


def test_driver_resets_after_diagnosis_failure(tmp_path,monkeypatch):
    monkeypatch.setattr(driver,'ROOT',tmp_path)
    monkeypatch.delenv('INCIDENT_ZERO_TEST',raising=False)
    calls=[]
    def command(args,**kwargs):
        calls.append(args)
        if args[0]=='agent.run':
            raise RuntimeError('model unavailable')
        return {}
    monkeypatch.setattr(driver,'command',command)
    monkeypatch.setattr(driver,'require_clean',lambda *a:None)
    monkeypatch.setattr(driver,'check_demo_unchanged',lambda:None)
    monkeypatch.setattr(driver.Detector,'prime_baseline',lambda *a,**k:None)
    monkeypatch.setattr(driver.Detector,'poll',lambda *a,**k:None)
    monkeypatch.setattr(driver,'wait_for_alert',lambda *a,**k:{'signal':'error_rate'})
    monkeypatch.setattr(driver,'write_alert',lambda a,d:d/'alert.json')
    assert driver.main(['payment-failure','--live','--report-id','new','--operator','Tester'])==1
    assert [c[:2] for c in calls].count(['faultctl','reset'])==2
    assert calls[-1][:2]==['faultctl','reset']
