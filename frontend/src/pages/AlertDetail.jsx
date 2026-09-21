import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Bell, Check, Eye, RefreshCw } from 'lucide-react';
import ContributingFactors from '../components/ContributingFactors';
import { getAlerts, getAlert, acknowledgeAlert, getContributingFactors } from '../services/api';

export default function AlertsPage({ wsProgress }) {
  const [searchParams] = useSearchParams();
  const [alerts, setAlerts] = useState([]);
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [factors, setFactors] = useState([]);
  const [filter, setFilter] = useState('all');
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  // Track the last pipeline completion stage we already reacted to
  const lastProgressStageRef = useRef(null);

  useEffect(() => {
    loadAlerts();
  }, [filter]);

  useEffect(() => {
    const alertId = searchParams.get('id');
    if (alertId) {
      loadAlertDetail(parseInt(alertId));
    }
  }, [searchParams]);

  /**
   * When the WebSocket pipeline broadcasts a "complete" progress event,
   * automatically refresh the alert list so newly generated alerts appear
   * without the user needing to manually reload.
   */
  useEffect(() => {
    if (!wsProgress) return;
    if (wsProgress.stage === 'complete' && wsProgress.stage !== lastProgressStageRef.current) {
      lastProgressStageRef.current = wsProgress.stage;
      // Small delay to allow the backend to finish writing the last alert to DB
      const timer = setTimeout(() => {
        loadAlerts();
        lastProgressStageRef.current = null; // Reset so next run also triggers
      }, 800);
      return () => clearTimeout(timer);
    }
  }, [wsProgress]);

  const loadAlerts = async () => {
    setError(null);
    try {
      const params = {};
      if (filter !== 'all') params.severity = filter.toUpperCase();
      const res = await getAlerts(params);
      setAlerts(Array.isArray(res.data) ? res.data : []);
    } catch (e) {
      console.error('Failed to load alerts:', e);
      const msg = e?.response?.data?.detail || e?.message || 'Unknown error';
      setError(`Failed to load alerts: ${msg}`);
      setAlerts([]);
    }
    setLoading(false);
    setRefreshing(false);
  };

  const handleRefresh = () => {
    setRefreshing(true);
    loadAlerts();
  };

  const loadAlertDetail = async (alertId) => {
    try {
      const [alertRes, factorsRes] = await Promise.all([
        getAlert(alertId),
        getContributingFactors(alertId).catch(() => ({ data: [] })),
      ]);
      setSelectedAlert(alertRes.data);
      setFactors(factorsRes.data);
    } catch (e) {
      console.error('Failed to load alert detail:', e);
    }
  };

  const handleAcknowledge = async (alertId) => {
    try {
      await acknowledgeAlert(alertId);
      loadAlerts();
      if (selectedAlert?.id === alertId) {
        loadAlertDetail(alertId);
      }
    } catch (e) {
      console.error('Failed to acknowledge alert:', e);
    }
  };

  const filters = ['all', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'];

  return (
    <div className="animate-in">
      <div className="page-header">
        <div>
          <h1>Alert Management</h1>
          <p>Review, investigate, and acknowledge security alerts</p>
        </div>
        {!selectedAlert && (
          <button
            className="btn btn-secondary btn-sm"
            onClick={handleRefresh}
            disabled={refreshing}
            style={{ display: 'flex', alignItems: 'center', gap: 6 }}
            title="Refresh alerts from backend"
          >
            <RefreshCw size={14} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
            {refreshing ? 'Refreshing...' : 'Refresh'}
          </button>
        )}
      </div>

      {/* Detail View */}
      {selectedAlert && (
        <div className="card" style={{ marginBottom: '24px' }}>
          <div className="card-header">
            <span className="card-title">
              Alert #{selectedAlert.id} Detail
            </span>
            <button
              className="btn btn-secondary btn-sm"
              onClick={() => { setSelectedAlert(null); setFactors([]); }}
            >
              ← Back to List
            </button>
          </div>

          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px', marginBottom: '24px' }}>
            <div>
              <h3 style={{ fontSize: '18px', marginBottom: '8px' }}>{selectedAlert.title}</h3>
              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap', marginBottom: '16px' }}>
                <span className={`severity-badge ${selectedAlert.severity?.toLowerCase()}`}>
                  <span className="severity-dot" /> {selectedAlert.severity}
                </span>
                <span style={{
                  padding: '3px 10px',
                  borderRadius: '9999px',
                  background: 'var(--bg-surface)',
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-secondary)',
                }}>
                  Score: {selectedAlert.threat_score?.toFixed(1)}
                </span>
                <span style={{
                  padding: '3px 10px',
                  borderRadius: '9999px',
                  background: 'var(--bg-surface)',
                  fontSize: '11px',
                  fontFamily: 'var(--font-mono)',
                  color: 'var(--text-secondary)',
                }}>
                  {selectedAlert.confidence != null
                    ? `${(selectedAlert.confidence * 100).toFixed(0)}% confidence`
                    : 'N/A'}
                </span>
              </div>
              <div style={{
                padding: '16px',
                background: 'var(--bg-card)',
                borderRadius: '10px',
                fontSize: '13px',
                color: 'var(--text-secondary)',
                lineHeight: 1.7,
                whiteSpace: 'pre-wrap',
                maxHeight: '400px',
                overflow: 'auto',
              }}>
                {selectedAlert.description || 'No explanation available'}
              </div>
            </div>
            <div>
              <table className="data-table">
                <tbody>
                  <tr><td>Category</td><td>{selectedAlert.threat_category}</td></tr>
                  <tr><td>Status</td><td style={{ textTransform: 'uppercase' }}>{selectedAlert.status}</td></tr>
                  <tr><td>Session</td><td>#{selectedAlert.session_id}</td></tr>
                  <tr><td>Created</td><td>{new Date(selectedAlert.created_at).toLocaleString()}</td></tr>
                  {selectedAlert.acknowledged_by && (
                    <>
                      <tr><td>Acknowledged By</td><td>{selectedAlert.acknowledged_by}</td></tr>
                      <tr><td>Acknowledged At</td><td>{new Date(selectedAlert.acknowledged_at).toLocaleString()}</td></tr>
                    </>
                  )}
                </tbody>
              </table>

              {selectedAlert.status === 'new' && (
                <button
                  className="btn btn-primary btn-sm"
                  style={{ marginTop: '16px' }}
                  onClick={() => handleAcknowledge(selectedAlert.id)}
                >
                  <Check size={14} /> Acknowledge Alert
                </button>
              )}
            </div>
          </div>

          <ContributingFactors factors={factors} />
        </div>
      )}

      {/* Filter Bar */}
      {!selectedAlert && (
        <>
          <div style={{ display: 'flex', gap: '8px', marginBottom: '16px', flexWrap: 'wrap' }}>
            {filters.map((f) => (
              <button
                key={f}
                className={`btn btn-sm ${filter === f ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setFilter(f)}
              >
                {f === 'all' ? 'All' : f}
              </button>
            ))}
          </div>

          {/* Alert List */}
          {loading ? (
            <div className="card">
              <div className="empty-state">
                <div style={{ color: 'var(--accent-cyan)', fontSize: '13px' }}>Loading alerts...</div>
              </div>
            </div>
          ) : error ? (
            <div className="card">
              <div className="empty-state">
                <Bell size={48} style={{ color: 'var(--severity-critical)' }} />
                <h3 style={{ color: 'var(--severity-critical)' }}>Failed to Load Alerts</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>{error}</p>
                <button className="btn btn-primary btn-sm" onClick={handleRefresh} style={{ marginTop: '12px' }}>
                  Retry
                </button>
              </div>
            </div>
          ) : alerts.length === 0 ? (
            <div className="card">
              <div className="empty-state">
                <Bell size={48} />
                <h3>No Alerts</h3>
                <p>No alerts match the current filter. Run a simulation to generate some.</p>
              </div>
            </div>
          ) : (
            <div className="card" style={{ overflow: 'auto' }}>
              <table className="data-table">
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Title</th>
                    <th>Severity</th>
                    <th>Score</th>
                    <th>Category</th>
                    <th>Status</th>
                    <th>Time</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {alerts.map((alert) => (
                    <tr key={alert.id}>
                      <td style={{ color: 'var(--text-primary)' }}>#{alert.id}</td>
                      <td style={{ color: 'var(--text-primary)', maxWidth: '250px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                        {alert.title}
                      </td>
                      <td>
                        <span className={`severity-badge ${alert.severity?.toLowerCase()}`}>
                          <span className="severity-dot" /> {alert.severity}
                        </span>
                      </td>
                      <td style={{ fontWeight: 700 }}>{alert.threat_score?.toFixed(1)}</td>
                      <td style={{ fontSize: '11px' }}>{alert.threat_category || '—'}</td>
                      <td style={{ textTransform: 'uppercase', fontSize: '11px' }}>{alert.status}</td>
                      <td>{new Date(alert.created_at).toLocaleTimeString()}</td>
                      <td>
                        <div style={{ display: 'flex', gap: '4px' }}>
                          <button
                            className="btn btn-secondary btn-sm btn-icon"
                            onClick={() => loadAlertDetail(alert.id)}
                            title="View details"
                          >
                            <Eye size={14} />
                          </button>
                          {alert.status === 'new' && (
                            <button
                              className="btn btn-secondary btn-sm btn-icon"
                              onClick={() => handleAcknowledge(alert.id)}
                              title="Acknowledge"
                            >
                              <Check size={14} />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}
    </div>
  );
}
