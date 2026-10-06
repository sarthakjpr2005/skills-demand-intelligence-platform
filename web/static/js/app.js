/* ═══════════════════════════════════════════════════════════════
   SKILLS DEMAND INTELLIGENCE PLATFORM — APP LOGIC
   Particle canvas · Animated counters · Chart.js · Live API
═══════════════════════════════════════════════════════════════ */

'use strict';

// ── Particle Canvas ──────────────────────────────────────────────
(function initParticles() {
  const canvas = document.getElementById('particle-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let W, H, particles = [];

  const COLORS = ['rgba(99,102,241,', 'rgba(6,182,212,', 'rgba(16,185,129,', 'rgba(168,85,247,'];

  function resize() {
    W = canvas.width  = window.innerWidth;
    H = canvas.height = window.innerHeight;
  }

  function spawnParticle() {
    const c = COLORS[Math.floor(Math.random() * COLORS.length)];
    return {
      x: Math.random() * W,
      y: Math.random() * H,
      r: Math.random() * 1.8 + 0.3,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      a: Math.random() * 0.4 + 0.1,
      color: c
    };
  }

  function init() {
    resize();
    particles = Array.from({ length: 80 }, spawnParticle);
  }

  function draw() {
    ctx.clearRect(0, 0, W, H);
    particles.forEach(p => {
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

    // Draw connections
    for (let i = 0; i < particles.length; i++) {
      for (let j = i + 1; j < particles.length; j++) {
        const dx = particles[i].x - particles[j].x;
        const dy = particles[i].y - particles[j].y;
        const d  = Math.sqrt(dx * dx + dy * dy);
        if (d < 120) {
          ctx.beginPath();
          ctx.moveTo(particles[i].x, particles[i].y);
          ctx.lineTo(particles[j].x, particles[j].y);
          ctx.strokeStyle = 'rgba(99,102,241,' + (0.08 * (1 - d / 120)) + ')';
          ctx.lineWidth = 0.5;
          ctx.stroke();
        }
      }
    }
    requestAnimationFrame(draw);
  }

  init();
  draw();
  window.addEventListener('resize', init);
})();

// ── Chart.js global defaults ─────────────────────────────────────
Chart.defaults.color = '#94a3b8';
Chart.defaults.font.family = "'Inter', system-ui, sans-serif";
Chart.defaults.font.size = 11;

// ── Utilities ────────────────────────────────────────────────────
const $ = id => document.getElementById(id);
const API = path => fetch(path).then(r => r.json());

function fmt(n, prefix = '') {
  if (n == null || isNaN(n)) return '--';
  if (Math.abs(n) >= 1000) return prefix + Math.round(n).toLocaleString();
  return prefix + Math.round(n).toLocaleString();
}

function fmtSalary(n) {
  if (!n || n === 0) return 'N/A';
  return '£' + Math.round(n).toLocaleString();
}

function animateCounter(el, target, prefix = '', suffix = '') {
  if (!el) return;
  const duration = 900;
  const start = performance.now();
  const from = 0;
  function step(now) {
    const p = Math.min((now - start) / duration, 1);
    const ease = 1 - Math.pow(1 - p, 3);
    const val = Math.round(from + (target - from) * ease);
    el.textContent = prefix + val.toLocaleString() + suffix;
    if (p < 1) requestAnimationFrame(step);
    else el.textContent = prefix + Math.round(target).toLocaleString() + suffix;
  }
  requestAnimationFrame(step);
}

function showToast(msg, type = 'success') {
  const tc = $('toast-container');
  if (!tc) return;
  const t = document.createElement('div');
  t.className = `toast toast-${type}`;
  const icon = type === 'success'
    ? '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#10b981" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>'
    : '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#ef4444" stroke-width="2.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>';
  t.innerHTML = icon + msg;
  tc.appendChild(t);
  setTimeout(() => { t.style.opacity = '0'; t.style.transform = 'translateX(20px)'; t.style.transition = '0.3s'; setTimeout(() => t.remove(), 300); }, 3500);
}

function getCatClass(cat) {
  const map = {
    cloud:'cat-cloud', warehouse:'cat-warehouse', language:'cat-language',
    platform:'cat-platform', orchestration:'cat-orchestration',
    transformation:'cat-transformation', bi:'cat-bi', iac:'cat-iac'
  };
  return map[cat?.toLowerCase()] || 'cat-warehouse';
}

// ── Tab Navigation ───────────────────────────────────────────────
const PAGES = { overview:'Overview', skills:'Skills Explorer', stacks:'Tech Stacks', companies:'Companies', pipeline:'Observability' };
let activeTab = 'overview';

document.querySelectorAll('.nav-item').forEach(btn => {
  btn.addEventListener('click', () => {
    const tab = btn.dataset.tab;
    if (!tab) return;
    switchTab(tab);
  });
});

function switchTab(tab) {
  document.querySelectorAll('.nav-item').forEach(b => b.classList.toggle('active', b.dataset.tab === tab));
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.toggle('active', p.id === 'tab-' + tab));
  const bc = $('breadcrumb-page');
  if (bc) bc.textContent = PAGES[tab] || tab;
  activeTab = tab;
}

// Sidebar toggle (mobile)
const sidebarToggle = $('sidebar-toggle');
const sidebar = document.querySelector('.sidebar');
if (sidebarToggle) {
  sidebarToggle.addEventListener('click', () => {
    sidebar?.classList.toggle('open');
  });
}

// ── Chart Instances ──────────────────────────────────────────────
let chartSkills = null, chartCategories = null;

function destroyChart(c) { if (c) { try { c.destroy(); } catch (_) {} } }

const PALETTE = [
  '#6366f1','#06b6d4','#10b981','#f59e0b','#a855f7','#ef4444',
  '#22d3ee','#34d399','#fbbf24','#c084fc','#f87171','#818cf8',
  '#2dd4bf','#fb923c','#e879f9','#4ade80'
];

// ── OVERVIEW ─────────────────────────────────────────────────────
async function loadOverview() {
  try {
    const [kpis, skills, cats] = await Promise.all([
      API('/api/overview'),
      API('/api/skills'),
      API('/api/categories')
    ]);

    // KPIs with animated counters
    animateCounter($('val-total-postings'), kpis.total_postings);
    animateCounter($('val-tracked-skills'), kpis.tracked_skills);
    animateCounter($('val-total-companies'), kpis.total_companies);

    const salEl = $('val-avg-salary');
    if (salEl) animateCounter(salEl, kpis.avg_salary, '£');

    const mentEl = $('val-skill-mentions');
    if (mentEl) animateCounter(mentEl, kpis.total_skill_mentions, '', ' mentions');

    // Skills badge in nav
    const badge = $('badge-skills');
    if (badge) badge.textContent = kpis.tracked_skills;

    // SLA
    updateSLA(kpis);

    // Top skills horizontal bar
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
            backgroundColor: top10.map((_, i) => PALETTE[i % PALETTE.length] + '99'),
            borderColor:     top10.map((_, i) => PALETTE[i % PALETTE.length]),
            borderWidth: 1.5,
            borderRadius: 6,
            borderSkipped: false,
          }]
        },
        options: {
          indexAxis: 'y',
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 800, easing: 'easeOutQuart' },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: 'rgba(15,23,42,0.95)',
              borderColor: 'rgba(99,102,241,0.3)',
              borderWidth: 1,
              titleColor: '#f1f5f9',
              bodyColor: '#94a3b8',
              callbacks: {
                label: ctx => ` ${ctx.parsed.x} postings (${top10[ctx.dataIndex].market_penetration_pct}% market)`
              }
            }
          },
          scales: {
            x: {
              grid: { color: 'rgba(255,255,255,0.04)' },
              ticks: { color: '#64748b' },
              border: { color: 'rgba(255,255,255,0.06)' }
            },
            y: {
              grid: { display: false },
              ticks: { color: '#94a3b8', font: { weight: '600' } },
              border: { display: false }
            }
          }
        }
      });
    }

    // Doughnut category chart
    destroyChart(chartCategories);
    const ctxC = $('chart-categories');
    if (ctxC && cats.length) {
      chartCategories = new Chart(ctxC, {
        type: 'doughnut',
        data: {
          labels: cats.map(c => c.skill_category.charAt(0).toUpperCase() + c.skill_category.slice(1)),
          datasets: [{
            data: cats.map(c => c.total_mentions),
            backgroundColor: cats.map((_, i) => PALETTE[i % PALETTE.length] + 'bb'),
            borderColor: cats.map((_, i) => PALETTE[i % PALETTE.length]),
            borderWidth: 1.5,
            hoverOffset: 8,
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          cutout: '62%',
          animation: { duration: 900 },
          plugins: {
            legend: {
              position: 'right',
              labels: {
                boxWidth: 10,
                boxHeight: 10,
                padding: 12,
                color: '#94a3b8',
                font: { size: 11 },
                usePointStyle: true
              }
            },
            tooltip: {
              backgroundColor: 'rgba(15,23,42,0.95)',
              borderColor: 'rgba(99,102,241,0.3)',
              borderWidth: 1,
              callbacks: {
                label: ctx => ` ${ctx.label}: ${ctx.parsed} mentions`
              }
            }
          }
        }
      });
    }

    showToast('Dashboard data refreshed', 'success');
  } catch (err) {
    console.error('loadOverview error:', err);
    showToast('Could not connect to database', 'error');
  }
}

