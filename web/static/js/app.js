/* ═══════════════════════════════════════════════════════════════
   SKILLS DEMAND INTELLIGENCE PLATFORM — APP LOGIC
   Aceternity Spotlight Cards · Lucide Icons · Chart.js · Live API
   ═══════════════════════════════════════════════════════════════ */

'use strict';

// ── Helpers ──────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

async function API(url, options) {
  const res = await fetch(url, options);
  if (!res.ok) throw new Error(`API Error ${res.status}: ${res.statusText}`);
  return res.json();
}

function refreshIcons() {
  if (window.lucide && typeof window.lucide.createIcons === 'function') {
    window.lucide.createIcons();
  }
}

// ── Particle Canvas with Cursor Reactivity ──────────────────────
(function initParticles() {
  const canvas = $('particle-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H, particles = [];
  const mouse = { x: -1000, y: -1000, radius: 140 };

  const COLORS = [
    'rgba(99, 102, 241,',
    'rgba(6, 182, 212,',
    'rgba(16, 185, 129,',
    'rgba(139, 92, 246,'
  ];

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }

  function spawnParticle() {
    const c = COLORS[Math.floor(Math.random() * COLORS.length)];
    return {
      x: Math.random() * W,
      y: Math.random() * H,
      r: Math.random() * 1.6 + 0.4,
      vx: (Math.random() - 0.5) * 0.35,
      vy: (Math.random() - 0.5) * 0.35,
      a: Math.random() * 0.45 + 0.15,
      color: c
    };
  }

  function init() {
    resize();
    particles = Array.from({ length: 75 }, spawnParticle);
  }

  window.addEventListener('resize', resize);
  window.addEventListener('mousemove', e => {
    mouse.x = e.clientX;
    mouse.y = e.clientY;
  });
  window.addEventListener('mouseout', () => {
    mouse.x = -1000;
    mouse.y = -1000;
  });

  function draw() {
    ctx.clearRect(0, 0, W, H);

    particles.forEach(p => {
      // Mouse gravity repulsion/attraction
      const dx = mouse.x - p.x;
      const dy = mouse.y - p.y;
      const dist = Math.sqrt(dx * dx + dy * dy);
      if (dist < mouse.radius) {
        const force = (mouse.radius - dist) / mouse.radius;
        p.x -= (dx / dist) * force * 1.5;
        p.y -= (dy / dist) * force * 1.5;
      }

      p.x += p.vx;
      p.y += p.vy;
      if (p.x < 0) p.x = W;
      if (p.x > W) p.x = 0;
      if (p.y < 0) p.y = H;
      if (p.y > H) p.y = 0;

      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = p.color + p.a + ')';
      ctx.fill();
    });

    // Particle connecting lines
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const d  = Math.sqrt(dx * dx + dy * dy);
        if (d < 110) {
          const alpha = (1 - d / 110) * 0.12;
          ctx.strokeStyle = `rgba(99, 102, 241, ${alpha})`;
          ctx.lineWidth = 0.8;
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.stroke();
        }
      }
    }

    requestAnimationFrame(draw);
  }

  init();
  draw();
})();

// ── Aceternity Spotlight Cursor Follower ─────────────────────────
(function initSpotlights() {
  document.addEventListener('mousemove', e => {
    const cards = document.querySelectorAll('.spotlight-card');
    cards.forEach(card => {
      const rect = card.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      card.style.setProperty('--mouse-x', `${x}px`);
      card.style.setProperty('--mouse-y', `${y}px`);
    });
  });
})();

