import { useState, useEffect } from 'react';
import Head from 'next/head';
import axios from 'axios';
import {
  RefreshCw, Database, Mail, MessageSquare, CheckCircle, XCircle, Eye,
  Filter, Users, TrendingUp, Clock, Send, Calendar, Zap, CheckSquare, Square
} from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || '/api/proxy';

interface Metrics {
  total_leads: number;
  leads_enriched: number;
  messages_generated: number;
  messages_sent: number;
  messages_failed: number;
  status_breakdown: Record<string, number>;
  pipeline_running: boolean;
  current_stage: string | null;
  progress: number;
}

interface Lead {
  id: number;
  full_name: string;
  company_name: string;
  role_title: string;
  industry: string;
  email: string;
  linkedin_url?: string;
  company_website?: string;
  phone?: string;
  comments?: string;
  source?: string;
  status: string;
  updated_at: string;
}

interface LeadMessages {
  [key: string]: {
    subject?: string;
    body?: string;
    html_body?: string;
    revision?: number;
    review_feedback?: string | null;
    message?: string;
  };
}

export default function Home() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [totalLeadCount, setTotalLeadCount] = useState(0);
  const [leadLoadError, setLeadLoadError] = useState('');
  const [refreshingLeads, setRefreshingLeads] = useState(false);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [selectedLeadMessages, setSelectedLeadMessages] = useState<LeadMessages | null>(null);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [filterSource, setFilterSource] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [approvingEmail, setApprovingEmail] = useState(false);
  const [revisingEmail, setRevisingEmail] = useState(false);
  const [selectedVariation, setSelectedVariation] = useState<'A' | 'B'>('A');
  const [reviewFeedback, setReviewFeedback] = useState('');
  const [approvalMessage, setApprovalMessage] = useState('');

  // Multi-select, Bulk Actions & Scheduling state
  const [selectedLeadIds, setSelectedLeadIds] = useState<number[]>([]);
  const [autoSendAll, setAutoSendAll] = useState(false);
  const [scheduleModalOpen, setScheduleModalOpen] = useState(false);
  const [scheduleTarget, setScheduleTarget] = useState<'selected' | 'all'>('selected');
  const [schedulePreset, setSchedulePreset] = useState<'1h' | '3h' | 'tomorrow' | 'custom'>('1h');
  const [customScheduleTime, setCustomScheduleTime] = useState('');
  const [bulkActionLoading, setBulkActionLoading] = useState(false);
  const [bulkActionFeedback, setBulkActionFeedback] = useState('');

  const fetchMetrics = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/metrics`);
      setMetrics(response.data);
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
    }
  };

  const fetchLeads = async () => {
    try {
      const response = await axios.get(`${API_BASE_URL}/leads?limit=100`);
      if (!Array.isArray(response.data.leads)) throw new Error('API response did not include a leads list.');
      setLeads(response.data.leads);
      setTotalLeadCount(Number(response.data.total) || response.data.leads.length);
      setLeadLoadError('');
    } catch (error: any) {
      console.error('Failed to fetch leads:', error);
      setLeadLoadError(error?.response?.data?.detail || error?.message || 'Could not load leads from the API.');
    }
  };

  const refreshDashboard = async () => {
    setRefreshingLeads(true);
    try {
      await Promise.all([fetchLeads(), fetchMetrics()]);
    } finally {
      setRefreshingLeads(false);
    }
  };

  const clearData = async () => {
    if (!confirm('Are you sure you want to clear all data?')) return;
    
    try {
      await axios.delete(`${API_BASE_URL}/leads`);
      fetchMetrics();
      fetchLeads();
    } catch (error) {
      console.error('Failed to clear data:', error);
    }
  };

  const fetchLeadMessages = async (leadId: number) => {
    setLoadingMessages(true);
    try {
      const response = await axios.get(`${API_BASE_URL}/leads/${leadId}/messages`);
      setSelectedLeadMessages(response.data.messages);
    } catch (error) {
      console.error('Failed to fetch lead messages:', error);
      setSelectedLeadMessages(null);
    } finally {
      setLoadingMessages(false);
    }
  };

  const handleViewLead = async (lead: Lead) => {
    setSelectedLead(lead);
    setSelectedLeadMessages(null);
    setSelectedVariation('A');
    setReviewFeedback('');
    setApprovalMessage('');
    await fetchLeadMessages(lead.id);
  };

  const approveEmail = async () => {
    if (!selectedLead || !confirm(`Approve Variation ${selectedVariation} and send the email to ${selectedLead.email}?`)) return;
    setApprovingEmail(true);
    setApprovalMessage('');
    try {
      await axios.post(`${API_BASE_URL}/leads/${selectedLead.id}/approve`, {
        variation: selectedVariation,
      });
      setApprovalMessage(`Variation ${selectedVariation} approved. Email delivery has been queued.`);
      setSelectedLead({ ...selectedLead, status: 'SENDING' });
      await fetchLeads();
      await fetchMetrics();
    } catch (error: any) {
      setApprovalMessage(error?.response?.data?.detail || 'Could not queue email delivery.');
    } finally {
      setApprovingEmail(false);
    }
  };

  const requestRewrite = async () => {
    if (!selectedLead || !reviewFeedback.trim()) return;
    setRevisingEmail(true);
    setApprovalMessage(`Rewriting Variation ${selectedVariation}…`);
    try {
      const response = await axios.post(
        `${API_BASE_URL}/leads/${selectedLead.id}/revise`,
        { variation: selectedVariation, feedback: reviewFeedback.trim() },
        { headers: { 'Idempotency-Key': crypto.randomUUID() } },
      );
      const jobId = response.data.job_id;
      for (let attempt = 0; attempt < 120; attempt += 1) {
        await new Promise(resolve => setTimeout(resolve, 1500));
        const jobResponse = await axios.get(`${API_BASE_URL}/jobs/${jobId}`);
        const job = jobResponse.data;
        if (job.status === 'COMPLETED') {
          await fetchLeadMessages(selectedLead.id);
          setReviewFeedback('');
          setApprovalMessage(`Variation ${selectedVariation} updated. Review it below before sending.`);
          return;
        }
        if (job.status === 'FAILED' || job.status === 'SUPPRESSED') {
          throw new Error(job.error_message || `Rewrite ${job.status.toLowerCase()}.`);
        }
      }
      setApprovalMessage('Rewrite is still running. Close and reopen this lead to see the updated draft.');
    } catch (error: any) {
      setApprovalMessage(error?.response?.data?.detail || error?.message || 'Could not rewrite the email.');
    } finally {
      setRevisingEmail(false);
      await fetchMetrics();
    }
  };

  const filteredLeads = leads.filter(lead => {
    if (filterSource === 'facebook' && !['facebook', 'facebook_leads'].includes(lead.source || '')) return false;
    if (filterSource === 'google_sheets' && lead.source !== 'google_sheets') return false;
    if (filterStatus !== 'all' && lead.status !== filterStatus) return false;
    return true;
  });

  const pendingLeads = leads.filter(l => l.status === 'PENDING_APPROVAL');
  const pendingCount = pendingLeads.length;

  const toggleSelectLead = (id: number) => {
    setSelectedLeadIds(prev =>
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const isAllFilteredSelected = filteredLeads.length > 0 && filteredLeads.every(l => selectedLeadIds.includes(l.id));

  const toggleSelectAll = () => {
    if (isAllFilteredSelected) {
      setSelectedLeadIds(prev => prev.filter(id => !filteredLeads.some(l => l.id === id)));
    } else {
      const allFilteredIds = filteredLeads.map(l => l.id);
      setSelectedLeadIds(prev => Array.from(new Set([...prev, ...allFilteredIds])));
    }
  };

  const toggleAutoSendAll = async () => {
    const nextState = !autoSendAll;
    setAutoSendAll(nextState);
    if (nextState && pendingCount > 0) {
      if (confirm(`Auto-Send Mode is now ON! Would you like to immediately queue outreach for all ${pendingCount} lead(s) awaiting review?`)) {
        await handleSendAllPending();
      }
    }
  };

  const handleRetryLead = async (leadId: number) => {
    try {
      await axios.post(`${API_BASE_URL}/leads/${leadId}/retry`);
      setBulkActionFeedback('🔄 Re-queued lead for processing.');
      await refreshDashboard();
    } catch (err: any) {
      alert(`Could not retry lead: ${err?.response?.data?.detail || err.message}`);
    }
  };

  const handleSendSelected = async () => {
    if (selectedLeadIds.length === 0) return;
    if (!confirm(`Approve and send outreach to ${selectedLeadIds.length} selected lead(s)?`)) return;
    setBulkActionLoading(true);
    setBulkActionFeedback('');
    try {
      const res = await axios.post(`${API_BASE_URL}/leads/bulk-approve`, {
        lead_ids: selectedLeadIds,
        variation: 'A',
      });
      setBulkActionFeedback(`✅ Successfully queued outreach for ${res.data.queued_count} selected lead(s)!`);
      setSelectedLeadIds([]);
      await refreshDashboard();
    } catch (err: any) {
      setBulkActionFeedback(`❌ Error: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setBulkActionLoading(false);
    }
  };

  const handleSendAllPending = async () => {
    if (pendingCount === 0) {
      alert('No leads are currently awaiting review.');
      return;
    }
    if (!confirm(`Approve and send outreach to all ${pendingCount} pending lead(s)?`)) return;
    setBulkActionLoading(true);
    setBulkActionFeedback('');
    try {
      const res = await axios.post(`${API_BASE_URL}/leads/approve-all`, {
        variation: 'A',
      });
      setBulkActionFeedback(`✅ Successfully queued outreach for all ${res.data.queued_count} pending lead(s)!`);
      await refreshDashboard();
    } catch (err: any) {
      setBulkActionFeedback(`❌ Error: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setBulkActionLoading(false);
    }
  };

  const handleOpenScheduleModal = (target: 'selected' | 'all') => {
    if (target === 'selected' && selectedLeadIds.length === 0) {
      alert('Please select at least one lead from the table first.');
      return;
    }
    if (target === 'all' && pendingCount === 0) {
      alert('No leads are currently awaiting review.');
      return;
    }
    setScheduleTarget(target);
    setSchedulePreset('1h');
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(9, 0, 0, 0);
    setCustomScheduleTime(tomorrow.toISOString().slice(0, 16));
    setScheduleModalOpen(true);
  };

  const handleExecuteSchedule = async () => {
    let schedIso = '';
    const now = new Date();
    if (schedulePreset === '1h') {
      schedIso = new Date(now.getTime() + 60 * 60 * 1000).toISOString();
    } else if (schedulePreset === '3h') {
      schedIso = new Date(now.getTime() + 3 * 60 * 60 * 1000).toISOString();
    } else if (schedulePreset === 'tomorrow') {
      const tom = new Date(now);
      tom.setDate(tom.getDate() + 1);
      tom.setHours(9, 0, 0, 0);
      schedIso = tom.toISOString();
    } else if (schedulePreset === 'custom') {
      if (!customScheduleTime) {
        alert('Please choose a valid date and time.');
        return;
      }
      schedIso = new Date(customScheduleTime).toISOString();
    }

    setBulkActionLoading(true);
    setBulkActionFeedback('');
    try {
      if (scheduleTarget === 'selected') {
        const res = await axios.post(`${API_BASE_URL}/leads/bulk-approve`, {
          lead_ids: selectedLeadIds,
          variation: 'A',
          scheduled_for: schedIso,
        });
        setBulkActionFeedback(`🕒 Scheduled outreach for ${res.data.queued_count} lead(s) at ${new Date(schedIso).toLocaleString()}!`);
        setSelectedLeadIds([]);
      } else {
        const res = await axios.post(`${API_BASE_URL}/leads/approve-all`, {
          variation: 'A',
          scheduled_for: schedIso,
        });
        setBulkActionFeedback(`🕒 Scheduled outreach for all ${res.data.queued_count} pending lead(s) at ${new Date(schedIso).toLocaleString()}!`);
      }
      setScheduleModalOpen(false);
      await refreshDashboard();
    } catch (err: any) {
      alert(`Scheduling failed: ${err?.response?.data?.detail || err.message}`);
    } finally {
      setBulkActionLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    fetchLeads();

    // Poll for updates every 10 seconds (reduced from 3 seconds)
    const interval = setInterval(() => {
      if (autoRefresh) {
        fetchMetrics();
        fetchLeads();
      }
    }, 10000);

    return () => clearInterval(interval);
  }, [autoRefresh]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'NEW': return 'bg-gray-700 text-gray-200';
      case 'ENRICHED': return 'bg-blue-900 text-blue-200';
      case 'MESSAGED': return 'bg-purple-900 text-purple-200';
      case 'PENDING_APPROVAL': return 'bg-amber-900 text-amber-200';
      case 'SENT': return 'bg-green-900 text-green-200';
      case 'FAILED': return 'bg-red-900 text-red-200';
      default: return 'bg-gray-700 text-gray-200';
    }
  };

  return (
    <>
      <Head>
        <title>Lead Generation Pipeline - MCP Dashboard</title>
        <meta name="description" content="Monitor your lead generation pipeline" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className="min-h-screen bg-gradient-to-br from-gray-900 to-gray-950">
        {/* Header */}
        <header className="bg-gray-800 shadow-lg border-b border-gray-700">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-white">Lead Monitoring Dashboard</h1>
                <p className="text-sm text-gray-400 mt-1">Real-time Lead Processing from Facebook & Google Sheets</p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={toggleAutoSendAll}
                  title="Toggle automatic email dispatch for all incoming/pending leads"
                  className={`flex items-center gap-2 px-3 py-2 text-sm rounded-md font-medium transition-colors shadow-sm ${
                    autoSendAll
                      ? 'bg-amber-600 hover:bg-amber-500 text-white'
                      : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                  }`}
                >
                  <Zap className={`w-4 h-4 ${autoSendAll ? 'text-yellow-200 fill-yellow-200' : ''}`} />
                  {autoSendAll ? 'Auto-Send: ON' : 'Auto-Send: OFF'}
                </button>
                <button
                  onClick={handleSendAllPending}
                  disabled={pendingCount === 0 || bulkActionLoading}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm bg-green-700 hover:bg-green-600 text-white font-medium rounded-md shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Send className="w-4 h-4" />
                  Send All Pending ({pendingCount})
                </button>
                <button
                  onClick={() => handleOpenScheduleModal('all')}
                  disabled={pendingCount === 0 || bulkActionLoading}
                  className="flex items-center gap-1.5 px-3 py-2 text-sm bg-purple-700 hover:bg-purple-600 text-purple-100 font-medium rounded-md shadow-sm disabled:opacity-40 disabled:cursor-not-allowed"
                >
                  <Calendar className="w-4 h-4" />
                  Schedule All ({pendingCount})
                </button>
                <button
                  onClick={() => setAutoRefresh(!autoRefresh)}
                  className={`flex items-center gap-2 px-3 py-2 text-sm rounded-md ${
                    autoRefresh 
                      ? 'bg-blue-900 hover:bg-blue-800 text-blue-200' 
                      : 'bg-gray-700 hover:bg-gray-600 text-gray-300'
                  }`}
                >
                  {autoRefresh ? (
                    <>
                      <RefreshCw className="w-4 h-4 animate-spin" />
                      Auto-refresh ON
                    </>
                  ) : (
                    <>
                      <RefreshCw className="w-4 h-4" />
                      Auto-refresh OFF
                    </>
                  )}
                </button>
                <button
                  onClick={refreshDashboard}
                  disabled={refreshingLeads}
                  className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-md disabled:opacity-50"
                >
                  <RefreshCw className={`w-4 h-4 ${refreshingLeads ? 'animate-spin' : ''}`} />
                  Refresh
                </button>
                <button
                  onClick={clearData}
                  className="flex items-center gap-2 px-3 py-2 text-sm bg-red-900 hover:bg-red-800 text-red-200 rounded-md"
                >
                  <XCircle className="w-4 h-4" />
                  Clear All
                </button>
              </div>
            </div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Filters */}
          <div className="bg-gray-800 rounded-lg shadow-xl border border-gray-700 p-6 mb-6">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Filters</h2>
              <button
                onClick={() => {
                  setFilterSource('all');
                  setFilterStatus('all');
                }}
                className="text-sm text-blue-400 hover:text-blue-300"
              >
                Clear Filters
              </button>
            </div>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mt-4">
              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Source
                </label>
                <select
                  value={filterSource}
                  onChange={(e) => setFilterSource(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-gray-200 rounded-md focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                >
                  <option value="all">All Sources</option>
                  <option value="facebook">Facebook Lead Ads</option>
                  <option value="google_sheets">Google Sheets</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Status
                </label>
                <select
                  value={filterStatus}
                  onChange={(e) => setFilterStatus(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-700 border border-gray-600 text-gray-200 rounded-md focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                >
                  <option value="all">All Status</option>
                  <option value="NEW">New</option>
                  <option value="ENRICHED">Enriched</option>
                  <option value="MESSAGED">Messaged</option>
                  <option value="PENDING_APPROVAL">Awaiting Review</option>
                  <option value="SENT">Sent</option>
                  <option value="FAILED">Failed</option>
                  <option value="SUPPRESSED">Suppressed</option>
                </select>
              </div>
            </div>
          </div>

          {leadLoadError && (
            <div role="alert" className="mb-5 flex items-center justify-between gap-3 rounded-lg border border-red-700 bg-red-950/60 px-4 py-3 text-sm text-red-200">
              <span>Could not load leads: {leadLoadError}</span>
              <button onClick={refreshDashboard} className="shrink-0 underline">Retry</button>
            </div>
          )}

          {/* Metrics Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
            <MetricCard
              title="Total Leads"
              value={totalLeadCount}
              icon={<Database className="w-6 h-6" />}
              color="bg-blue-500"
            />
            <MetricCard
              title="Facebook Leads"
              value={leads.filter(l => l.source === 'facebook_leads' || l.source === 'facebook').length}
              icon={<Users className="w-6 h-6" />}
              color="bg-blue-600"
            />
            <MetricCard
              title="Google Sheets"
              value={leads.filter(l => l.source === 'google_sheets').length}
              icon={<CheckCircle className="w-6 h-6" />}
              color="bg-green-600"
            />
            <MetricCard
              title="Messaged"
              value={leads.filter(l => l.status === 'MESSAGED' || l.status === 'SENT').length}
              icon={<MessageSquare className="w-6 h-6" />}
              color="bg-purple-500"
            />
            <MetricCard
              title="Sent"
              value={leads.filter(l => l.status === 'SENT').length}
              icon={<Mail className="w-6 h-6" />}
              color="bg-green-500"
            />
          </div>

          {/* Bulk Action Feedback Banner */}
          {bulkActionFeedback && (
            <div className="mb-6 flex items-center justify-between gap-3 rounded-lg border border-indigo-700 bg-indigo-950/70 px-4 py-3 text-sm text-indigo-100 shadow-lg">
              <span>{bulkActionFeedback}</span>
              <button
                onClick={() => setBulkActionFeedback('')}
                className="text-xs text-indigo-300 hover:text-white underline ml-4"
              >
                Dismiss
              </button>
            </div>
          )}

          {/* Selected Leads Floating Action Bar */}
          {selectedLeadIds.length > 0 && (
            <div className="mb-6 bg-gradient-to-r from-purple-900/90 to-indigo-900/90 border border-purple-500 rounded-lg p-4 shadow-xl flex flex-wrap items-center justify-between gap-4 animate-in fade-in slide-in-from-top-2">
              <div className="flex items-center gap-2">
                <CheckSquare className="w-5 h-5 text-purple-300" />
                <span className="font-semibold text-white">
                  {selectedLeadIds.length} lead{selectedLeadIds.length > 1 ? 's' : ''} selected
                </span>
                <span className="text-xs text-purple-200 ml-2">
                  (Actions apply strictly to these specific leads)
                </span>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <button
                  onClick={handleSendSelected}
                  disabled={bulkActionLoading}
                  className="flex items-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-md shadow disabled:opacity-50 transition-colors"
                >
                  <Send className="w-4 h-4" />
                  Send Outreach ({selectedLeadIds.length})
                </button>
                <button
                  onClick={() => handleOpenScheduleModal('selected')}
                  disabled={bulkActionLoading}
                  className="flex items-center gap-1.5 px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white font-medium rounded-md shadow disabled:opacity-50 transition-colors"
                >
                  <Calendar className="w-4 h-4" />
                  Schedule Selected ({selectedLeadIds.length})
                </button>
                <button
                  onClick={() => setSelectedLeadIds([])}
                  className="px-3 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white text-sm rounded-md transition-colors"
                >
                  Clear Selection
                </button>
              </div>
            </div>
          )}

          {/* Leads Table */}
          <div className="bg-gray-800 rounded-lg shadow-xl border border-gray-700 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-700 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Leads ({filteredLeads.length} shown of {totalLeadCount})</h2>
              <div className="flex items-center gap-3 text-sm text-gray-400">
                <span>{autoRefresh ? 'Auto-refresh every 10 seconds' : 'Auto-refresh paused'}</span>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-700">
                <thead className="bg-gray-900">
                  <tr>
                    <th className="px-4 py-3 text-left w-10">
                      <input
                        type="checkbox"
                        checked={isAllFilteredSelected}
                        onChange={toggleSelectAll}
                        aria-label="Select all filtered leads"
                        className="w-4 h-4 text-purple-600 bg-gray-700 border-gray-600 rounded focus:ring-purple-500 focus:ring-2 cursor-pointer"
                      />
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Company
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Role
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Source
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Status
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider">
                      Actions
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-gray-800 divide-y divide-gray-700">
                  {filteredLeads.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-6 py-4 text-center text-gray-400">
                        {filterSource !== 'all' || filterStatus !== 'all' 
                          ? 'No leads match the selected filters.'
                          : 'No leads yet. Leads will appear here automatically when they arrive from Facebook or Google Sheets.'}
                      </td>
                    </tr>
                  ) : (
                    filteredLeads.map((lead) => {
                      const isSelected = selectedLeadIds.includes(lead.id);
                      return (
                        <tr key={lead.id} className={`hover:bg-gray-700 transition-colors ${isSelected ? 'bg-purple-950/30' : ''}`}>
                          <td className="px-4 py-4 whitespace-nowrap">
                            <input
                              type="checkbox"
                              checked={isSelected}
                              onChange={() => toggleSelectLead(lead.id)}
                              aria-label={`Select lead ${lead.full_name}`}
                              className="w-4 h-4 text-purple-600 bg-gray-700 border-gray-600 rounded focus:ring-purple-500 focus:ring-2 cursor-pointer"
                            />
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-100">
                            {lead.full_name}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-200">
                            {lead.company_name}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-300">
                            {lead.role_title}
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                              lead.source === 'facebook_leads' || lead.source === 'facebook'
                                ? 'bg-blue-900 text-blue-200'
                                : lead.source === 'google_sheets'
                                ? 'bg-green-900 text-green-200'
                                : 'bg-gray-700 text-gray-300'
                            }`}>
                              {lead.source === 'facebook_leads' || lead.source === 'facebook' ? 'Facebook' : lead.source === 'google_sheets' ? 'Google Sheets' : 'Manual/Unknown'}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap">
                            <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(lead.status)}`}>
                              {lead.status}
                            </span>
                          </td>
                          <td className="px-6 py-4 whitespace-nowrap text-sm">
                            <div className="flex items-center gap-2">
                              <button
                                onClick={() => handleViewLead(lead)}
                                className="text-blue-400 hover:text-blue-300 flex items-center gap-1"
                              >
                                <Eye className="w-4 h-4" />
                                View
                              </button>
                              {lead.status === 'FAILED' && (
                                <button
                                  onClick={() => handleRetryLead(lead.id)}
                                  className="text-amber-400 hover:text-amber-300 flex items-center gap-1 text-xs px-2 py-1 bg-amber-950/40 border border-amber-700/60 rounded transition-colors"
                                  title="Retry processing this lead"
                                >
                                  <RefreshCw className="w-3 h-3" />
                                  Retry
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Lead Details Modal */}
          {selectedLead && (
            <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
              <div className="bg-gray-800 rounded-lg max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto border border-gray-700">
                <div className="px-6 py-4 border-b border-gray-700 flex items-center justify-between sticky top-0 bg-gray-800">
                  <h3 className="text-lg font-semibold text-white">Lead Details</h3>
                  <button
                    onClick={() => setSelectedLead(null)}
                    className="text-gray-400 hover:text-gray-300"
                  >
                    <XCircle className="w-6 h-6" />
                  </button>
                </div>
                
                <div className="px-6 py-4 space-y-6">
                  {/* Basic Info */}
                  <div>
                    <h4 className="text-sm font-semibold text-gray-200 mb-3">Basic Information</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="text-xs text-gray-400">Name</label>
                        <p className="text-sm font-medium text-gray-100">{selectedLead.full_name}</p>
                      </div>
                      <div>
                        <label className="text-xs text-gray-400">Email</label>
                        <p className="text-sm font-medium text-gray-100">{selectedLead.email || 'N/A'}</p>
                      </div>
                      <div>
                        <label className="text-xs text-gray-400">Phone</label>
                        <p className="text-sm font-medium text-gray-100">{selectedLead.phone || 'N/A'}</p>
                      </div>
                      <div>
                        <label className="text-xs text-gray-400">Company</label>
                        <p className="text-sm font-medium text-gray-100">{selectedLead.company_name}</p>
                      </div>
                      <div>
                        <label className="text-xs text-gray-400">Role</label>
                        <p className="text-sm font-medium text-gray-100">{selectedLead.role_title}</p>
                      </div>
                      <div>
                        <label className="text-xs text-gray-400">Industry</label>
                        <p className="text-sm font-medium text-gray-100">{selectedLead.industry || 'N/A'}</p>
                      </div>
                      <div>
                        <label className="text-xs text-gray-400">Source</label>
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${
                          selectedLead.source === 'facebook_leads' || selectedLead.source === 'facebook'
                            ? 'bg-blue-900 text-blue-200'
                            : selectedLead.source === 'google_sheets'
                            ? 'bg-green-900 text-green-200'
                            : 'bg-gray-700 text-gray-300'
                        }`}>
                          {selectedLead.source === 'facebook_leads' || selectedLead.source === 'facebook' ? 'Facebook Lead Ads' : selectedLead.source === 'google_sheets' ? 'Google Sheets' : 'Manual/Unknown'}
                        </span>
                      </div>
                      <div>
                        <label className="text-xs text-gray-400">Status</label>
                        <span className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(selectedLead.status)}`}>
                          {selectedLead.status}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Comments */}
                  {selectedLead.comments && (
                    <div>
                      <h4 className="text-sm font-semibold text-gray-200 mb-2">Comments</h4>
                      <p className="text-sm text-gray-300 bg-gray-900 p-3 rounded-md">{selectedLead.comments}</p>
                    </div>
                  )}

                  {/* LinkedIn */}
                  {selectedLead.linkedin_url && (
                    <div>
                      <h4 className="text-sm font-semibold text-gray-200 mb-2">LinkedIn</h4>
                      <a
                        href={selectedLead.linkedin_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-blue-400 hover:text-blue-300"
                      >
                        {selectedLead.linkedin_url}
                      </a>
                    </div>
                  )}

                  {/* Company Website */}
                  {selectedLead.company_website && (
                    <div>
                      <h4 className="text-sm font-semibold text-gray-200 mb-2">Company Website</h4>
                      <a
                        href={selectedLead.company_website}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-sm text-blue-400 hover:text-blue-300"
                      >
                        {selectedLead.company_website}
                      </a>
                    </div>
                  )}

                  {/* Generated Messages */}
                  <div>
                    <h4 className="text-sm font-semibold text-gray-200 mb-3">Generated Messages</h4>
                    {loadingMessages ? (
                      <div className="flex items-center justify-center py-8">
                        <RefreshCw className="w-6 h-6 animate-spin text-gray-500" />
                        <span className="ml-2 text-sm text-gray-400">Loading messages...</span>
                      </div>
                    ) : selectedLeadMessages && Object.keys(selectedLeadMessages).length > 0 ? (
                      <div className="space-y-4">
                        {/* Email Messages */}
                        {Object.keys(selectedLeadMessages).filter(key => key.startsWith('email_')).length > 0 && (
                          <div className="border border-gray-700 rounded-lg p-4">
                            <div className="flex items-center gap-2 mb-3">
                              <Mail className="w-4 h-4 text-purple-400" />
                              <h5 className="text-sm font-semibold text-gray-200">Email Messages</h5>
                            </div>
                            
                            {Object.entries(selectedLeadMessages)
                              .filter(([key]) => key.startsWith('email_'))
                              .map(([key, value], index) => {
                                const variation = key.replace('email_', '').toUpperCase();
                                return (
                                  <div key={key} className={`${index > 0 ? 'mt-4 pt-4 border-t border-gray-700' : ''}`}>
                                    <div className={`px-3 py-2 rounded-t-md flex items-center justify-between ${selectedVariation === variation ? 'bg-purple-800/60 ring-1 ring-purple-400' : 'bg-purple-900/30'}`}>
                                      <div>
                                        <p className="text-xs font-medium text-purple-300">Variation {variation}{value.revision && value.revision > 1 ? ` · revision ${value.revision}` : ''}</p>
                                        {value.review_feedback && <p className="mt-1 text-xs text-purple-200">Latest note: {value.review_feedback}</p>}
                                      </div>
                                      {selectedLead.status === 'PENDING_APPROVAL' && (
                                        <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-white">
                                          <input
                                            type="radio"
                                            name="email-variation"
                                            value={variation}
                                            checked={selectedVariation === variation}
                                            onChange={() => setSelectedVariation(variation === 'B' ? 'B' : 'A')}
                                            className="accent-purple-400"
                                          />
                                          Choose to send
                                        </label>
                                      )}
                                    </div>
                                    <div className={`bg-gray-900 p-3 rounded-b-md ${selectedLead.status === 'PENDING_APPROVAL' && selectedVariation === variation ? 'ring-1 ring-purple-400' : ''}`}>
                                      <p className="text-xs text-gray-400 mb-1">Subject:</p>
                                      <p className="text-sm font-medium text-gray-100 mb-3">{value.subject}</p>
                                      {value.html_body ? (
                                        <iframe
                                          title={`Email variation ${variation} preview`}
                                          sandbox=""
                                          srcDoc={value.html_body}
                                          className="mt-3 h-[440px] w-full rounded-lg border border-gray-700 bg-white"
                                        />
                                      ) : (
                                        <>
                                          <p className="text-xs text-gray-400 mb-1">Body:</p>
                                          <p className="text-sm text-gray-300 whitespace-pre-wrap">{value.body}</p>
                                        </>
                                      )}
                                    </div>
                                  </div>
                                );
                              })}
                          </div>
                        )}

                        {selectedLead.status === 'PENDING_APPROVAL' && (
                          <div className="rounded-lg border border-amber-700/60 bg-amber-950/30 p-4">
                            <h5 className="text-sm font-semibold text-amber-200">Request changes</h5>
                            <p className="mt-1 text-xs text-gray-300">
                              Add the points you want included or explain what should change in Variation {selectedVariation}. The previous version remains saved.
                            </p>
                            <textarea
                              value={reviewFeedback}
                              onChange={event => setReviewFeedback(event.target.value)}
                              disabled={revisingEmail}
                              maxLength={2000}
                              rows={4}
                              placeholder="For example: mention their interest in voice AI, make the opening less formal, and keep the call request to one sentence."
                              className="mt-3 w-full rounded-md border border-gray-600 bg-gray-900 p-3 text-sm text-gray-100 placeholder:text-gray-500 focus:border-amber-400 focus:outline-none disabled:opacity-60"
                            />
                            <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
                              <span className="text-xs text-gray-400">{reviewFeedback.length}/2000 characters</span>
                              <button
                                onClick={requestRewrite}
                                disabled={revisingEmail || !reviewFeedback.trim()}
                                className="rounded-md bg-amber-700 px-4 py-2 text-sm font-medium text-white hover:bg-amber-600 disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                {revisingEmail ? 'Rewriting…' : `Reject & rewrite Variation ${selectedVariation}`}
                              </button>
                            </div>
                          </div>
                        )}

                        {/* LinkedIn Messages */}
                        {Object.keys(selectedLeadMessages).filter(key => key.startsWith('linkedin_')).length > 0 && (
                          <div className="border border-gray-700 rounded-lg p-4">
                            <div className="flex items-center gap-2 mb-3">
                              <MessageSquare className="w-4 h-4 text-blue-400" />
                              <h5 className="text-sm font-semibold text-gray-200">LinkedIn Messages</h5>
                            </div>
                            
                            {Object.entries(selectedLeadMessages)
                              .filter(([key]) => key.startsWith('linkedin_'))
                              .map(([key, value], index) => {
                                const variation = key.replace('linkedin_', '').toUpperCase();
                                return (
                                  <div key={key} className={`${index > 0 ? 'mt-4 pt-4 border-t border-gray-700' : ''}`}>
                                    <div className="bg-blue-900/30 px-3 py-2 rounded-t-md">
                                      <p className="text-xs font-medium text-blue-300">Variation {variation}</p>
                                    </div>
                                    <div className="bg-gray-900 p-3 rounded-b-md">
                                      <p className="text-sm text-gray-300 whitespace-pre-wrap">{value.message}</p>
                                    </div>
                                  </div>
                                );
                              })}
                          </div>
                        )}
                      </div>
                    ) : (
                      <div className="bg-gray-900 rounded-lg p-6 text-center">
                        <MessageSquare className="w-8 h-8 text-gray-600 mx-auto mb-2" />
                        <p className="text-sm text-gray-400">No messages generated for this lead yet.</p>
                      </div>
                    )}
                  </div>
                </div>

                <div className="px-6 py-4 border-t border-gray-700 bg-gray-900 flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    {selectedLead.status === 'FAILED' && (
                      <button
                        onClick={async () => {
                          await handleRetryLead(selectedLead.id);
                          setSelectedLead(null);
                        }}
                        className="flex items-center gap-1.5 px-4 py-2 bg-amber-700 text-white rounded-md hover:bg-amber-600 transition-colors"
                      >
                        <RefreshCw className="w-4 h-4" />
                        Retry Processing
                      </button>
                    )}
                    {selectedLead.status === 'PENDING_APPROVAL' && (
                      <button
                        onClick={approveEmail}
                        disabled={approvingEmail || revisingEmail}
                        className="px-4 py-2 bg-emerald-700 text-white rounded-md hover:bg-emerald-600 disabled:opacity-50"
                      >
                        {approvingEmail ? 'Queueing…' : `Approve Variation ${selectedVariation} & send`}
                      </button>
                    )}
                    {approvalMessage && <span className="text-sm text-gray-300">{approvalMessage}</span>}
                  </div>
                  <button
                    onClick={() => setSelectedLead(null)}
                    className="px-4 py-2 bg-gray-700 text-gray-200 rounded-md hover:bg-gray-600"
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          )}

          {/* Schedule Outreach Modal */}
          {scheduleModalOpen && (
            <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50 animate-in fade-in">
              <div className="bg-gray-800 rounded-lg max-w-md w-full mx-4 border border-gray-700 shadow-2xl overflow-hidden">
                <div className="px-6 py-4 border-b border-gray-700 flex items-center justify-between bg-gray-850">
                  <div className="flex items-center gap-2">
                    <Calendar className="w-5 h-5 text-purple-400" />
                    <h3 className="text-lg font-semibold text-white">Schedule Email Outreach</h3>
                  </div>
                  <button
                    onClick={() => setScheduleModalOpen(false)}
                    className="text-gray-400 hover:text-gray-300"
                  >
                    <XCircle className="w-5 h-5" />
                  </button>
                </div>

                <div className="px-6 py-5 space-y-4">
                  <p className="text-sm text-gray-300">
                    Choose delivery schedule for{' '}
                    <span className="font-semibold text-purple-300">
                      {scheduleTarget === 'selected'
                        ? `${selectedLeadIds.length} selected lead(s)`
                        : `all ${pendingCount} pending lead(s)`}
                    </span>
                    :
                  </p>

                  <div className="space-y-2">
                    <label
                      onClick={() => setSchedulePreset('1h')}
                      className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors ${
                        schedulePreset === '1h'
                          ? 'border-purple-500 bg-purple-950/40 text-purple-200'
                          : 'border-gray-700 bg-gray-900/50 text-gray-300 hover:bg-gray-700/50'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <Clock className="w-4 h-4 text-purple-400" />
                        <span className="text-sm font-medium">In 1 hour</span>
                      </div>
                      <input
                        type="radio"
                        name="schedulePreset"
                        checked={schedulePreset === '1h'}
                        onChange={() => setSchedulePreset('1h')}
                        className="text-purple-600 focus:ring-purple-500"
                      />
                    </label>

                    <label
                      onClick={() => setSchedulePreset('3h')}
                      className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors ${
                        schedulePreset === '3h'
                          ? 'border-purple-500 bg-purple-950/40 text-purple-200'
                          : 'border-gray-700 bg-gray-900/50 text-gray-300 hover:bg-gray-700/50'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <Clock className="w-4 h-4 text-purple-400" />
                        <span className="text-sm font-medium">In 3 hours</span>
                      </div>
                      <input
                        type="radio"
                        name="schedulePreset"
                        checked={schedulePreset === '3h'}
                        onChange={() => setSchedulePreset('3h')}
                        className="text-purple-600 focus:ring-purple-500"
                      />
                    </label>

                    <label
                      onClick={() => setSchedulePreset('tomorrow')}
                      className={`flex items-center justify-between p-3 rounded-lg border cursor-pointer transition-colors ${
                        schedulePreset === 'tomorrow'
                          ? 'border-purple-500 bg-purple-950/40 text-purple-200'
                          : 'border-gray-700 bg-gray-900/50 text-gray-300 hover:bg-gray-700/50'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <Calendar className="w-4 h-4 text-purple-400" />
                        <span className="text-sm font-medium">Tomorrow at 9:00 AM</span>
                      </div>
                      <input
                        type="radio"
                        name="schedulePreset"
                        checked={schedulePreset === 'tomorrow'}
                        onChange={() => setSchedulePreset('tomorrow')}
                        className="text-purple-600 focus:ring-purple-500"
                      />
                    </label>

                    <label
                      onClick={() => setSchedulePreset('custom')}
                      className={`flex flex-col p-3 rounded-lg border cursor-pointer transition-colors gap-2 ${
                        schedulePreset === 'custom'
                          ? 'border-purple-500 bg-purple-950/40 text-purple-200'
                          : 'border-gray-700 bg-gray-900/50 text-gray-300 hover:bg-gray-700/50'
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <Clock className="w-4 h-4 text-purple-400" />
                          <span className="text-sm font-medium">Custom Date & Time</span>
                        </div>
                        <input
                          type="radio"
                          name="schedulePreset"
                          checked={schedulePreset === 'custom'}
                          onChange={() => setSchedulePreset('custom')}
                          className="text-purple-600 focus:ring-purple-500"
                        />
                      </div>
                      {schedulePreset === 'custom' && (
                        <input
                          type="datetime-local"
                          value={customScheduleTime}
                          onChange={(e) => setCustomScheduleTime(e.target.value)}
                          className="mt-2 w-full px-3 py-2 bg-gray-900 border border-gray-600 rounded-md text-sm text-gray-100 focus:border-purple-400 focus:outline-none"
                        />
                      )}
                    </label>
                  </div>
                </div>

                <div className="px-6 py-4 border-t border-gray-700 bg-gray-900 flex items-center justify-end gap-3">
                  <button
                    onClick={() => setScheduleModalOpen(false)}
                    className="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-md transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleExecuteSchedule}
                    disabled={bulkActionLoading}
                    className="flex items-center gap-2 px-4 py-2 text-sm bg-purple-600 hover:bg-purple-500 text-white font-medium rounded-md shadow disabled:opacity-50 transition-colors"
                  >
                    <Calendar className="w-4 h-4" />
                    {bulkActionLoading ? 'Scheduling…' : 'Confirm & Schedule'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </main>
      </div>
    </>
  );
}

interface MetricCardProps {
  title: string;
  value: number;
  icon: React.ReactNode;
  color: string;
}

function MetricCard({ title, value, icon, color }: MetricCardProps) {
  return (
    <div className="bg-gray-800 rounded-lg shadow-xl border border-gray-700 p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-400 mb-1">{title}</p>
          <p className="text-2xl font-bold text-white">{value}</p>
        </div>
        <div className={`${color} text-white p-3 rounded-lg`}>
          {icon}
        </div>
      </div>
    </div>
  );
}