function updateSLA(kpis) {
  const dot   = $('sla-dot');
  const title = $('sla-title');
  const time  = $('sla-time');
  const fresh = $('freshness-badge');
  const freshTxt = $('freshness-text');
  const sCard = $('sidebar-health-dot');

  const h = kpis.hours_since_last_load;
  let healthy = kpis.sla_healthy;

  if (dot) {
    dot.className = 'sla-dot pulsing';
    if (!healthy || h > 36) { dot.classList.add('fail-dot'); }
    else if (h > 24) { dot.classList.add('warn-dot'); }
  }

  if (title) {
    if (healthy && h <= 24) title.textContent = 'Warehouse Fresh';
    else if (h <= 36) title.textContent = 'SLA Warning';
    else title.textContent = 'SLA Breach';
    title.style.color = healthy ? '' : (h <= 36 ? '#fbbf24' : '#f87171');
  }

  if (time) time.textContent = h > 0 ? `${h}h ago` : 'Just now';

  if (freshTxt) {
    freshTxt.textContent = healthy ? 'Live Data' : `${h}h stale`;
  }
  if (fresh) {
    const fd = fresh.querySelector('.fresh-dot');
    if (fd) fd.style.background = healthy ? '#10b981' : (h <= 36 ? '#f59e0b' : '#ef4444');
  }
}