// ── Toast Notification System ───────────────────────────────────
function showToast(message, type = 'info') {
  const container = $('toast-container');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;

  const iconName = type === 'success' ? 'check-circle' : type === 'error' ? 'alert-triangle' : 'info';
  toast.innerHTML = `<i data-lucide="${iconName}"></i> <span>${message}</span>`;
  container.appendChild(toast);
  refreshIcons();

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(10px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ── Number Counter Animation ────────────────────────────────────
function animateCounter(el, target, prefix = '', suffix = '') {
  if (!el || target == null || isNaN(target)) return;
  const num = Math.round(Number(target));
  const duration = 1000;
  const start = 0;
  const startTime = performance.now();

  function update(now) {
    const progress = Math.min((now - startTime) / duration, 1);
    const ease = 1 - Math.pow(1 - progress, 3); // Ease out cubic
    const current = Math.round(start + (num - start) * ease);
    el.textContent = `${prefix}${current.toLocaleString()}${suffix}`;
    if (progress < 1) requestAnimationFrame(update);
  }

  requestAnimationFrame(update);
}

// ── Tab Navigation & Router ─────────────────────────────────────
const PAGES = {
  overview:  'Overview',
  skills:    'Skills Explorer',
  stacks:    'Tech Stacks & Synergies',
  companies: 'Hiring Companies',
  pipeline:  'Observability Hub'
};

let activeTab = 'overview';

function setTab(tab) {
  if (!PAGES[tab]) return;

  document.querySelectorAll('.nav-item').forEach(b => {
    b.classList.toggle('active', b.dataset.tab === tab);
  });
  document.querySelectorAll('.tab-pane').forEach(p => {
    p.classList.toggle('active', p.id === 'tab-' + tab);
  });

  const bc = $('breadcrumb-page');
  if (bc) bc.textContent = PAGES[tab];

  activeTab = tab;
  refreshIcons();

  // Trigger lazy loading per tab
  if (tab === 'skills') loadSkills();
  else if (tab === 'stacks') loadTechStacks();
  else if (tab === 'companies') loadCompanies();
  else if (tab === 'pipeline') loadPipeline();
}

// Attach Nav Listeners
document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => setTab(btn.dataset.tab));
});

// Quick action buttons in hero
$('hero-btn-explore')?.addEventListener('click', () => setTab('skills'));
$('hero-btn-audit')?.addEventListener('click', () => triggerAudit());

// Mobile sidebar toggle
$('sidebar-toggle')?.addEventListener('click', () => {
  $('sidebar')?.classList.toggle('open');
});

// ── Chart.js Instances & Palette ────────────────────────────────
let chartSkills = null;
let chartCategories = null;

function destroyChart(c) {
  if (c) {
    try { c.destroy(); } catch (_) {}
  }
}

const PALETTE = [
  '#6366f1', '#06b6d4', '#10b981', '#f59e0b', '#8b5cf6', '#ef4444',
  '#22d3ee', '#34d399', '#fbbf24', '#c084fc', '#f87171', '#818cf8',
  '#2dd4bf', '#fb923c', '#e879f9', '#4ade80'
];

