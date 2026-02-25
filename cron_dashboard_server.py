#!/usr/bin/env python3
"""
Cron Dashboard API Server
Serves the dashboard and fetches cron data via OpenClaw CLI
"""

import json
import os
import http.server
import socketserver
import subprocess
import threading
from pathlib import Path

PORT = 9000
LOCK = threading.Lock()

# Dashboard HTML with API integration
DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Cron Job Dashboard - CDP Project</title>
    <style>
        :root {
            --bg-primary: #0f172a;
            --bg-secondary: #1e293b;
            --bg-card: #334155;
            --text-primary: #f8fafc;
            --text-secondary: #94a3b8;
            --accent-green: #22c55e;
            --accent-red: #ef4444;
            --accent-yellow: #eab308;
            --accent-blue: #3b82f6;
            --border: #475569;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            padding: 20px;
        }
        
        .header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 30px;
            padding-bottom: 20px;
            border-bottom: 1px solid var(--border);
        }
        
        .header h1 { font-size: 1.8rem; }
        .header .refresh-btn {
            background: var(--accent-blue);
            color: white;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-size: 14px;
        }
        
        .stats {
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 20px;
            margin-bottom: 30px;
        }
        
        .stat-card {
            background: var(--bg-secondary);
            padding: 20px;
            border-radius: 12px;
            text-align: center;
        }
        
        .stat-card .number {
            font-size: 2.5rem;
            font-weight: bold;
        }
        
        .stat-card .label {
            color: var(--text-secondary);
            font-size: 14px;
            margin-top: 5px;
        }
        
        .stat-card.total .number { color: var(--accent-blue); }
        .stat-card.ok .number { color: var(--accent-green); }
        .stat-card.error .number { color: var(--accent-red); }
        .stat-card.disabled .number { color: var(--accent-yellow); }
        
        .filters {
            display: flex;
            gap: 10px;
            margin-bottom: 20px;
            flex-wrap: wrap;
        }
        
        .filter-btn {
            background: var(--bg-secondary);
            color: var(--text-secondary);
            border: 1px solid var(--border);
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
        }
        
        .filter-btn.active {
            background: var(--accent-blue);
            color: white;
            border-color: var(--accent-blue);
        }
        
        .jobs-grid {
            display: grid;
            gap: 12px;
        }
        
        .job-card {
            background: var(--bg-secondary);
            border-radius: 10px;
            padding: 16px 20px;
            display: grid;
            grid-template-columns: 80px 1fr 150px 120px 100px;
            align-items: center;
            gap: 15px;
            border: 1px solid transparent;
        }
        
        .job-card:hover {
            border-color: var(--border);
        }
        
        .job-card.error {
            border-left: 4px solid var(--accent-red);
        }
        
        .job-card.ok {
            border-left: 4px solid var(--accent-green);
        }
        
        .status-badge {
            padding: 4px 10px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 600;
            text-align: center;
        }
        
        .status-badge.ok { background: #166534; color: #86efac; }
        .status-badge.error { background: #991b1b; color: #fca5a5; }
        
        .job-name {
            font-weight: 500;
            font-size: 14px;
        }
        
        .job-schedule {
            color: var(--text-secondary);
            font-size: 13px;
        }
        
        .job-next {
            color: var(--text-secondary);
            font-size: 12px;
        }
        
        .job-last {
            font-size: 12px;
        }
        
        .job-last.error { color: var(--accent-red); }
        .job-last.ok { color: var(--accent-green); }
        
        .category-title {
            font-size: 14px;
            color: var(--text-secondary);
            margin: 20px 0 10px 0;
            padding-bottom: 5px;
            border-bottom: 1px solid var(--border);
        }
        
        .loading {
            text-align: center;
            padding: 40px;
            color: var(--text-secondary);
        }
        
        .error-msg {
            background: #991b1b;
            color: #fca5a5;
            padding: 20px;
            border-radius: 8px;
            text-align: center;
        }
        
        @media (max-width: 900px) {
            .stats { grid-template-columns: repeat(2, 1fr); }
            .job-card { grid-template-columns: 1fr; gap: 8px; }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 Cron Job Monitor</h1>
        <button class="refresh-btn" onclick="loadJobs()">🔄 重新整理</button>
    </div>
    
    <div class="stats">
        <div class="stat-card total">
            <div class="number" id="totalJobs">-</div>
            <div class="label">總工作數</div>
        </div>
        <div class="stat-card ok">
            <div class="number" id="okJobs">-</div>
            <div class="label">運行正常</div>
        </div>
        <div class="stat-card error">
            <div class="number" id="errorJobs">-</div>
            <div class="label">錯誤</div>
        </div>
        <div class="stat-card disabled">
            <div class="number" id="disabledJobs">-</div>
            <div class="label">已停用</div>
        </div>
    </div>
    
    <div class="filters">
        <button class="filter-btn active" onclick="filterJobs('all')">全部</button>
        <button class="filter-btn" onclick="filterJobs('ok')">正常</button>
        <button class="filter-btn" onclick="filterJobs('error')">錯誤</button>
        <button class="filter-btn" onclick="filterJobs('CDP')">CDP專案</button>
        <button class="filter-btn" onclick="filterJobs('Digital Twin')">數位孿生</button>
        <button class="filter-btn" onclick="filterJobs('Competitor')">競爭分析</button>
    </div>
    
    <div id="jobsContainer">
        <div class="loading">載入中...</div>
    </div>
    
    <script>
        let allJobs = [];
        
        function formatTime(ms) {
            if (!ms) return '-';
            const date = new Date(ms);
            const now = new Date();
            const diff = date - now;
            
            if (diff < 0) return '已過期';
            
            const hours = Math.floor(diff / (1000 * 60 * 60));
            const minutes = Math.floor((diff % (1000 * 60 * 60)) / (1000 * 60));
            
            if (hours > 24) {
                return date.toLocaleDateString('zh-TW', { month: 'short', day: 'numeric' });
            }
            return `${hours}小時${minutes}分`;
        }
        
        function formatDuration(ms) {
            if (!ms) return '-';
            if (ms < 1000) return `${ms}ms`;
            return `${(ms/1000).toFixed(1)}秒`;
        }
        
        function renderJobs(jobs) {
            const container = document.getElementById('jobsContainer');
            
            if (!jobs || jobs.length === 0) {
                container.innerHTML = '<div class="error-msg">無工作資料</div>';
                return;
            }
            
            // Group by category
            const categories = {
                'CDP & 監控': jobs.filter(j => 
                    j.name.includes('CDP') || j.name.includes('Crypto') || j.name.includes('Job')
                ),
                '數位孿生': jobs.filter(j => 
                    j.name.includes('Digital Twin') || j.name.includes('Intelligence') || j.name.includes('Sandbox')
                ),
                '競爭分析': jobs.filter(j => j.name.includes('Competitor')),
                '提醒': jobs.filter(j => j.name.includes('Reminder') || j.name.includes('提醒')),
                '其他': jobs.filter(j => 
                    !j.name.includes('CDP') && !j.name.includes('Crypto') && 
                    !j.name.includes('Job') && !j.name.includes('Digital Twin') &&
                    !j.name.includes('Intelligence') && !j.name.includes('Sandbox') &&
                    !j.name.includes('Competitor') && !j.name.includes('Reminder') &&
                    !j.name.includes('提醒')
                )
            };
            
            let html = '';
            
            for (const [category, items] of Object.entries(categories)) {
                if (items.length === 0) continue;
                
                html += `<div class="category-title">${category} (${items.length})</div>`;
                
                for (const job of items) {
                    const statusClass = job.state?.lastStatus || 'unknown';
                    const statusText = statusClass === 'ok' ? '正常' : statusClass === 'error' ? '錯誤' : '未知';
                    
                    html += `
                        <div class="job-card ${statusClass}" data-category="${category}">
                            <div class="status-badge ${statusClass}">${statusText}</div>
                            <div>
                                <div class="job-name">${job.name}</div>
                                <div class="job-schedule">${job.schedule?.expr || '-'} (${job.schedule?.tz || 'UTC'})</div>
                            </div>
                            <div class="job-next">下次: ${formatTime(job.state?.nextRunAtMs)}</div>
                            <div class="job-last ${statusClass}">運行: ${formatDuration(job.state?.lastDurationMs)}</div>
                            <div>${job.enabled ? '✅' : '❌'}</div>
                        </div>
                    `;
                }
            }
            
            container.innerHTML = html;
        }
        
        function filterJobs(filter) {
            document.querySelectorAll('.filter-btn').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
            
            let filtered = allJobs;
            
            if (filter === 'ok') {
                filtered = allJobs.filter(j => j.state?.lastStatus === 'ok');
            } else if (filter === 'error') {
                filtered = allJobs.filter(j => j.state?.lastStatus === 'error');
            } else if (filter === 'CDP') {
                filtered = allJobs.filter(j => j.name.includes('CDP') || j.name.includes('Crypto') || j.name.includes('Job'));
            } else if (filter === 'Digital Twin') {
                filtered = allJobs.filter(j => j.name.includes('Digital Twin') || j.name.includes('Intelligence') || j.name.includes('Sandbox'));
            } else if (filter === 'Competitor') {
                filtered = allJobs.filter(j => j.name.includes('Competitor'));
            }
            
            renderJobs(filtered);
        }
        
        function updateStats(jobs) {
            document.getElementById('totalJobs').textContent = jobs.length;
            document.getElementById('okJobs').textContent = jobs.filter(j => j.state?.lastStatus === 'ok').length;
            document.getElementById('errorJobs').textContent = jobs.filter(j => j.state?.lastStatus === 'error').length;
            document.getElementById('disabledJobs').textContent = jobs.filter(j => !j.enabled).length;
        }
        
        async function loadJobs() {
            const container = document.getElementById('jobsContainer');
            container.innerHTML = '<div class="loading">載入中...</div>';
            
            try {
                const response = await fetch('/api/cron');
                if (!response.ok) throw new Error('API error');
                const data = await response.json();
                allJobs = data.jobs || [];
                updateStats(allJobs);
                renderJobs(allJobs);
            } catch (e) {
                console.error('Failed to load jobs:', e);
                container.innerHTML = '<div class="error-msg">載入失敗，請確認本地伺服器運行中<br>' + e.message + '</div>';
            }
        }
        
        loadJobs();
        setInterval(loadJobs, 30000);
    </script>
</body>
</html>
'''

# Cache for cron data (refresh every 30 seconds)
_cron_cache = {"jobs": [], "timestamp": 0}
CACHE_TTL = 30  # seconds

def fetch_cron_jobs():
    global _cron_cache
    import time
    
    current_time = time.time()
    
    # Return cached data if still valid
    if current_time - _cron_cache["timestamp"] < CACHE_TTL:
        return _cron_cache
    
    try:
        # Use openclaw CLI to get cron jobs
        result = subprocess.run(
            ["openclaw", "cron", "list", "--json"],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        if result.returncode == 0:
            data = json.loads(result.stdout)
            _cron_cache = {"jobs": data.get("jobs", []), "timestamp": current_time}
        else:
            print(f"Error fetching cron jobs: {result.stderr}")
    except Exception as e:
        print(f"Exception fetching cron jobs: {e}")
    
    return _cron_cache

class DashboardHandler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/api/cron':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            
            data = fetch_cron_jobs()
            self.wfile.write(json.dumps(data).encode())
        elif self.path == '/' or self.path == '/index.html' or self.path == '/dashboard':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            self.wfile.write(DASHBOARD_HTML.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def log_message(self, format, *args):
        print(f"[{self.log_date_time_string()}] {format % args}")

print(f"Starting Cron Dashboard Server on port {PORT}")
print(f"Dashboard: http://localhost:{PORT}/dashboard")
print(f"Use Ctrl+C to stop")

with socketserver.TCPServer(("0.0.0.0", PORT), DashboardHandler) as httpd:
    httpd.serve_forever()