// ── SKILLS EXPLORER ──────────────────────────────────────────────
let allSkills = [];

async function loadSkills() {
  try {
    allSkills = await API('/api/skills');
    renderSkillsGrid(allSkills);
  } catch (err) {
    console.error('loadSkills error:', err);
    showToast('Could not load skills data', 'error');
  }
}

function renderSkillsGrid(data) {
  const container = $('skills-grid-container');
  if (!container) return;

  if (!data.length) {
    container.innerHTML = '<div style="color:var(--text-muted);text-align:center;padding:3rem;grid-column:1/-1">No skills match the current filter.</div>';
    return;
  }

  const maxCount = Math.max(...data.map(s => s.posting_count || 0), 1);

  container.innerHTML = data.map(s => {
    const pct   = Math.round(((s.posting_count || 0) / maxCount) * 100);
    const cat   = (s.skill_category || 'other').toLowerCase();
    const catCls = getCatClass(cat);
    const salary = s.avg_midpoint_salary > 0 ? fmtSalary(s.avg_midpoint_salary) : 'N/A';
    const pen   = s.market_penetration_pct || 0;

    return `
      <div class="skill-tile">
        <div class="skill-tile-top">
          <span class="skill-name">${s.skill_display_name}</span>
          <span class="skill-cat-badge ${catCls}">${cat}</span>
        </div>
        <div class="skill-demand-bar-outer">
          <div class="skill-demand-bar" style="width:${pct}%"></div>
        </div>
        <div class="skill-tile-stats">
          <div class="skill-stat">
            <span class="skill-stat-val">${s.posting_count || 0}</span>
            <span class="skill-stat-lbl">postings</span>
          </div>
          <div class="skill-stat">
            <span class="skill-stat-val">${pen}%</span>
            <span class="skill-stat-lbl">market</span>
          </div>
          <div class="skill-stat">
            <span class="skill-stat-val">${salary}</span>
            <span class="skill-stat-lbl">avg salary</span>
          </div>
        </div>
      </div>`;
  }).join('');
}

// Search + filter
const searchInput = $('skill-search-input');
const sortSelect  = $('sort-select');