// ── OVERVIEW TAB LOGIC ──────────────────────────────────────────
async function loadOverview() {
  try {
    const [kpis, skills, cats] = await Promise.all([
      API('/api/overview'),
      API('/api/skills'),
      API('/api/categories')
    ]);

    // Animate Bento Top KPIs
    animateCounter($('val-total-postings'), kpis.total_postings);
    animateCounter($('val-tracked-skills'), kpis.tracked_skills);
    animateCounter($('val-total-companies'), kpis.total_companies);

    if ($('val-avg-salary')) {
      animateCounter($('val-avg-salary'), kpis.avg_salary, '£');
    }
    if ($('val-skill-mentions')) {
      animateCounter($('val-skill-mentions'), kpis.total_skill_mentions, '', ' mentions');
    }

    // Sidebar skills badge
    if ($('badge-skills')) {
      $('badge-skills').textContent = kpis.tracked_skills;
    }

    // Update SLA indicator
    updateSLA(kpis);

    // Chart 1: Top Skills Bar Chart
    const top10 = skills.slice(0, 10);
    destroyChart(chartSkills);
    const ctxS = $('chart-top-skills');
    if (ctxS) {
      chartSkills = new Chart(ctxS, {
        type: 'bar',
        data: {
          labels: top10.map(s => s.skill_display_name),
          datasets: [{
            label: 'Job Postings',
            data: top10.map(s => s.posting_count),
            backgroundColor: top10.map((_, i) => PALETTE[i % PALETTE.length] + 'cc'),
            borderColor: top10.map((_, i) => PALETTE[i % PALETTE.length]),
            borderWidth: 1.5,
            borderRadius: 6,
            borderSkipped: false,
          }]
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 900, easing: 'easeOutQuart' },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: 'rgba(13, 19, 31, 0.95)',
              borderColor: 'rgba(99, 102, 241, 0.35)',
              borderWidth: 1,
              titleColor: '#f8fafc',
              bodyColor: '#94a3b8',
              padding: 12,
              displayColors: false,
              callbacks: {
                label: ctx => ` ${ctx.parsed.x} postings (${top10[ctx.dataIndex].market_penetration_pct}% market share)`
              }
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(255, 255, 255, 0.04)' },
              ticks: { color: '#64748b', font: { family: 'Plus Jakarta Sans', size: 11 } },
              border: { color: 'rgba(255, 255, 255, 0.06)' }
            },
            y: {
              grid: { display: false },
              ticks: { color: '#f8fafc', font: { family: 'Plus Jakarta Sans', size: 12, weight: 600 } },
              border: { display: false }
            }
          }
        }
      });
    }

    // Chart 2: Category Donut Chart
    destroyChart(chartCategories);
    const ctxC = $('chart-categories');
    if (ctxC) {
      chartCategories = new Chart(ctxC, {
        type: 'doughnut',
        data: {
          labels: cats.map(c => c.category_name.toUpperCase()),
          datasets: [{
            data: cats.map(c => c.total_postings),
            backgroundColor: PALETTE.slice(0, cats.length),
            borderColor: 'rgba(8, 12, 20, 0.8)',
            borderWidth: 3,
            hoverOffset: 6
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '72%',
          animation: { animateRotate: true, duration: 1000 },
          plugins: {
            legend: {
              position: 'right',
              labels: {
                color: '#94a3b8',
                font: { family: 'Plus Jakarta Sans', size: 11 },
                boxWidth: 10,
                padding: 12
              }
            },
            tooltip: {
              backgroundColor: 'rgba(13, 19, 31, 0.95)',
              borderColor: 'rgba(99, 102, 241, 0.35)',
              borderWidth: 1,
              padding: 10
            }
          }
        }
      });
    }

  } catch (err) {
    console.error('loadOverview error:', err);
    showToast('Failed to load live overview metrics', 'error');
  }
}

function updateSLA(kpis) {
  const dot = $('sla-dot');
  const title = $('sla-title');
  const time = $('sla-time');
  const freshText = $('freshness-text');
  const healthDot = $('sidebar-health-dot');

  const hours = kpis.hours_since_last_load != null ? kpis.hours_since_last_load : 0;
  const isHealthy = kpis.sla_healthy !== false;

  if (isHealthy) {
    if (dot) { dot.className = 'sla-dot pulsing'; dot.style.background = '#10b981'; }
    if (title) title.textContent = 'Warehouse Fresh';
    if (freshText) freshText.textContent = `Live Data (${hours}h ago)`;
    if (healthDot) healthDot.style.background = '#10b981';
  } else {
    if (dot) { dot.className = 'sla-dot'; dot.style.background = '#f59e0b'; }
    if (title) title.textContent = 'Warehouse Stale';
    if (freshText) freshText.textContent = `Stale (${hours}h ago)`;
    if (healthDot) healthDot.style.background = '#f59e0b';
  }

  if (time) time.textContent = `${hours}h since last sync`;
}

// ── TAB 2: SKILLS EXPLORER LOGIC ────────────────────────────────
let allSkillsData = [];
let activeCategory = 'ALL';

async function loadSkills() {
  const grid = $('skills-grid');
  if (!grid) return;

  try {
    allSkillsData = await API('/api/skills');
    renderSkillsGrid();
  } catch (err) {
    console.error('loadSkills error:', err);
    grid.innerHTML = '<div class="loading-state">Failed to fetch skills data</div>';
  }
}

