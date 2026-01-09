import { useState, useEffect } from 'react';
import Head from 'next/head';
import axios from 'axios';
import { Play, Square, RefreshCw, Database, Mail, MessageSquare, CheckCircle, XCircle } from 'lucide-react';

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
  status: string;
  updated_at: string;
}

export default function Home() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(false);
  const [dryRun, setDryRun] = useState(true);
  const [enrichmentMode, setEnrichmentMode] = useState('offline');
  const [leadCount, setLeadCount] = useState(200);

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
      const response = await axios.get(`${API_BASE_URL}/leads?limit=50`);
      setLeads(response.data.leads);
    } catch (error) {
      console.error('Failed to fetch leads:', error);
    }
  };

  const runPipeline = async () => {
    setLoading(true);
    try {
      await axios.post(`${API_BASE_URL}/pipeline/run`, {
        dry_run: dryRun,
        enrichment_mode: enrichmentMode,
        lead_count: leadCount,
        channel: 'both'
      });
    } catch (error) {
      console.error('Failed to run pipeline:', error);
      alert('Failed to start pipeline');
    } finally {
      setLoading(false);
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

  useEffect(() => {
    fetchMetrics();
    fetchLeads();

    // Poll for updates
    const interval = setInterval(() => {
      fetchMetrics();
      if (metrics?.pipeline_running) {
        fetchLeads();
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [metrics?.pipeline_running]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'NEW': return 'bg-gray-100 text-gray-800';
      case 'ENRICHED': return 'bg-blue-100 text-blue-800';
      case 'MESSAGED': return 'bg-purple-100 text-purple-800';
      case 'SENT': return 'bg-green-100 text-green-800';
      case 'FAILED': return 'bg-red-100 text-red-800';
      default: return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <>
      <Head>
        <title>Lead Generation Pipeline - MCP Dashboard</title>
        <meta name="description" content="Monitor your lead generation pipeline" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
      </Head>

      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100">
        {/* Header */}
        <header className="bg-white shadow-sm border-b">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
            <div className="flex items-center justify-between">
              <div>
                <h1 className="text-2xl font-bold text-gray-900">Lead Generation Pipeline</h1>
                <p className="text-sm text-gray-500 mt-1">MCP-Powered Outreach System</p>
              </div>
              <div className="flex items-center gap-2">
                <Database className="w-5 h-5 text-gray-400" />
                <span className="text-sm text-gray-600">SQLite</span>
              </div>
            </div>
          </div>
        </header>

        <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {/* Controls */}
          <div className="bg-white rounded-lg shadow-md p-6 mb-8">
            <h2 className="text-lg font-semibold mb-4">Pipeline Controls</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Lead Count
                </label>
                <input
                  type="number"
                  value={leadCount}
                  onChange={(e) => setLeadCount(Number(e.target.value))}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                  min="1"
                  max="1000"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Enrichment Mode
                </label>
                <select
                  value={enrichmentMode}
                  onChange={(e) => setEnrichmentMode(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-md"
                >
                  <option value="offline">Offline (Rule-based)</option>
                  <option value="ai">AI (Groq LLM)</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Run Mode
                </label>
                <div className="flex items-center gap-4">
                  <label className="flex items-center">
                    <input
                      type="radio"
                      checked={dryRun}
                      onChange={() => setDryRun(true)}
                      className="mr-2"
                    />
                    <span className="text-sm">Dry Run</span>
                  </label>
                  <label className="flex items-center">
                    <input
                      type="radio"
                      checked={!dryRun}
                      onChange={() => setDryRun(false)}
                      className="mr-2"
                    />
                    <span className="text-sm">Live Run</span>
                  </label>
                </div>
              </div>
            </div>

            <div className="flex gap-3">
              <button
                onClick={runPipeline}
                disabled={loading || metrics?.pipeline_running}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                {metrics?.pipeline_running ? (
                  <>
                    <RefreshCw className="w-4 h-4 animate-spin" />
                    Running...
                  </>
                ) : (
                  <>
                    <Play className="w-4 h-4" />
                    Run Pipeline
                  </>
                )}
              </button>

              <button
                onClick={clearData}
                disabled={metrics?.pipeline_running}
                className="flex items-center gap-2 px-4 py-2 bg-red-600 text-white rounded-md hover:bg-red-700 disabled:bg-gray-400 disabled:cursor-not-allowed"
              >
                <XCircle className="w-4 h-4" />
                Clear Data
              </button>
            </div>

            {metrics?.pipeline_running && (
              <div className="mt-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-gray-700">
                    {metrics.current_stage}
                  </span>
                  <span className="text-sm text-gray-600">{metrics.progress}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full transition-all duration-300"
                    style={{ width: `${metrics.progress}%` }}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Metrics Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4 mb-8">
            <MetricCard
              title="Total Leads"
              value={metrics?.total_leads || 0}
              icon={<Database className="w-6 h-6" />}
              color="bg-blue-500"
            />
            <MetricCard
              title="Enriched"
              value={metrics?.leads_enriched || 0}
              icon={<CheckCircle className="w-6 h-6" />}
              color="bg-purple-500"
            />
            <MetricCard
              title="Messages Generated"
              value={metrics?.messages_generated || 0}
              icon={<MessageSquare className="w-6 h-6" />}
              color="bg-indigo-500"
            />
            <MetricCard
              title="Messages Sent"
              value={metrics?.messages_sent || 0}
              icon={<Mail className="w-6 h-6" />}
              color="bg-green-500"
            />
            <MetricCard
              title="Failed"
              value={metrics?.messages_failed || 0}
              icon={<XCircle className="w-6 h-6" />}
              color="bg-red-500"
            />
          </div>

          {/* Leads Table */}
          <div className="bg-white rounded-lg shadow-md overflow-hidden">
            <div className="px-6 py-4 border-b border-gray-200">
              <h2 className="text-lg font-semibold">Recent Leads</h2>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Name
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Company
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Role
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Industry
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Status
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {leads.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-4 text-center text-gray-500">
                        No leads yet. Run the pipeline to generate leads.
                      </td>
                    </tr>
                  ) : (
                    leads.map((lead) => (
                      <tr key={lead.id} className="hover:bg-gray-50">
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {lead.full_name}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {lead.company_name}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {lead.role_title}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {lead.industry}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <span className={`px-2 py-1 inline-flex text-xs leading-5 font-semibold rounded-full ${getStatusColor(lead.status)}`}>
                            {lead.status}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          </div>
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
    <div className="bg-white rounded-lg shadow-md p-6">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-gray-600 mb-1">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
        </div>
        <div className={`${color} text-white p-3 rounded-lg`}>
          {icon}
        </div>
      </div>
    </div>
  );
}