function applyFilters() {
  const query = (searchInput?.value || '').toLowerCase().trim();
  const active = document.querySelector('.chip.active')?.dataset.category || 'all';
  const sortBy = sortSelect?.value || 'demand';

  let data = [...allSkills];

  if (active !== 'all') data = data.filter(s => s.skill_category?.toLowerCase() === active);
  if (query) data = data.filter(s => s.skill_display_name?.toLowerCase().includes(query));

  data.sort((a, b) => {
    if (sortBy === 'salary') return (b.avg_midpoint_salary || 0) - (a.avg_midpoint_salary || 0);
    if (sortBy === 'name')   return a.skill_display_name.localeCompare(b.skill_display_name);
    return (b.posting_count || 0) - (a.posting_count || 0);
  });

  renderSkillsGrid(data);
}

searchInput?.addEventListener('input', applyFilters);
sortSelect?.addEventListener('change', applyFilters);

document.getElementById('category-filter-chips')?.addEventListener('click', e => {
  const chip = e.target.closest('.chip');
  if (!chip) return;
  document.querySelectorAll('.chip').forEach(c => c.classList.remove('active'));
  chip.classList.add('active');
  applyFilters();
});

// ── TECH STACKS ──────────────────────────────────────────────────
async function loadTechStacks() {
  try {
    const pairs = await API('/api/cooccurrences');
    const container = $('stack-pairs-container');
    if (!container || !pairs.length) return;

    const max = pairs[0].pair_count || 1;

    container.innerHTML = pairs.map((p, i) => {
      const pct = Math.round((p.pair_count / max) * 100);
      return `
        <div class="stack-pair">
          <span class="pair-rank">${i + 1}</span>
          <div class="pair-pills">
            <span class="pair-pill">${p.skill_a}</span>
            <span class="pair-plus">+</span>
            <span class="pair-pill">${p.skill_b}</span>
          </div>
          <div class="pair-count-bar">
            <div class="pair-bar-outer">
              <div class="pair-bar-fill" style="width:${pct}%"></div>
            </div>
            <span class="pair-count">${p.pair_count}</span>
          </div>
        </div>`;
    }).join('');
  } catch (err) {
    console.error('loadTechStacks error:', err);
    showToast('Could not load co-occurrence data', 'error');
  }
}

// ── COMPANIES & SALARY ───────────────────────────────────────────
async function loadCompanies() {
  try {
    const [companies, locations, skills] = await Promise.all([
      API('/api/companies'),
      API('/api/locations'),
      API('/api/skills')
    ]);

    // Companies list
    const compEl = $('companies-list-container');
    if (compEl && companies.length) {
      compEl.innerHTML = companies.slice(0, 12).map((c, i) => {
        const initials = c.company_name.split(/\s+/).slice(0, 2).map(w => w[0]).join('').toUpperCase();
        return `
          <div class="company-row">
            <span class="company-rank">${i + 1}</span>
            <div class="company-avatar">${initials}</div>
            <div class="company-info">
              <div class="company-name">${c.company_name}</div>
              <div class="company-skills">${c.top_skills || 'Various skills'}</div>
            </div>
            <span class="company-count">${c.active_postings}</span>
          </div>`;
      }).join('');
    }

    // Locations
    const locEl = $('locations-list-container');
    const flags = {'LONDON':'🇬🇧','GB':'🇬🇧','UK':'🇬🇧','REMOTE':'🌐','US':'🇺🇸','DE':'🇩🇪','FR':'🇫🇷','SG':'🇸🇬','AU':'🇦🇺','IE':'🇮🇪','NL':'🇳🇱','CA':'🇨🇦'};
    if (locEl && locations.length) {
      locEl.innerHTML = locations.slice(0, 8).map(l => {
        const flag = flags[l.country?.toUpperCase()] || flags[l.city?.toUpperCase()] || '📍';
        return `
          <div class="location-row">
            <span class="location-flag">${flag}</span>
            <span class="location-name">${l.city}${l.country ? ', ' + l.country : ''}</span>
            <span class="location-count">${l.posting_count}</span>
          </div>`;
      }).join('');
    }

    // Salary spectrum (from skills data sorted by salary)
    const salEl = $('salary-spectrum-container');
    const salSkills = [...skills].filter(s => s.avg_midpoint_salary > 0).sort((a, b) => b.avg_midpoint_salary - a.avg_midpoint_salary).slice(0, 8);
    const maxSal = salSkills[0]?.avg_midpoint_salary || 1;
    if (salEl && salSkills.length) {
      salEl.innerHTML = salSkills.map((s, i) => {
        const pct = Math.round((s.avg_midpoint_salary / maxSal) * 100);
        return `
          <div class="salary-row">
            <span class="sal-rank">${i + 1}</span>
            <span class="sal-name">${s.skill_display_name}</span>
            <div class="sal-bar-wrap">
              <div class="sal-bar-outer">
                <div class="sal-bar-fill" style="width:${pct}%"></div>
              </div>
              <span class="sal-val">${fmtSalary(s.avg_midpoint_salary)}</span>
            </div>
          </div>`;
      }).join('');
    }
  } catch (err) {
    console.error('loadCompanies error:', err);
    showToast('Could not load company data', 'error');
  }
}