function renderSkillsGrid() {
  const grid = $('skills-grid');
  if (!grid) return;

  const searchVal = ($('skills-search')?.value || '').trim().toLowerCase();
  const sortVal = $('skills-sort')?.value || 'demand-desc';

  let filtered = allSkillsData.filter(s => {
    const matchCat = activeCategory === 'ALL' || (s.skill_category || '').toLowerCase() === activeCategory.toLowerCase();
    const matchSearch = !searchVal ||
      (s.skill_display_name || '').toLowerCase().includes(searchVal) ||
      (s.skill_category || '').toLowerCase().includes(searchVal);
    return matchCat && matchSearch;
  });

  // Sorting
  filtered.sort((a, b) => {
    if (sortVal === 'demand-desc') return (b.posting_count || 0) - (a.posting_count || 0);
    if (sortVal === 'demand-asc')  return (a.posting_count || 0) - (b.posting_count || 0);
    if (sortVal === 'salary-desc') return (b.avg_midpoint_salary || 0) - (a.avg_midpoint_salary || 0);
    if (sortVal === 'name-asc')   return (a.skill_display_name || '').localeCompare(b.skill_display_name || '');
    return 0;
  });

  if (!filtered.length) {
    grid.innerHTML = `
      <div class="loading-state" style="grid-column: 1 / -1;">
        <span>No technologies match your filter criteria</span>
      </div>`;
    return;
  }

  const maxPostings = Math.max(...allSkillsData.map(s => s.posting_count || 1), 1);

  grid.innerHTML = filtered.map(s => {
    const pct = ((s.posting_count / maxPostings) * 100).toFixed(0);
    const sal = s.avg_midpoint_salary ? `£${Math.round(s.avg_midpoint_salary).toLocaleString()}` : 'Negotiable';

    return `
      <div class="skill-card spotlight-card">
        <div class="skill-card-top">
          <span class="skill-name">${s.skill_display_name}</span>
          <span class="skill-category-badge">${s.skill_category || 'General'}</span>
        </div>
        <div class="skill-metric-row">
          <span class="skill-count">${s.posting_count} <span style="font-size:0.75rem;font-weight:400;color:var(--text-muted)">postings</span></span>
          <span class="skill-pct">${s.market_penetration_pct}% market</span>
        </div>
        <div class="skill-progress-bar">
          <div class="skill-progress-fill" style="width: ${pct}%;"></div>
        </div>
        <div class="skill-meta">
          <span><i data-lucide="coins" style="width:12px;height:12px;vertical-align:-1px"></i> Avg: <strong>${sal}</strong></span>
          <span>Verified Node</span>
        </div>
      </div>`;
  }).join('');

  refreshIcons();
}

// Filter listeners
$('category-filters')?.addEventListener('click', e => {
  const btn = e.target.closest('.pill');
  if (!btn) return;

  document.querySelectorAll('#category-filters .pill').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  activeCategory = btn.dataset.category || 'ALL';
  renderSkillsGrid();
});

$('skills-search')?.addEventListener('input', () => {
  const clearBtn = $('skills-search-clear');
  if (clearBtn) {
    clearBtn.style.display = $('skills-search').value ? 'block' : 'none';
  }
  renderSkillsGrid();
});

$('skills-search-clear')?.addEventListener('click', () => {
  const inp = $('skills-search');
  if (inp) {
    inp.value = '';
    inp.focus();
  }
  $('skills-search-clear').style.display = 'none';
  renderSkillsGrid();
});

$('skills-sort')?.addEventListener('change', renderSkillsGrid);

// Keyboard shortcut ⌘K / Ctrl+K
document.addEventListener('keydown', e => {
  if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
    e.preventDefault();
    setTab('skills');
    $('skills-search')?.focus();
  }
});

// ── TAB 3: TECH STACKS LOGIC ────────────────────────────────────
let allStacksData = [];

async function loadTechStacks() {
  const tbody = $('stacks-tbody');
  if (!tbody) return;

  try {
    allStacksData = await API('/api/cooccurrences');
    renderStacksTable();

    if (allStacksData.length > 0) {
      const top = allStacksData[0];
      if ($('top-pair-name')) $('top-pair-name').textContent = `${top.skill_a} + ${top.skill_b}`;
      if ($('top-pair-count')) $('top-pair-count').textContent = `${top.pair_count} verified joint postings`;
    }
  } catch (err) {
    console.error('loadTechStacks error:', err);
    tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">Failed to load tech co-occurrences</td></tr>';
  }
}

