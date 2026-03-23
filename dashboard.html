<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>WarWatch — Bot Log</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Lora:wght@700&family=IBM+Plex+Sans:wght@300;400;500&family=IBM+Plex+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
*,*::before,*::after{margin:0;padding:0;box-sizing:border-box}
html{scroll-behavior:smooth}
body{font-family:'IBM Plex Sans',sans-serif;font-size:14px;line-height:1.7;background:#141414;color:#e0e0dc}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.3}}
@keyframes fadeUp{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}

/* ── CANONICAL HEADER ── */
header{background:#1a1a1a;padding:23px 32px;position:sticky;top:0;z-index:200;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #2a2a2a}
.masthead{font-size:22px;font-weight:900;letter-spacing:-.02em;display:flex;align-items:center;line-height:1}
.masthead-war{background:#c41e3a;color:#fff;padding:3px 10px}
.masthead-watch{color:#fff;padding:3px 5px}
.header-date{font-size:11px;color:#888;letter-spacing:.06em;font-family:'IBM Plex Mono',monospace}
nav{display:flex;align-items:center;gap:0}
.nav-item{color:#aaa;text-decoration:none;padding:0 16px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;font-weight:500;border-right:1px solid #444;transition:color .2s;white-space:nowrap}
.nav-item:last-child{border-right:none;padding-right:0}
.nav-item:hover{color:#fff}
.nav-item.live{color:#c41e3a}
.ai-sum-badge{background:#1a1a1a;border:1px solid #c41e3a;color:#c41e3a;font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:700;padding:3px 9px;letter-spacing:.1em;text-transform:uppercase;border-radius:2px;white-space:nowrap}
.ai-sum-badge{background:transparent;border:1px solid #c41e3a;color:#c41e3a;font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:700;padding:3px 9px;letter-spacing:.1em;text-transform:uppercase;border-radius:2px;white-space:nowrap}
.live-dot{display:inline-block;width:6px;height:6px;border-radius:50%;background:#c41e3a;margin-right:4px;animation:pulse 1.5s infinite}

/* ── SUB BAR ── */
.sub-bar{background:#1e1e1e;border-bottom:1px solid #2a2a2a;padding:9px 32px;display:flex;align-items:center;gap:12px}
.sub-title{font-family:'IBM Plex Mono',monospace;font-size:11px;font-weight:500;letter-spacing:.08em;text-transform:uppercase;color:#888}
.sub-title span{color:#c41e3a}
.sub-status{display:flex;align-items:center;gap:5px;font-family:'IBM Plex Mono',monospace;font-size:10px;color:#555;margin-left:auto}
.run-dot{width:6px;height:6px;border-radius:50%;background:#3daa72;animation:pulse 2s infinite;flex-shrink:0}
.sub-last{font-family:'IBM Plex Mono',monospace;font-size:10px;color:#444}

/* ── LAYOUT ── */
.page{padding:20px 32px 50px;display:grid;grid-template-columns:1fr 260px;gap:20px;max-width:1300px;margin:0 auto;align-items:start}

/* ── LOG SECTION ── */
.log-head{display:flex;align-items:center;gap:10px;margin-bottom:14px}
.log-head-lbl{font-family:'IBM Plex Mono',monospace;font-size:10px;letter-spacing:.12em;text-transform:uppercase;color:#555}
.log-head-count{font-family:'IBM Plex Mono',monospace;font-size:9px;color:#444}
.log-head-line{flex:1;height:1px;background:#2a2a2a}
.log-list{display:flex;flex-direction:column;gap:12px}

.rc{background:#1e1e1e;border:1px solid #2a2a2a;border-radius:7px;padding:16px 18px;animation:fadeUp .35s ease forwards;opacity:0}
.rc-top{display:flex;align-items:center;gap:8px;margin-bottom:10px}
.lv{font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:700;padding:2px 7px;border-radius:2px;letter-spacing:.06em;text-transform:uppercase}
.lv-crit{background:rgba(196,30,58,.2);color:#e07070;border:.5px solid rgba(196,30,58,.4)}
.lv-high{background:rgba(212,137,42,.2);color:#d4a94a;border:.5px solid rgba(212,137,42,.4)}
.lv-med{background:rgba(61,170,114,.2);color:#5ccc8e;border:.5px solid rgba(61,170,114,.4)}
.lv-low{background:rgba(100,100,100,.2);color:#888;border:.5px solid rgba(100,100,100,.3)}
.rc-ts{font-family:'IBM Plex Mono',monospace;font-size:10px;color:#555}
.rc-tone{font-family:'IBM Plex Mono',monospace;font-size:9px;color:#444;margin-left:auto;text-transform:uppercase;letter-spacing:.04em}
.rc-summary{font-size:12px;color:#888;line-height:1.75;font-weight:300;margin-bottom:10px}
.rc-devs{display:flex;flex-direction:column;gap:5px}
.rc-dev{display:flex;align-items:flex-start;gap:7px;font-size:11px;color:#666;line-height:1.45}
.rc-dev-actor{color:#ccc;font-weight:500;white-space:nowrap;flex-shrink:0}
.rc-dev-hl{flex:1}
.rc-dev-link{font-family:'IBM Plex Mono',monospace;font-size:10px;color:#c41e3a;text-decoration:none;flex-shrink:0;margin-left:6px}
.rc-dev-link:hover{opacity:.7}
.rc-foot{display:flex;align-items:center;gap:12px;margin-top:10px;padding-top:10px;border-top:1px solid #222}
.rc-foot-stat{font-family:'IBM Plex Mono',monospace;font-size:9px;color:#444}

/* ── SIDEBAR ── */
.sidebar{display:flex;flex-direction:column;gap:12px}
.side-card{background:#1e1e1e;border:1px solid #2a2a2a;border-radius:7px;padding:16px 18px}
.side-head{font-family:'IBM Plex Mono',monospace;font-size:9px;letter-spacing:.12em;text-transform:uppercase;color:#555;margin-bottom:12px;display:flex;align-items:center;gap:6px}
.side-head::after{content:'';flex:1;height:1px;background:#2a2a2a}

.stat-row{display:flex;flex-direction:column;gap:8px}
.stat-item{display:flex;justify-content:space-between;align-items:baseline}
.stat-name{font-size:12px;color:#777}
.stat-val{font-family:'IBM Plex Mono',monospace;font-size:12px;color:#ddd}
.stat-val.red{color:#c41e3a}
.stat-val.green{color:#3daa72}
.stat-val.amber{color:#d4892a}

.chart-wrap{height:80px;display:flex;align-items:flex-end;gap:3px}
.bar-item{flex:1;display:flex;flex-direction:column;align-items:center;gap:3px}
.bar-col{width:100%;border-radius:2px 2px 0 0;min-height:4px;transition:height .8s cubic-bezier(.4,0,.2,1)}
.bar-lbl{font-family:'IBM Plex Mono',monospace;font-size:7px;color:#444}

.pipeline-row{display:flex;align-items:center;gap:8px;padding:7px 0;border-bottom:.5px solid #222}
.pipeline-row:last-child{border-bottom:none}
.pipeline-name{font-family:'IBM Plex Mono',monospace;font-size:10px;color:#bbb}
.pill-ok{background:rgba(61,170,114,.2);color:#5ccc8e;font-family:'IBM Plex Mono',monospace;font-size:9px;padding:2px 7px;border-radius:2px;margin-left:auto}
.pill-run{background:rgba(212,137,42,.2);color:#d4a94a;font-family:'IBM Plex Mono',monospace;font-size:9px;padding:2px 7px;border-radius:2px;margin-left:auto}
.pill-off{background:rgba(100,100,100,.15);color:#555;font-family:'IBM Plex Mono',monospace;font-size:9px;padding:2px 7px;border-radius:2px;margin-left:auto}

.about-item{margin-bottom:9px}
.about-key{font-family:'IBM Plex Mono',monospace;font-size:9px;color:#555;margin-bottom:2px}
.about-val{font-size:11px;color:#777;line-height:1.6;font-weight:300}

/* ── FOOTER ── */
footer{padding:18px 24px;border:1px solid #2a2a2a;background:#1a1a1a;border-radius:6px;display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;margin-top:10px}
.footer-logo{font-family:'IBM Plex Mono',monospace;font-size:12px;font-weight:500;letter-spacing:.08em;text-transform:uppercase;color:#888}
.footer-logo span{color:#c41e3a}
.footer-meta{font-family:'IBM Plex Mono',monospace;font-size:11px;color:#555;text-align:right;line-height:1.7}

@media(max-width:900px){.page{grid-template-columns:1fr}.sidebar{display:none}}
@media(max-width:600px){header{padding:12px 16px}.masthead{font-size:18px}.page{padding:16px}}
.ai-sum-badge{background:transparent;border:1px solid #c41e3a;color:#c41e3a;font-family:'IBM Plex Mono',monospace;font-size:9px;font-weight:700;padding:3px 9px;letter-spacing:.1em;text-transform:uppercase;border-radius:2px;white-space:nowrap}
</style>
</head>
<body>

<header>
  <div style="display:flex;flex-direction:column;gap:0"><div style="display:flex;align-items:center;gap:10px"><h1 class="masthead"><span class="masthead-war">WAR</span><span class="masthead-watch">WATCH</span></h1><span class="ai-sum-badge">AI Summariser</span></div>
  <div class="header-date" id="header-date" style="font-size:9px;color:#555;letter-spacing:.06em;font-family:\'IBM Plex Mono\',monospace;margin-top:3px"></div>
  </div>
  <nav>
    <a class="nav-item live" href="index.html"><span class="live-dot"></span>Live</a>
    <a class="nav-item" href="india.html">India</a>
    <a class="nav-item" href="economy.html">Economy</a>
    <a class="nav-item" href="digest.html">Daily Digest</a>
    <a class="nav-item" href="records.html">Records</a>
    <a class="nav-item" href="warwatch.html">War Context</a>
  </nav>
</header>

<div class="sub-bar">
  <span class="sub-title">War<span>Watch</span> Bot — Report Log</span>
  <div class="sub-status"><span class="run-dot"></span>Running · GitHub Actions</div>
  <span class="sub-last" id="last-run-txt">Last run: —</span>
</div>

<div class="page">

  <div>
    <div class="log-head">
      <span class="log-head-lbl">Report log</span>
      <span class="log-head-count" id="report-count"></span>
      <div class="log-head-line"></div>
    </div>

    <div class="log-list" id="log-list">
      <!-- Populated by live_data.js history. Static fallbacks below. -->
      <div class="rc" style="animation-delay:.05s">
        <div class="rc-top">
          <span class="lv lv-crit">Critical</span>
          <span class="rc-ts" id="ts-0">—</span>
          <span class="rc-tone">HOSTILE</span>
        </div>
        <div class="rc-summary" id="summary-0">US strikes on Chabahar IRGC drone base confirmed. Iran retaliates with ballistic test over Gulf. Two US carrier groups now in theatre. UNSC veto blocks ceasefire resolution.</div>
        <div class="rc-devs" id="devs-0">
          <div class="rc-dev"><span class="rc-dev-actor">US</span><span class="rc-dev-hl">Strikes destroy IRGC drone infrastructure in Chabahar province</span><a class="rc-dev-link" href="https://www.ndtv.com" target="_blank">↗</a></div>
          <div class="rc-dev"><span class="rc-dev-actor">Iran</span><span class="rc-dev-hl">Khorramshahr-4 ballistic test over Gulf — 2,000km range demonstrated</span><a class="rc-dev-link" href="https://www.ndtv.com" target="_blank">↗</a></div>
          <div class="rc-dev"><span class="rc-dev-actor">Israel</span><span class="rc-dev-hl">25-drone swarm over Tel Aviv intercepted by Iron Dome</span><a class="rc-dev-link" href="https://www.ndtv.com" target="_blank">↗</a></div>
          <div class="rc-dev"><span class="rc-dev-actor">UN</span><span class="rc-dev-hl">Russia, China jointly veto UNSC ceasefire resolution 11-2</span><a class="rc-dev-link" href="https://www.ndtv.com" target="_blank">↗</a></div>
        </div>
        <div class="rc-foot">
          <span class="rc-foot-stat">17 sources · 4 tiers</span>
          <span class="rc-foot-stat" id="arts-0">— articles processed</span>
        </div>
      </div>

      <div class="rc" style="animation-delay:.1s">
        <div class="rc-top">
          <span class="lv lv-crit">Critical</span>
          <span class="rc-ts" id="ts-1">—</span>
          <span class="rc-tone">ESCALATING</span>
        </div>
        <div class="rc-summary" id="summary-1">USS Gerald Ford repositions to within 180 miles of Iranian coast. Brent crude hits $103. Qatar initiates back-channel talks between US and Iran.</div>
        <div class="rc-devs" id="devs-1">
          <div class="rc-dev"><span class="rc-dev-actor">US Navy</span><span class="rc-dev-hl">Gerald Ford carrier group moves within striking range of key Iranian sites</span><a class="rc-dev-link" href="https://www.ndtv.com" target="_blank">↗</a></div>
          <div class="rc-dev"><span class="rc-dev-actor">Markets</span><span class="rc-dev-hl">Brent crude $103 — Goldman raises 90-day target to $115</span><a class="rc-dev-link" href="https://www.ndtv.com" target="_blank">↗</a></div>
          <div class="rc-dev"><span class="rc-dev-actor">Qatar</span><span class="rc-dev-hl">Mediating 72-hour pause proposal — no agreement yet</span><a class="rc-dev-link" href="https://www.ndtv.com" target="_blank">↗</a></div>
        </div>
        <div class="rc-foot">
          <span class="rc-foot-stat">17 sources · 4 tiers</span>
          <span class="rc-foot-stat">18 articles processed</span>
        </div>
      </div>

      <div class="rc" style="animation-delay:.15s">
        <div class="rc-top">
          <span class="lv lv-high">High</span>
          <span class="rc-ts" id="ts-2">—</span>
          <span class="rc-tone">TENSE</span>
        </div>
        <div class="rc-summary" id="summary-2">India activates SPR protocol as crude spikes. Houthi missile targets UAE cargo port — intercepted. Pakistan closes airspace to US military aircraft.</div>
        <div class="rc-devs" id="devs-2">
          <div class="rc-dev"><span class="rc-dev-actor">India</span><span class="rc-dev-hl">SPR protocol activated — HPCL, BPCL, IOC on high alert</span><a class="rc-dev-link" href="https://www.ndtv.com" target="_blank">↗</a></div>
          <div class="rc-dev"><span class="rc-dev-actor">Houthis</span><span class="rc-dev-hl">Missile targeting UAE Jebel Ali port intercepted by Patriot battery</span><a class="rc-dev-link" href="https://www.ndtv.com" target="_blank">↗</a></div>
          <div class="rc-dev"><span class="rc-dev-actor">Pakistan</span><span class="rc-dev-hl">Closes airspace to US military aircraft — cites neutrality</span><a class="rc-dev-link" href="https://www.ndtv.com" target="_blank">↗</a></div>
        </div>
        <div class="rc-foot">
          <span class="rc-foot-stat">17 sources · 4 tiers</span>
          <span class="rc-foot-stat">15 articles processed</span>
        </div>
      </div>

      <div class="rc" style="animation-delay:.2s">
        <div class="rc-top">
          <span class="lv lv-med">Medium</span>
          <span class="rc-ts" id="ts-3">—</span>
          <span class="rc-tone">CAUTIOUS</span>
        </div>
        <div class="rc-summary">Overnight monitoring — no major escalation. Hormuz traffic nominal. UK, France call for emergency UNSC session. Gold at $3,080.</div>
        <div class="rc-devs">
          <div class="rc-dev"><span class="rc-dev-actor">Monitor</span><span class="rc-dev-hl">Hormuz transit nominal — 14 tankers passed 00:00–06:00 UTC</span></div>
          <div class="rc-dev"><span class="rc-dev-actor">UK/France</span><span class="rc-dev-hl">Joint statement calling for emergency UNSC session</span><a class="rc-dev-link" href="https://www.bbc.com" target="_blank">↗</a></div>
        </div>
        <div class="rc-foot">
          <span class="rc-foot-stat">17 sources · 4 tiers</span>
          <span class="rc-foot-stat">9 articles processed</span>
        </div>
      </div>

    </div>
  </div>

  <div class="sidebar">

    <div class="side-card">
      <div class="side-head">Session stats</div>
      <div class="stat-row">
        <div class="stat-item"><span class="stat-name">Total reports</span><span class="stat-val" id="s-total">—</span></div>
        <div class="stat-item"><span class="stat-name">Escalation level</span><span class="stat-val red" id="s-level">—</span></div>
        <div class="stat-item"><span class="stat-name">Last updated</span><span class="stat-val amber" id="s-updated">—</span></div>
        <div class="stat-item"><span class="stat-name">Sources active</span><span class="stat-val green">17 / 17</span></div>
        <div class="stat-item"><span class="stat-name">Overall tone</span><span class="stat-val" id="s-tone">—</span></div>
      </div>
    </div>

    <div class="side-card">
      <div class="side-head">Escalation history</div>
      <div class="chart-wrap" id="chart-wrap">
        <!-- Populated from live_data.js history -->
      </div>
    </div>

    <div class="side-card">
      <div class="side-head">Pipeline status</div>
      <div class="pipeline-row"><span class="pipeline-name">scraper.py</span><span class="pill-ok">OK</span></div>
      <div class="pipeline-row"><span class="pipeline-name">summarizer.py</span><span class="pill-ok">OK</span></div>
      <div class="pipeline-row"><span class="pipeline-name">dashboard.py</span><span class="pill-ok">OK</span></div>
      <div class="pipeline-row"><span class="pipeline-name">emailer.py</span><span class="pill-ok">OK</span></div>
      <div class="pipeline-row"><span class="pipeline-name">GitHub Actions</span><span class="pill-run">Running</span></div>
    </div>

    <div class="side-card">
      <div class="side-head">About</div>
      <div class="about-item"><div class="about-key">bot.py</div><div class="about-val">Runs automatically via GitHub Actions</div></div>
      <div class="about-item"><div class="about-key">scraper.py</div><div class="about-val">17 RSS sources, 4 tiers — wire services, conflict-focused, India, policy</div></div>
      <div class="about-item"><div class="about-key">summarizer.py</div><div class="about-val">AI Summariser — 7-para per development, 5-para India summary, 3-para exec summary</div></div>
      <div class="about-item"><div class="about-key">dashboard.py</div><div class="about-val">Converts reports to live_data.js consumed by all HTML pages</div></div>
      <div class="about-item"><div class="about-key">emailer.py</div><div class="about-val">Gmail SMTP — sends full HTML report on each pipeline update</div></div>
    </div>

  </div>

</div>

<footer>
  <div class="footer-logo">War<span>Watch</span> — Bot Log</div>
  <div class="footer-meta">17 RSS sources · AI Summariser · GitHub Actions<br><a href="index.html" style="color:#444;text-decoration:none">← Back to Live</a></div>
</footer>

<script src="live_data.js" onerror="void 0"></script>
<script>
/* ── Live date ── */
(function(){
  var d=new Date();
  var DAYS=['Sunday','Monday','Tuesday','Wednesday','Thursday','Friday','Saturday'];
  var MONTHS=['January','February','March','April','May','June','July','August','September','October','November','December'];
  document.getElementById('header-date').textContent=DAYS[d.getDay()]+', '+MONTHS[d.getMonth()]+' '+d.getDate()+', '+d.getFullYear();
})();

var D=window.WARWATCH_LIVE;

/* ── Sidebar stats from live_data ── */
if(D){
  if(D.escalationLevel){
    var sl=document.getElementById('s-level');
    if(sl) sl.textContent=D.escalationLevel;
  }
  if(D.generatedAt){
    var su=document.getElementById('s-updated');
    if(su) su.textContent=D.generatedAt;
    var lr=document.getElementById('last-run-txt');
    if(lr) lr.textContent='Last run: '+D.generatedAt;
    /* update first card ts */
    var t0=document.getElementById('ts-0');
    if(t0) t0.textContent=D.generatedAt;
  }
  if(D.totalReports){
    var st=document.getElementById('s-total');
    if(st) st.textContent=D.totalReports;
    var rc=document.getElementById('report-count');
    if(rc) rc.textContent=D.totalReports+' total reports';
    /* arts count */
    var a0=document.getElementById('arts-0');
    if(a0) a0.textContent=(D.heroStats&&D.heroStats.sourcesUsed?D.heroStats.sourcesUsed:17)+' sources used';
  }
  if(D.sentiment&&D.sentiment.overall_tone){
    var sto=document.getElementById('s-tone');
    if(sto) sto.textContent=D.sentiment.overall_tone;
  }

  /* Populate top card from latest report data */
  if(D.execSummaryRich||D.execSummary||D.executive_summary){
    var s0=document.getElementById('summary-0');
    if(s0){
      var txt=D.execSummaryRich||D.execSummary||D.executive_summary;
      s0.textContent=txt.split('\n\n')[0]||txt.slice(0,300);
    }
  }
  if(D.newsCards&&D.newsCards.length){
    var d0=document.getElementById('devs-0');
    if(d0){
      d0.innerHTML=D.newsCards.slice(0,4).map(function(c){
        var link=c.sourceUrl&&c.sourceUrl!='#'?'<a class="rc-dev-link" href="'+c.sourceUrl+'" target="_blank">↗</a>':'';
        return '<div class="rc-dev"><span class="rc-dev-actor">'+(c.actor||c.orgs&&c.orgs[0]||'Monitor')+'</span><span class="rc-dev-hl">'+c.headline+'</span>'+link+'</div>';
      }).join('');
    }
  }

  /* Escalation chart from history */
  var hist=D.history||[];
  if(hist.length){
    var wrap=document.getElementById('chart-wrap');
    if(wrap){
      var recent=hist.slice(-12);
      var LH={CRITICAL:98,HIGH:72,MEDIUM:50,LOW:25};
      var LC={CRITICAL:'#c41e3a',HIGH:'#d4892a',MEDIUM:'#d4892a',LOW:'#3daa72'};
      wrap.innerHTML=recent.map(function(h,i){
        var ht=(LH[h.l]||50)/100*76;
        var col=LC[h.l]||'#555';
        var lbl=h.t?h.t.slice(11,16):'';
        return '<div class="bar-item"><div class="bar-col" style="height:4px;background:'+col+'" data-h="'+ht+'"></div><div class="bar-lbl">'+lbl+'</div></div>';
      }).join('');
      setTimeout(function(){
        wrap.querySelectorAll('.bar-col').forEach(function(b){
          b.style.transition='height .8s cubic-bezier(.4,0,.2,1)';
          b.style.height=b.dataset.h+'px';
        });
      },300);
    }
  }

  /* Populate other card timestamps from history */
  if(hist.length>1){var t1=document.getElementById('ts-1');if(t1) t1.textContent=hist[hist.length-2]&&hist[hist.length-2].t||'';}
  if(hist.length>2){var t2=document.getElementById('ts-2');if(t2) t2.textContent=hist[hist.length-3]&&hist[hist.length-3].t||'';}
  if(hist.length>3){var t3=document.getElementById('ts-3');if(t3) t3.textContent=hist[hist.length-4]&&hist[hist.length-4].t||'';}
}

/* Animate cards */
window.addEventListener('load',function(){
  document.querySelectorAll('.rc').forEach(function(el,i){
    var delay=parseFloat(el.style.animationDelay)||0;
    el.style.opacity='0'; el.style.transform='translateY(8px)';
    setTimeout(function(){
      el.style.transition='opacity .35s ease,transform .35s ease';
      el.style.opacity='1'; el.style.transform='translateY(0)';
    },100+delay*1000);
  });
});
</script>
</body>
</html>