// ── OBSERVABILITY HUB ────────────────────────────────────────────
async function loadPipeline() {
  try {
    const data = await API('/api/pipeline/health');
    const { runs = [], checks = [], table_counts = {} } = data;

    // Obs hero
    const pass = checks.filter(c => c.status === 'PASS').length;
    const warn = checks.filter(c => c.status === 'WARN').length;
    const fail = checks.filter(c => c.status === 'FAIL').length;
    const total = checks.length;

    const ringCount = $('ring-count');
    if (ringCount) ringCount.textContent = `${pass}/${total}`;

    const ringProgress = $('ring-progress');
    if (ringProgress && total > 0) {
      const circumference = 2 * Math.PI * 26;
      const offset = circumference * (1 - pass / total);
      ringProgress.style.strokeDashoffset = offset;
      ringProgress.style.stroke = fail > 0 ? '#ef4444' : warn > 0 ? '#f59e0b' : 'url(#rg)';
    }

    const statusLabel = $('obs-status-label');
    const statusDesc  = $('obs-status-desc');
    if (statusLabel) {
      if (fail > 0)      { statusLabel.textContent = `${fail} Check${fail>1?'s':''} Failing`; statusLabel.style.color = '#f87171'; }
      else if (warn > 0) { statusLabel.textContent = `${warn} Warning${warn>1?'s':''}`; statusLabel.style.color = '#fbbf24'; }
      else               { statusLabel.textContent = 'All Checks Passing'; statusLabel.style.color = '#34d399'; }
    }
    if (statusDesc) statusDesc.textContent = `${pass} passed · ${warn} warned · ${fail} failed of ${total} assertions`;

    // Update sidebar dot
    const sidebarDot = $('sidebar-health-dot');
    if (sidebarDot) {
      sidebarDot.style.background = fail > 0 ? '#ef4444' : warn > 0 ? '#f59e0b' : '#10b981';
    }

    // Mini stats
    const miniStats = $('obs-mini-stats');
    if (miniStats) {
      miniStats.innerHTML = `
        <div class="obs-mini-stat">
          <span class="obs-mini-val pass">${pass}</span>
          <span class="obs-mini-lbl">Pass</span>
        </div>
        <div class="obs-mini-stat">
          <span class="obs-mini-val warn">${warn}</span>
          <span class="obs-mini-lbl">Warn</span>
        </div>
        <div class="obs-mini-stat">
          <span class="obs-mini-val fail">${fail}</span>
          <span class="obs-mini-lbl">Fail</span>
        </div>`;
    }

    // Warehouse tile counts
    const whContainer = $('warehouse-stats-container');
    if (whContainer) {
      const tiles = [
        { label: 'raw_postings',        count: table_counts.raw_postings       || 0, schema: 'staging' },
        { label: 'fct_postings',        count: table_counts.fct_postings        || 0, schema: 'marts' },
        { label: 'fct_posting_skills',  count: table_counts.fct_posting_skills  || 0, schema: 'marts' },
        { label: 'dim_company',         count: table_counts.dim_company          || 0, schema: 'marts' },
        { label: 'dim_skill',           count: table_counts.dim_skill            || 0, schema: 'marts' },
        { label: 'dim_location',        count: table_counts.dim_location         || 0, schema: 'marts' },
        { label: 'dim_date',            count: table_counts.dim_date             || 0, schema: 'marts' },
        { label: 'quality_checks',      count: table_counts.quality_checks       || 0, schema: 'monitoring' },
      ];
      whContainer.innerHTML = tiles.map(t => `
        <div class="warehouse-tile">
          <div class="wh-label">${t.label}</div>
          <div class="wh-count">${t.count.toLocaleString()}</div>
          <div class="wh-schema">${t.schema}</div>
        </div>`).join('');
    }

    // Quality checks table
    const tbody = $('tbody-quality-checks');
    if (tbody && checks.length) {
      tbody.innerHTML = checks.map(c => {
        const badgeCls = c.status === 'PASS' ? 'badge-pass' : c.status === 'WARN' ? 'badge-warn' : 'badge-fail';
        const cat = (c.check_category || '').replace(/_/g, ' ');
        const obs = c.observed_value != null ? c.observed_value.toFixed(2) : '—';
        const thr = c.threshold_value != null ? c.threshold_value.toFixed(2) : '—';
        return `
          <tr>
            <td><span class="status-badge ${badgeCls}">${c.status}</span></td>
            <td style="color:var(--text-secondary);text-transform:capitalize">${cat}</td>
            <td style="font-weight:600;color:var(--text-primary)">${c.check_name}</td>
            <td class="mono">${c.table_name || '—'}</td>
            <td class="mono">${obs}</td>
            <td class="mono">${thr}</td>
            <td style="font-size:11px;color:var(--text-secondary);max-width:220px">${c.details || '—'}</td>
          </tr>`;
      }).join('');

      if (checks[0]?.executed_at) {
        const ts = $('checks-timestamp');
        if (ts) ts.textContent = 'Last verified: ' + new Date(checks[0].executed_at).toLocaleString();
      }
    }

    // Pipeline runs table
    const tRuns = $('tbody-pipeline-runs');
    if (tRuns && runs.length) {
      tRuns.innerHTML = runs.map(r => {
        const dur = r.duration_seconds ? Math.round(r.duration_seconds) + 's' : '—';
        const shortId = r.pull_batch_id ? r.pull_batch_id.slice(0, 8) + '…' : '—';
        const started = r.started_at ? new Date(r.started_at).toLocaleString() : '—';
        const statusCls = r.status === 'success' || r.status === 'completed' ? 'badge-pass' : r.status === 'partial' ? 'badge-warn' : 'badge-fail';
        return `
          <tr>
            <td class="mono" style="font-size:10.5px;color:var(--text-muted)">${shortId}</td>
            <td style="font-size:12px">${started}</td>
            <td class="mono">${dur}</td>
            <td class="mono">${r.records_fetched ?? '—'}</td>
            <td class="mono" style="color:var(--emerald-lg)">${r.records_passed ?? '—'}</td>
            <td class="mono" style="color:var(--amber-lg)">${r.records_failed ?? '—'}</td>
            <td class="mono">${r.records_deduplicated ?? '—'}</td>
            <td class="mono" style="color:var(--cyan-lg)">${r.records_loaded ?? '—'}</td>
            <td><span class="status-badge ${statusCls}">${r.status ?? '—'}</span></td>
          </tr>`;
      }).join('');
    }

    showToast('Observability data loaded', 'success');
  } catch (err) {
    console.error('loadPipeline error:', err);
    showToast('Could not load observability data', 'error');
  }
}

// Run Audit button
$('btn-trigger-audit')?.addEventListener('click', async () => {
  const btn = $('btn-trigger-audit');
  if (btn) { btn.disabled = true; btn.textContent = 'Running…'; }
  try {
    await fetch('/api/pipeline/run-audit', { method: 'POST' });
    showToast('Quality audit completed!', 'success');
    await loadPipeline();
  } catch (err) {
    showToast('Audit failed — check pipeline', 'error');
  } finally {
    if (btn) { btn.disabled = false; btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polygon points="5 3 19 12 5 21 5 3"/></svg> Run Quality Audit'; }
  }
});

// ── Refresh Button ───────────────────────────────────────────────
$('btn-refresh-all')?.addEventListener('click', async () => {
  const btn = $('btn-refresh-all');
  btn?.classList.add('spinning');
  await loadAll();
  btn?.classList.remove('spinning');
  showToast('All data refreshed', 'success');
});

// ── Load All ─────────────────────────────────────────────────────
async function loadAll() {
  await Promise.allSettled([
    loadOverview(),
    loadSkills(),
    loadTechStacks(),
    loadCompanies(),
    loadPipeline()
  ]);
}

// ── Boot ─────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  loadAll();
});