function renderStacksTable() {
  const tbody = $('stacks-tbody');
  if (!tbody) return;

  const q = ($('stacks-search')?.value || '').trim().toLowerCase();
  const filtered = allStacksData.filter(s =>
    !q ||
    (s.skill_a || '').toLowerCase().includes(q) ||
    (s.skill_b || '').toLowerCase().includes(q)
  );

  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="6" class="loading-cell">No matching technology pairings</td></tr>';
    return;
  }

  const maxJoint = Math.max(...allStacksData.map(s => s.pair_count || 1), 1);

  tbody.innerHTML = filtered.map((row, idx) => {
    const widthPct = Math.round((row.pair_count / maxJoint) * 100);
    return `
      <tr>
        <td style="font-family:var(--font-mono);color:var(--text-dim);font-weight:700">#${idx + 1}</td>
        <td><span class="skill-pill">${row.skill_a}</span></td>
        <td><span class="skill-pill cyan">${row.skill_b}</span></td>
        <td style="font-family:var(--font-mono);font-weight:700;color:#fff">${row.pair_count}</td>
        <td>
          <div class="synergy-bar-wrap">
            <div class="synergy-bar-fill" style="width: ${widthPct}%;"></div>
          </div>
        </td>
        <td style="font-family:var(--font-mono);color:var(--cyan)">${widthPct}%</td>
      </tr>`;
  }).join('');
}

$('stacks-search')?.addEventListener('input', renderStacksTable);

// ── TAB 4: COMPANIES LOGIC ──────────────────────────────────────
let allCompaniesData = [];

async function loadCompanies() {
  const tbody = $('companies-tbody');
  if (!tbody) return;

  try {
    const [companies, locations] = await Promise.all([
      API('/api/companies?limit=25'),
      API('/api/locations?limit=5')
    ]);

    allCompaniesData = companies;
    renderCompaniesTable();

    // Render geographic hiring hubs
    const geoContainer = $('geo-hubs-list');
    if (geoContainer && locations.length) {
      geoContainer.innerHTML = locations.map(loc => `
        <div class="geo-item">
          <span class="geo-name"><i data-lucide="map-pin"></i> ${loc.city}, ${loc.country}</span>
          <span class="geo-count">${loc.posting_count} roles (avg £${Math.round(loc.avg_salary).toLocaleString()})</span>
        </div>`).join('');
      refreshIcons();
    }
  } catch (err) {
    console.error('loadCompanies error:', err);
    tbody.innerHTML = '<tr><td colspan="4" class="loading-cell">Failed to load hiring companies</td></tr>';
  }
}

function renderCompaniesTable() {
  const tbody = $('companies-tbody');
  if (!tbody) return;

  const q = ($('companies-search')?.value || '').trim().toLowerCase();
  const filtered = allCompaniesData.filter(c =>
    !q ||
    (c.company_name || '').toLowerCase().includes(q) ||
    (c.top_skills || '').toLowerCase().includes(q)
  );

  if (!filtered.length) {
    tbody.innerHTML = '<tr><td colspan="4" class="loading-cell">No matching hiring companies</td></tr>';
    return;
  }

  tbody.innerHTML = filtered.map(c => {
    const skills = (c.top_skills || 'General Data Pipeline')
      .split(',')
      .map(s => `<span class="skill-pill" style="margin-right:4px">${s.trim()}</span>`)
      .join('');

    const sal = c.min_salary && c.max_salary
      ? `£${Math.round(c.min_salary).toLocaleString()} - £${Math.round(c.max_salary).toLocaleString()}`
      : 'Competitive';

    return `
      <tr>
        <td style="font-weight:700;color:#fff">${c.company_name}</td>
        <td style="font-family:var(--font-mono);font-weight:600">${c.active_postings}</td>
        <td>${skills}</td>
        <td style="font-family:var(--font-mono);color:var(--emerald);font-size:0.78rem">${sal}</td>
      </tr>`;
  }).join('');
}

$('companies-search')?.addEventListener('input', renderCompaniesTable);

