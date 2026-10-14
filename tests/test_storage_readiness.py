from app.db import db


def test_readiness_detects_database_failure(client, monkeypatch):
    result = client.get('/api/system/status')
    assert result.status_code == 200
    assert result.json()['database']['datasets']['enterprises'] == 0
    def fail(*args, **kwargs): raise RuntimeError('do-not-leak-secret')
    monkeypatch.setattr(db, 'query', fail)
    response = client.get('/api/health')
    assert response.status_code == 503
    assert response.json()['database']['ready'] is False
    assert 'do-not-leak-secret' not in response.text


def test_pie_keeps_all_accidents_in_denominator():
    from app.report_charts import specifications
    stats = {'distributions': {'type': [{'name': str(i), 'value': i+1} for i in range(15)]}, 'network': {'nodes': [], 'links': []}, 'monthly': {}}
    data = specifications(stats, None)[4]['option']['series'][0]['data']
    assert sum(x['value'] for x in data) == 120
    assert len(data) == 12
