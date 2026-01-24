import { useState, useEffect } from 'react';
import Head from 'next/head';
import axios from 'axios';
import { RefreshCw, Database, Mail, MessageSquare, CheckCircle, XCircle, Eye, Filter, Users, TrendingUp } from 'lucide-react';

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

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
    message?: string;
  };
}

export default function Home() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [selectedLeadMessages, setSelectedLeadMessages] = useState<LeadMessages | null>(null);
  const [loadingMessages, setLoadingMessages] = useState(false);
  const [filterSource, setFilterSource] = useState<string>('all');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [autoRefresh, setAutoRefresh] = useState(true);

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
      setLeads(response.data.leads);
    } catch (error) {
      console.error('Failed to fetch leads:', error);
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
    await fetchLeadMessages(lead.id);
  };

  const filteredLeads = leads.filter(lead => {
    if (filterSource !== 'all' && lead.source !== filterSource) return false;
    if (filterStatus !== 'all' && lead.status !== filterStatus) return false;
    return true;
  });

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
              <div className="flex items-center gap-4">
                <button
                  onClick={() => setAutoRefresh(!autoRefresh)}
                  className={`flex items-center gap-2 px-3 py-2 text-sm rounded-md ${
                    autoRefresh 
                      ? 'bg-green-900 hover:bg-green-800 text-green-200' 
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
                  onClick={fetchLeads}
                  className="flex items-center gap-2 px-3 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-gray-200 rounded-md"
                >
                  <RefreshCw className="w-4 h-4" />
                  Refresh Now
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
          
          {/* Pipeline Status */}
          {metrics?.pipeline_running && (
            <div className="bg-blue-900/30 border border-blue-700 rounded-lg p-4 mb-6">
              <div className="flex items-center justify-between mb-2">
                <div className="flex items-center gap-2">
                  <RefreshCw className="w-4 h-4 animate-spin text-blue-400" />
                  <span className="text-sm font-medium text-blue-200">
                    Processing: {metrics.current_stage}
                  </span>
                </div>
                <span className="text-sm text-blue-300">{metrics.progress}%</span>
              </div>
              <div className="w-full bg-blue-950 rounded-full h-2">
                <div
                  className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${metrics.progress}%` }}
                />
              </div>
            </div>
          )}

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
                  <option value="facebook_leads">Facebook Lead Ads</option>
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
                  <option value="new">New</option>
                  <option value="enriched">Enriched</option>
                  <option value="messaged">Messaged</option>
                  <option value="sent">Sent</option>
                </select>
              </div>
            </div>
          </div>

          {/* Metrics Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
            <MetricCard
              title="Total Leads"
              value={filteredLeads.length}
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
              value={leads.filter(l => l.status === 'messaged' || l.status === 'sent').length}
              icon={<MessageSquare className="w-6 h-6" />}
              color="bg-purple-500"
            />
            <MetricCard
              title="Sent"
              value={leads.filter(l => l.status === 'sent').length}
              icon={<Mail className="w-6 h-6" />}
              color="bg-green-500"
            />
          </div>

          {/* Leads Table */}
          <div className="bg-gray-800 rounded-lg shadow-xl border border-gray-700 overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-700 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-white">Leads ({filteredLeads.length})</h2>
              <div className="text-sm text-gray-400">
                {autoRefresh ? 'Auto-refresh every 10 seconds' : 'Auto-refresh paused'}
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-700">
                <thead className="bg-gray-900">
                  <tr>
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
                      <td colSpan={6} className="px-6 py-4 text-center text-gray-400">
                        {filterSource !== 'all' || filterStatus !== 'all' 
                          ? 'No leads match the selected filters.'
                          : 'No leads yet. Leads will appear here automatically when they arrive from Facebook or Google Sheets.'}
                      </td>
                    </tr>
                  ) : (
                    filteredLeads.map((lead) => (
                      <tr key={lead.id} className="hover:bg-gray-700">
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
                          <button
                            onClick={() => handleViewLead(lead)}
                            className="text-blue-400 hover:text-blue-300 flex items-center gap-1"
                          >
                            <Eye className="w-4 h-4" />
                            View
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>

          {/* Lead Details Modal */}
          {selectedLead && (
            <div className="fixed inset-0 bg-black bg-opacity-75 flex items-center justify-center z-50">
              <div className="bg-gray-800 rounded-lg max-w-3xl w-full mx-4 max-h-[90vh] overflow-y-auto border border-gray-700">
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
                                    <div className="bg-purple-900/30 px-3 py-2 rounded-t-md">
                                      <p className="text-xs font-medium text-purple-300">Variation {variation}</p>
                                    </div>
                                    <div className="bg-gray-900 p-3 rounded-b-md">
                                      <p className="text-xs text-gray-400 mb-1">Subject:</p>
                                      <p className="text-sm font-medium text-gray-100 mb-3">{value.subject}</p>
                                      <p className="text-xs text-gray-400 mb-1">Body:</p>
                                      <p className="text-sm text-gray-300 whitespace-pre-wrap">{value.body}</p>
                                    </div>
                                  </div>
                                );
                              })}
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

                <div className="px-6 py-4 border-t border-gray-700 bg-gray-900 flex justify-end">
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