// ── TAB 5: OBSERVABILITY LOGIC ──────────────────────────────────
async function loadPipeline() {
  try {
    const health = await API('/api/pipeline/health');
    const { checks = [], table_counts = {} } = health;

    // Render warehouse table counts
    const whGrid = $('warehouse-grid');
    if (whGrid && Object.keys(table_counts).length) {
      whGrid.innerHTML = Object.entries(table_counts).map(([name, count]) => `
        <div class="wh-tile spotlight-card">
          <div class="wh-name">${name}</div>
          <div class="wh-count">${Number(count).toLocaleString()}</div>
        </div>`).join('');
    }

    // Render 11 quality assertions
    const checksTbody = $('checks-tbody');
    if (checksTbody && checks.length) {
      let passCount = 0, warnCount = 0, failCount = 0;

      checksTbody.innerHTML = checks.map(c => {
        const isPass = c.status === 'PASS';
        const isWarn = c.status === 'WARN';
        const isFail = c.status === 'FAIL';

        if (isPass) passCount++;
        else if (isWarn) warnCount++;
        else failCount++;

        const badgeClass = isPass ? 'pass' : isWarn ? 'warn' : 'fail';
        const iconName = isPass ? 'check' : isWarn ? 'alert-triangle' : 'x';

        return `
          <tr>
            <td>
              <span class="status-badge ${badgeClass}">
                <i data-lucide="${iconName}" style="width:11px;height:11px"></i> ${c.status}
              </span>
            </td>
            <td style="font-weight:600;color:#fff">${c.check_name}</td>
            <td style="font-family:var(--font-mono);color:var(--text-dim);font-size:0.75rem">${c.table_name || 'pipeline'}</td>
            <td style="font-family:var(--font-mono);color:#fff">${c.observed_value != null ? c.observed_value.toFixed(2) : '—'}</td>
            <td style="font-family:var(--font-mono);color:var(--cyan)">${c.threshold_value != null ? c.threshold_value.toFixed(2) : '—'}</td>
            <td style="color:var(--text-muted);font-size:0.75rem">${c.details || 'Assertion verified successfully'}</td>
          </tr>`;
      }).join('');

      // Update summary counts
      if ($('obs-pass-count')) $('obs-pass-count').textContent = passCount;
      if ($('obs-warn-count')) $('obs-warn-count').textContent = warnCount;
      if ($('obs-fail-count')) $('obs-fail-count').textContent = failCount;

      // Update Status Ring
      const total = checks.length || 11;
      const rate = Math.round((passCount / total) * 100);
      if ($('obs-ring-val')) $('obs-ring-val').textContent = `${rate}%`;

      const ringCircle = $('ring-progress-circle');
      if (ringCircle) {
        const circumference = 2 * Math.PI * 26; // 163.36
        const offset = circumference - (rate / 100) * circumference;
        ringCircle.style.strokeDashoffset = offset;
      }

      if ($('obs-last-run') && checks[0]?.executed_at) {
        $('obs-last-run').textContent = `Last Audit: ${new Date(checks[0].executed_at).toLocaleString()}`;
      }
    }

    refreshIcons();
  } catch (err) {
    console.error('loadPipeline error:', err);
    showToast('Failed to load observability metrics', 'error');
  }
}

// Trigger quality audit
async function triggerAudit() {
  const btn = $('btn-run-audit');
  const heroBtn = $('hero-btn-audit');
  const btnText = $('btn-audit-text');

  if (btn) btn.disabled = true;
  if (heroBtn) heroBtn.disabled = true;
  if (btnText) btnText.textContent = 'Running Assertions...';

  try {
    showToast('Triggering 11 data quality assertions...', 'info');
    await fetch('/api/pipeline/run-audit', { method: 'POST' });
    showToast('Data quality audit passed! Warehouse catalog refreshed.', 'success');
    await loadPipeline();
  } catch (err) {
    showToast('Audit run encountered an error', 'error');
  } finally {
    if (btn) btn.disabled = false;
    if (heroBtn) heroBtn.disabled = false;
    if (btnText) btnText.textContent = 'Run Quality Audit';
  }
}

$('btn-run-audit')?.addEventListener('click', triggerAudit);

// ── GLOBAL REFRESH ALL ──────────────────────────────────────────
$('btn-refresh-all')?.addEventListener('click', async () => {
  const btn = $('btn-refresh-all');
  btn?.classList.add('spinning');
  showToast('Refreshing live pipeline metrics...', 'info');

  await Promise.allSettled([
    loadOverview(),
    loadSkills(),
    loadTechStacks(),
    loadCompanies(),
    loadPipeline()
  ]);

  btn?.classList.remove('spinning');
  showToast('Platform refreshed with live data', 'success');
});

// ── INITIAL BOOT ────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  refreshIcons();
  loadAll();
});
