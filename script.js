// Configuration
const DATA_URL = 'data/dashboard-data.json';
const STALENESS_THRESHOLD_DAYS = 45;

// Utility: Format date as relative time
function timeAgo(isoDateString) {
    if (!isoDateString) return 'Never';
    
    const date = new Date(isoDateString);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    if (diffDays === 0) return 'Today';
    if (diffDays === 1) return '1 day ago';
    if (diffDays < 30) return diffDays + ' days ago';
    
    const diffMonths = Math.floor(diffDays / 30);
    if (diffMonths === 1) return '1 month ago';
    if (diffMonths < 12) return diffMonths + ' months ago';
    
    const diffYears = Math.floor(diffDays / 365);
    if (diffYears === 1) return '1 year ago';
    return diffYears + ' years ago';
}

// Utility: Format date as human-readable
function formatDate(isoDateString) {
    if (!isoDateString) return 'Never';
    
    const date = new Date(isoDateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

// Create HTML for a single ingest card
function createIngestCard(ingest) {
    const card = document.createElement('div');
    card.className = 'ingest-card ' + ingest.status;
    
    // Status badge
    const badge = document.createElement('div');
    badge.className = 'status-badge ' + ingest.status;
    badge.title = ingest.status.charAt(0).toUpperCase() + ingest.status.slice(1);
    
    // Ingest name (linked to repo)
    const name = document.createElement('div');
    name.className = 'ingest-name';
    const nameLink = document.createElement('a');
    nameLink.href = ingest.repo_url;
    nameLink.target = '_blank';
    nameLink.textContent = ingest.name;
    name.appendChild(nameLink);

    // Add Koza 2 badge if applicable
    if (ingest.koza_version === '2') {
        const versionBadge = document.createElement('span');
        versionBadge.className = 'version-badge';
        versionBadge.textContent = 'koza 2';
        name.appendChild(versionBadge);
    }

    // Details container
    const details = document.createElement('div');
    details.className = 'ingest-details';
    
    // Release info
    const releaseRow = document.createElement('div');
    releaseRow.className = 'detail-row';
    
    const releaseLabel = document.createElement('div');
    releaseLabel.className = 'detail-label';
    releaseLabel.textContent = 'Latest Release';
    
    const releaseValue = document.createElement('div');
    releaseValue.className = 'detail-value';
    
    if (ingest.last_release) {
        const releaseLink = document.createElement('a');
        releaseLink.href = ingest.last_release.url;
        releaseLink.target = '_blank';
        releaseLink.textContent = ingest.last_release.tag;
        releaseValue.appendChild(releaseLink);
        
        const releaseTime = document.createElement('span');
        releaseTime.className = 'time-ago';
        releaseTime.textContent = timeAgo(ingest.last_release.date);
        releaseValue.appendChild(releaseTime);
    } else {
        const noRelease = document.createElement('span');
        noRelease.style.color = 'var(--text-secondary)';
        noRelease.textContent = 'No releases';
        releaseValue.appendChild(noRelease);
    }
    
    releaseRow.appendChild(releaseLabel);
    releaseRow.appendChild(releaseValue);
    
    // Workflow info
    const workflowRow = document.createElement('div');
    workflowRow.className = 'detail-row';
    
    const workflowLabel = document.createElement('div');
    workflowLabel.className = 'detail-label';
    workflowLabel.textContent = 'Last Workflow Run';
    
    const workflowValue = document.createElement('div');
    workflowValue.className = 'detail-value';
    
    if (ingest.last_workflow_run) {
        const workflowLink = document.createElement('a');
        workflowLink.href = ingest.last_workflow_run.url;
        workflowLink.target = '_blank';
        workflowLink.textContent = 'View run';
        workflowValue.appendChild(workflowLink);
        
        const conclusion = ingest.last_workflow_run.conclusion || 'unknown';
        const conclusionBadge = document.createElement('span');
        conclusionBadge.className = 'conclusion-badge ' + conclusion;
        conclusionBadge.textContent = conclusion;
        workflowValue.appendChild(conclusionBadge);
        
        const workflowTime = document.createElement('span');
        workflowTime.className = 'time-ago';
        workflowTime.textContent = timeAgo(ingest.last_workflow_run.date);
        workflowValue.appendChild(workflowTime);
    } else {
        const noWorkflow = document.createElement('span');
        noWorkflow.style.color = 'var(--text-secondary)';
        noWorkflow.textContent = 'No workflow runs';
        workflowValue.appendChild(noWorkflow);
    }
    
    workflowRow.appendChild(workflowLabel);
    workflowRow.appendChild(workflowValue);
    
    // Assemble card
    details.appendChild(releaseRow);
    details.appendChild(workflowRow);
    
    card.appendChild(badge);
    card.appendChild(name);
    card.appendChild(details);
    
    return card;
}

// Render the dashboard
function renderDashboard(data) {
    // Update last updated timestamp
    const lastUpdatedEl = document.getElementById('last-updated');
    lastUpdatedEl.textContent = 'Last updated: ' + formatDate(data.last_updated) + ' (' + timeAgo(data.last_updated) + ')';
    
    // Calculate summary stats
    const healthy = data.ingests.filter(function(i) { return i.status === 'healthy'; }).length;
    const stale = data.ingests.filter(function(i) { return i.status === 'stale'; }).length;
    const failed = data.ingests.filter(function(i) { return i.status === 'failed'; }).length;
    
    const summaryEl = document.getElementById('summary');
    summaryEl.innerHTML = '<span class="healthy">' + healthy + ' healthy</span>' +
                          '<span class="stale">' + stale + ' stale</span>' +
                          '<span class="failed">' + failed + ' failed</span>';
    
    // Render ingest cards
    const dashboardEl = document.getElementById('dashboard');
    dashboardEl.innerHTML = ''; // Clear loading message
    
    // Sort: failed first, then stale, then healthy, then alphabetically within each group
    const statusOrder = { 'failed': 0, 'stale': 1, 'healthy': 2 };
    const sortedIngests = data.ingests.sort(function(a, b) {
        if (statusOrder[a.status] !== statusOrder[b.status]) {
            return statusOrder[a.status] - statusOrder[b.status];
        }
        return a.name.localeCompare(b.name);
    });
    
    sortedIngests.forEach(function(ingest) {
        const card = createIngestCard(ingest);
        dashboardEl.appendChild(card);
    });
}

// Load and render dashboard data
function loadDashboard() {
    fetch(DATA_URL)
        .then(function(response) {
            if (!response.ok) {
                throw new Error('HTTP error! status: ' + response.status);
            }
            return response.json();
        })
        .then(function(data) {
            renderDashboard(data);
        })
        .catch(function(error) {
            console.error('Error loading dashboard data:', error);
            const dashboardEl = document.getElementById('dashboard');
            dashboardEl.innerHTML = '<div class="loading">Error loading dashboard data. Please try refreshing the page.</div>';
        });
}

// Initialize dashboard when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', loadDashboard);
} else {
    loadDashboard();
}
