import { useState, useEffect, useRef } from 'react';
import { FileText, Download, Loader2, RefreshCw } from 'lucide-react';
import { getSessions, generateReport, getReports, downloadReport } from '../services/api';

export default function Reports({ wsProgress }) {
  const [sessions, setSessions] = useState([]);
  const [reports, setReports] = useState([]);
  const [generating, setGenerating] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);
  const lastProgressStageRef = useRef(null);

  useEffect(() => {
    loadData();
  }, []);

  /**
   * When the WebSocket pipeline broadcasts a "complete" progress event,
   * automatically refresh the sessions list so completed sessions appear
   * without requiring the user to manually reload.
   */
  useEffect(() => {
    if (!wsProgress) return;
    if (wsProgress.stage === 'complete' && wsProgress.stage !== lastProgressStageRef.current) {
      lastProgressStageRef.current = wsProgress.stage;
      // Small delay to allow backend to finish committing the session record
      const timer = setTimeout(() => {
        loadData();
        lastProgressStageRef.current = null; // Reset so next pipeline run also triggers
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [wsProgress]);

  const loadData = async () => {
    setError(null);
    try {
      const [sessRes, repRes] = await Promise.all([
        getSessions(),
        getReports(),
      ]);
      setSessions(Array.isArray(sessRes.data) ? sessRes.data.filter((s) => s.status === 'completed') : []);
      setReports(Array.isArray(repRes.data) ? repRes.data : []);
    } catch (e) {
      console.error('Failed to load data:', e);
      const msg = e?.response?.data?.detail || e?.message || 'Unknown error';
      setError(`Failed to load data: ${msg}`);
      setSessions([]);
      setReports([]);
    }
    setLoading(false);
    setRefreshing(false);
  };

  const handleRefresh = () => {
    setRefreshing(true);
    loadData();
  };

  const handleGenerate = async (sessionId) => {
    setGenerating(sessionId);
    try {
      await generateReport(sessionId);
      await loadData();
    } catch (e) {
      console.error('Failed to generate report:', e);
    }
    setGenerating(null);
  };

  const handleDownload = async (report) => {
    try {
      const response = await downloadReport(report.id);
      const url = URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = `campusshield-report-${report.id}.pdf`;
      link.click();
      URL.revokeObjectURL(url);
    } catch (e) {
      console.error('Failed to download report:', e);
    }
  };

  return (
    <div className="animate-in">
      <div className="page-header">
        <div>
          <h1>Reports</h1>
          <p>Generate and download PDF reports from completed analysis sessions</p>
        </div>
        <button
          className="btn btn-secondary btn-sm"
          onClick={handleRefresh}
          disabled={refreshing}
          style={{ display: 'flex', alignItems: 'center', gap: 6 }}
          title="Refresh sessions from backend"
        >
          <RefreshCw size={14} style={{ animation: refreshing ? 'spin 1s linear infinite' : 'none' }} />
          {refreshing ? 'Refreshing...' : 'Refresh'}
        </button>
      </div>

      {/* Generate Reports */}
      <div className="card" style={{ marginBottom: '24px' }}>
        <div className="card-header">
          <span className="card-title">Generate Report</span>
        </div>

        {loading ? (
          <div className="empty-state">
            <div style={{ color: 'var(--accent-cyan)', fontSize: '13px' }}>Loading sessions...</div>
          </div>
        ) : error ? (
          <div className="empty-state">
            <FileText size={48} style={{ color: 'var(--severity-critical)' }} />
            <h3 style={{ color: 'var(--severity-critical)' }}>Failed to Load Sessions</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: '12px', fontFamily: 'var(--font-mono)' }}>{error}</p>
            <button className="btn btn-primary btn-sm" onClick={handleRefresh} style={{ marginTop: '12px' }}>
              Retry
            </button>
          </div>
        ) : sessions.length === 0 ? (
          <div className="empty-state">
            <FileText size={48} />
            <h3>No Completed Sessions</h3>
            <p>Run a simulation or upload a PCAP file to create a session. Sessions appear here once analysis completes.</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>Session</th>
                <th>Type</th>
                <th>Packets</th>
                <th>Windows</th>
                <th>Completed</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((s) => (
                <tr key={s.id}>
                  <td style={{ color: 'var(--text-primary)' }}>{s.name}</td>
                  <td style={{ textTransform: 'uppercase' }}>{s.source_type}</td>
                  <td>{s.packet_count?.toLocaleString()}</td>
                  <td>{s.flow_count}</td>
                  <td>{s.completed_at ? new Date(s.completed_at).toLocaleString() : '—'}</td>
                  <td>
                    <button
                      className="btn btn-primary btn-sm"
                      onClick={() => handleGenerate(s.id)}
                      disabled={generating === s.id}
                    >
                      {generating === s.id ? (
                        <><Loader2 size={14} className="loading-pulse" /> Generating...</>
                      ) : (
                        <><FileText size={14} /> Generate PDF</>
                      )}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Report History */}
      <div className="card">
        <div className="card-header">
          <span className="card-title">Report History</span>
        </div>

        {reports.length === 0 ? (
          <div className="empty-state">
            <p>No reports generated yet</p>
          </div>
        ) : (
          <table className="data-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Session</th>
                <th>Size</th>
                <th>Generated By</th>
                <th>Created</th>
                <th>Action</th>
              </tr>
            </thead>
            <tbody>
              {reports.map((r) => (
                <tr key={r.id}>
                  <td style={{ color: 'var(--text-primary)' }}>#{r.id}</td>
                  <td>Session #{r.session_id}</td>
                  <td>{r.file_size_bytes ? `${(r.file_size_bytes / 1024).toFixed(1)} KB` : '—'}</td>
                  <td>{r.generated_by || '—'}</td>
                  <td>{new Date(r.created_at).toLocaleString()}</td>
                  <td>
                    <button
                      type="button"
                      onClick={() => handleDownload(r)}
                      className="btn btn-secondary btn-sm"
                    >
                      <Download size={14} /> Download
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
