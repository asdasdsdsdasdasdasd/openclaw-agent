#!/usr/bin/env node
const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');

const BASE = __dirname;
const SENT_FILE = path.join(BASE, 'sent-applications.json');
const REJ_JSONL = path.join(BASE, 'rejected-leads.log.jsonl');
const REJ_JSON = path.join(BASE, 'rejected-leads.json');
const PROFILE = JSON.parse(fs.readFileSync(path.join(BASE, 'candidate-profile.json'), 'utf8'));

let sentC = 0, sentJ = [];
let rejUrls = new Set(), sentUrls = new Set();

// Load state
try { const d = JSON.parse(fs.readFileSync(SENT_FILE,'utf8')); sentC = d.sent_count||0; sentJ = d.sent_jobs||[]; sentJ.forEach(j => sentUrls.add(j.url)); } catch(_) {}
try { const a = JSON.parse(fs.readFileSync(REJ_JSON,'utf8')||'[]'); a.forEach(r => rejUrls.add(r.url)); } catch(_) {}

function genCL(title, company) {
  const edu = PROFILE.education || [];
  const skills = PROFILE.skills || [];
  const eduStr = edu.map(e => `${e.degree} in ${e.field} at ${e.institution}`).join(' and ');
  const skillStr = skills.join(', ');
  const t = title.toLowerCase();
  let extra = 'I am eager to apply my AI and machine learning knowledge to solve real-world problems.';
  if (t.includes('llm') || t.includes('nlp') || t.includes('language')) extra = 'I have strong NLP skills and experience with transformer architectures, making me well-suited for LLM development work.';
  else if (t.includes('agent') || t.includes('builder')) extra = 'I am passionate about AI Agents, workflow automation, and prompt engineering concepts such as Agentic AI and RAG.';
  else if (t.includes('vision')) extra = 'I have hands-on experience with deep learning models including ResNet for computer vision tasks.';
  else if (t.includes('engineer') || t.includes('developer')) extra = 'I have hands-on experience developing and deploying AI/ML models in production environments.';
  else if (t.includes('architect')) extra = 'I have a strong foundation in system design and AI architecture from my academic and project experience.';
  else if (t.includes('teacher') || t.includes('coach') || t.includes('mentor')) extra = 'I have experience teaching Python programming to students and explaining complex technical concepts clearly.';
  else if (t.includes('research') || t.includes('scientist')) extra = 'My academic background in AI research and hands-on project experience make me well-suited for this role.';
  return `Dear Hiring Team,\n\nI am writing to express my strong interest in the ${title} position at ${company}. As a ${eduStr}, I am excited to bring my technical expertise and passion for AI to your team.\n\n${extra}\n\nMy academic projects include building a Go AI using ResNet and Monte Carlo Tree Search, and conducting spatial-temporal sentiment analysis on Yelp review data. I have hands-on experience with ${skillStr}. I am a quick learner, a strong problem-solver, and fluent in English, Putonghua, and Cantonese.\n\nThank you for considering my application.\n\nBest regards,\n${PROFILE.name || PROFILE.fullName || 'Candidate'}\n\nNote: This email is automatically generated and sent by openclaw.`;
}

function saveSent(job) {
  sentC++; sentJ.push({timestamp: new Date().toISOString(), company: job.company, role: job.title, url: `https://hk.jobsdb.com/job/${job.jobId}`, action: 'sent'});
  fs.writeFileSync(SENT_FILE, JSON.stringify({sent_count: sentC, sent_jobs: sentJ}, null, 2));
  console.log(`✅ (${sentC}/50) ${job.title} @ ${job.company}`);
}
function saveRej(job, reason) {
  const e = {timestamp: new Date().toISOString(), company: job.company, role: job.title, url: `https://hk.jobsdb.com/job/${job.jobId}`, reason, action: 'rejected'};
  fs.appendFileSync(REJ_JSONL, JSON.stringify(e) + '\n');
  try { const a = JSON.parse(fs.readFileSync(REJ_JSON,'utf8')||'[]'); a.push(e); fs.writeFileSync(REJ_JSON, JSON.stringify(a,null,2)); } catch(_) { fs.writeFileSync(REJ_JSON, JSON.stringify([e],null,2)); }
  console.log(`❌ ${job.title} @ ${job.company} (${reason})`);
}

async function getTab() {
  const r = await fetch('http://127.0.0.1:9222/json');
  const tabs = await r.json();
  let tab = tabs.find(x => x.url && x.url.includes('jobsdb.com') && !x.url.includes('static'));
  if (!tab) tab = tabs.find(x => x.url && x.url.includes('jobsdb'));
  if (!tab) tab = tabs[0];
  return tab;
}

class Bot {
  constructor() { this.ws = null; this._id = 1; this._cbs = new Map(); this._navR = null; this._tabId = null; }
  
  async connect() {
    const tab = await getTab();
    this._tabId = tab.id;
    console.log('Tab:', (tab.url||'').substring(0,80));
    this.ws = new WebSocket(tab.webSocketDebuggerUrl);
    return new Promise((ok, fail) => {
      this.ws.on('open', ok);
      this.ws.on('error', fail);
      this.ws.on('message', d => {
        const m = JSON.parse(d.toString());
        if (m.id && this._cbs.has(m.id)) { this._cbs.get(m.id)(m); this._cbs.delete(m.id); }
        if (m.method==='Page.frameStoppedLoading' && this._navR) { this._navR(); this._navR = null; }
      });
    });
  }

  async reconnect() {
    if (this.ws) { try { this.ws.close(); } catch(_) {} }
    await this.connect();
  }

  s(ms) { return new Promise(r => setTimeout(r, ms)); }
  
  async send(method, params={}) {
    return new Promise((ok, fail) => {
      const id = this._id++;
      this._cbs.set(id, r => { if (r.error) fail(new Error(r.error.message)); else ok(r.result); });
      this.ws.send(JSON.stringify({id, method, params}));
    });
  }

  async goto(url) {
    try {
      await this.send('Page.enable');
      await this.send('Runtime.enable');
      await this.send('DOM.enable');
    } catch(_) {}
    return new Promise(ok => {
      const t = setTimeout(() => { this._navR = null; ok(); }, 10000);
      this._navR = () => { clearTimeout(t); setTimeout(ok, 500); };
      this.send('Page.navigate', {url}).catch(() => { clearTimeout(t); ok(); });
    });
  }

  async nav(url) { try { await this.goto(url); } catch(_) {} await this.s(2000); }

  async e(expr) {
    try {
      const r = await this.send('Runtime.evaluate', {expression: expr, returnByValue: true, awaitPromise: true, timeout: 5000});
      if (r.exceptionDetails) return null;
      return r.result.value;
    } catch(_) { return null; }
  }

  async url() { return (await this.e('window.location.href')) || ''; }
  async text() { return (await this.e('document.body?.innerText || ""')) || ''; }

  async clickBtnContaining(txt) {
    return this.e(`(() => { const t = ${JSON.stringify(txt)}.toLowerCase(); for (const b of document.querySelectorAll('button')) { if (b.textContent.trim().toLowerCase().includes(t)) { b.scrollIntoView(); b.click(); return true; } } return false; })()`);
  }

  async fillTA(text) {
    return this.e(`(() => { const el = document.querySelector('textarea'); if (!el) return false; const s = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, "value").set; s.call(el, ${JSON.stringify(text)}); el.dispatchEvent(new Event("input", {bubbles:true})); el.dispatchEvent(new Event("change", {bubbles:true})); return true; })()`);
  }

  async asyncApply(job) {
    const jUrl = `https://hk.jobsdb.com/job/${job.jobId}`;
    if (rejUrls.has(jUrl) || sentUrls.has(jUrl)) return;
    console.log(`\n▶ ${job.title} @ ${job.company}`);

    // Navigate directly to apply page
    await this.nav(jUrl + '/apply');
    let txt = await this.text();
    let u = await this.url();

    // Check for expired
    if (u.includes('apps.apple.com') || txt.includes('no longer') || txt.includes('not found')) {
      saveRej(job, 'expired'); return;
    }

    // If redirected to detail page (no /apply in URL), click Quick apply
    if (!u.includes('/apply')) {
      const cl = await this.e(`document.querySelector('a[href*="/apply"][class*="quick"]')?.href || document.querySelector('a[href*="/apply"]')?.href || ''`);
      if (cl) { await this.nav(cl); await this.s(1500); u = await this.url(); }
      else { saveRej(job, 'no_apply'); return; }
    }

    // Progressive flow handler
    let seen = new Set(), rounds = 0;
    while (rounds++ < 12) {
      u = await this.url(); txt = await this.text();
      
      // Terminals
      if (u.includes('apps.apple.com') || txt.includes('no longer') || txt.includes('not found')) { saveRej(job, 'expired'); return; }
      if (u.includes('/apply/success') || txt.includes('application has been submitted')) { saveSent(job); return; }
      if (u.includes('/my-activity/applied') || (txt.includes('applied on jobsdb') && txt.includes('applied'))) { saveSent(job); return; }
      
      // Loop cutoff
      if (seen.has(u)) {
        await this.clickBtnContaining('Continue') || await this.clickBtnContaining('Submit');
        await this.s(2000);
        if ((await this.url()).includes('/apply/success') || (await this.text()).includes('application has been')) { saveSent(job); return; }
        saveRej(job, 'loop'); return;
      }
      seen.add(u);

      // REVIEW: Submit application
      if (u.includes('/review') || txt.includes('Submit application')) {
        const ok = await this.e(`(() => { for (const b of document.querySelectorAll('button')) { if (b.textContent.trim().includes('Submit application')) { b.scrollIntoView(); b.click(); return true; } } return false; })()`);
        if (ok) {
          await this.s(4000);
          u = await this.url(); txt = await this.text();
          if (u.includes('/apply/success') || u.includes('/my-activity') || u.includes('/companies') || txt.includes('applied')) { saveSent(job); return; }
          saveRej(job, 'submit_fail'); return;
        }
        saveRej(job, 'no_submit'); return;
      }

      // EMPLOYER QUESTIONS
      if (u.includes('/role-requirements') || txt.includes('right to work')) {
        await this.e(`(() => { const rr = document.querySelectorAll('input[type="radio"]'); for (const r of rr) { if (r.offsetParent !== null) { r.scrollIntoView(); r.click(); r.dispatchEvent(new Event('change',{bubbles:true})); break; } } })()`);
        await this.s(200);
        await this.e(`(() => { for (const s of document.querySelectorAll('select')) { for (const o of s.options) { if (o.textContent.includes('2 weeks')) { s.value = o.value; s.dispatchEvent(new Event('change',{bubbles:true})); return; } } } })()`);
        await this.s(200);
        await this.clickBtnContaining('Continue');
        await this.s(1500); continue;
      }

      // PROFILE PAGE
      if (txt.includes('Your Jobsdb Profile is part')) {
        await this.clickBtnContaining('Continue');
        await this.s(1500); continue;
      }

      // DOCUMENTS - fill cover letter if textarea
      const hasTA = await this.e('!!document.querySelector("textarea")');
      if (hasTA) {
        await this.fillTA(genCL(job.title, job.company));
        await this.s(300);
      }

      // Click Continue/Next
      if (await this.clickBtnContaining('Continue') || await this.clickBtnContaining('Next')) {
        await this.s(1500); continue;
      }

      // Back at detail page - click apply again
      if (txt.includes('Quick apply') || txt.includes('Save')) {
        const cl = await this.e(`document.querySelector('a[href*="/apply"]')?.href || ''`);
        if (cl) { await this.nav(cl); await this.s(1500); continue; }
      }

      console.log(`  ? ${u.substring(0,80)}`);
      saveRej(job, 'unknown'); return;
    }
    saveRej(job, 'max_iter');
  }
}

async function scrapeJobs(d, url, label) {
  await d.nav(url);
  await this.s(2000);
  await d.s(1500);
  const jobs = await d.e(`(() => { const s = new Set(), r = []; document.querySelectorAll('article').forEach(art => { 
    const link = art.querySelector('a[href*="/job/"]');
    if (!link) return;
    const m = link.href.match(/\\/job\\/(\\d+)/);
    if (!m || s.has(m[1])) return;
    s.add(m[1]);
    const h = art.querySelector('h3');
    const t = h ? h.textContent.trim() : '';
    r.push({ id: m[1], t });
  }); return r; })()`);
  return jobs || [];
}

async function main() {
  console.log(`State: ${sentC} sent, ${rejUrls.size} rejected`);
  if (sentC >= 50) { console.log('Already at target!'); return; }

  const d = new Bot();
  await d.connect();
  console.log('Connected\n');

  // Scrape live from ML search - find AI-title jobs
  await d.nav('https://hk.jobsdb.com/machine-learning-jobs');
  await d.s(2000);
  
  // Get all job articles with their IDs and titles
  let jobs = await d.e(`(() => { const s = new Set(), r = []; document.querySelectorAll('article').forEach(art => { 
    const link = art.querySelector('a[href*="/job/"]');
    if (!link) return;
    const m = link.href.match(/\\/job\\/(\\d+)/);
    if (!m || s.has(m[1])) return;
    s.add(m[1]);
    const h = art.querySelector('h3');
    const t = h ? h.textContent.trim() : '';
    r.push({ id: m[1], t });
  }); return r; })()`);
  
  if (!jobs) jobs = [];
  console.log(`ML search: ${jobs.length} jobs found`);

  // Filter to AI-titled only (bypass rule)
  const aiJobs = jobs.filter(j => j.t.toLowerCase().includes('ai') && !j.t.toLowerCase().includes('data'));
  console.log(`AI-title bypass candidates: ${aiJobs.length}`);

  // Process each
  for (const j of aiJobs) {
    if (sentC >= 50) break;
    const jUrl = `https://hk.jobsdb.com/job/${j.id}`;
    if (rejUrls.has(jUrl) || sentUrls.has(jUrl)) continue;

    // Get full details
    await d.nav(`https://hk.jobsdb.com/job/${j.id}`);
    await d.s(1000);
    const u = await d.url();
    const txt = await d.text();
    if (u.includes('apps.apple.com') || txt.includes('not found') || txt.includes('no longer')) {
      saveRej({jobId: j.id, title: j.t, company: 'Unknown'}, 'expired'); continue;
    }
    const title = (await d.e(`document.querySelector('h1')?.textContent?.trim() || ''`)) || j.t;
    const company = await d.e(`document.querySelector('[data-automation="advertiserName"]')?.textContent?.trim() || document.querySelector('[data-automation="jobAdvertiser"]')?.textContent?.trim() || ''`);
    
    await d.asyncApply({jobId: j.id, title, company});
    await d.s(500);
  }

  // ML page 2
  if (sentC < 50) {
    console.log('\n--- ML Page 2 ---');
    await d.nav('https://hk.jobsdb.com/machine-learning-jobs?page=2');
    await d.s(2000);
    let jobs2 = await d.e(`(() => { const s = new Set(), r = []; document.querySelectorAll('article').forEach(art => { 
      const link = art.querySelector('a[href*="/job/"]');
      if (!link) return;
      const m = link.href.match(/\\/job\\/(\\d+)/);
      if (!m || s.has(m[1])) return;
      s.add(m[1]);
      const h = art.querySelector('h3');
      const t = h ? h.textContent.trim() : '';
      r.push({ id: m[1], t });
    }); return r; })()`);
    if (!jobs2) jobs2 = [];
    const ai2 = jobs2.filter(j => j.t.toLowerCase().includes('ai') && !j.t.toLowerCase().includes('data'));
    for (const j of ai2) {
      if (sentC >= 50) break;
      const jUrl = `https://hk.jobsdb.com/job/${j.id}`;
      if (rejUrls.has(jUrl) || sentUrls.has(jUrl)) continue;
      await d.nav(`https://hk.jobsdb.com/job/${j.id}`); await d.s(800);
      const u = await d.url(); const txt = await d.text();
      if (u.includes('apps.apple.com') || txt.includes('not found') || txt.includes('no longer')) { saveRej({jobId:j.id,title:j.t,company:''},'expired'); continue; }
      const title = (await d.e(`document.querySelector('h1')?.textContent?.trim()||''`)) || j.t;
      const company = await d.e(`document.querySelector('[data-automation="advertiserName"]')?.textContent?.trim()||document.querySelector('[data-automation="jobAdvertiser"]')?.textContent?.trim()||''`);
      await d.asyncApply({jobId: j.id, title, company}); await d.s(500);
    }
  }

  // Switch to ai-engineer
  if (sentC < 50) {
    console.log('\n--- AI Engineer search ---');
    await d.nav('https://hk.jobsdb.com/ai-engineer-jobs');
    await d.s(2000);
    let je = await d.e(`(() => { const s = new Set(), r = []; document.querySelectorAll('article').forEach(art => { 
      const link = art.querySelector('a[href*="/job/"]');
      if (!link) return;
      const m = link.href.match(/\\/job\\/(\\d+)/);
      if (!m || s.has(m[1])) return;
      s.add(m[1]);
      const h = art.querySelector('h3');
      const t = h ? h.textContent.trim() : '';
      r.push({ id: m[1], t });
    }); return r; })()`);
    if (!je) je = [];
    for (const j of je) {
      if (sentC >= 50) break;
      const jUrl = `https://hk.jobsdb.com/job/${j.id}`;
      if (rejUrls.has(jUrl) || sentUrls.has(jUrl)) continue;
      await d.nav(`https://hk.jobsdb.com/job/${j.id}`); await d.s(800);
      const u = await d.url(); const txt = await d.text();
      if (u.includes('apps.apple.com') || txt.includes('not found') || txt.includes('no longer')) { saveRej({jobId:j.id,title:j.t,company:''},'expired'); continue; }
      const title = (await d.e(`document.querySelector('h1')?.textContent?.trim()||''`)) || j.t;
      const company = await d.e(`document.querySelector('[data-automation="advertiserName"]')?.textContent?.trim()||document.querySelector('[data-automation="jobAdvertiser"]')?.textContent?.trim()||''`);
      await d.asyncApply({jobId: j.id, title, company}); await d.s(500);
    }
  }

  // AI Engineer page 2
  if (sentC < 50) {
    console.log('\n--- AI Engineer Page 2 ---');
    await d.nav('https://hk.jobsdb.com/ai-engineer-jobs?page=2');
    await d.s(2000);
    let je2 = await d.e(`(() => { const s = new Set(), r = []; document.querySelectorAll('article').forEach(art => { 
      const link = art.querySelector('a[href*="/job/"]');
      if (!link) return;
      const m = link.href.match(/\\/job\\/(\\d+)/);
      if (!m || s.has(m[1])) return;
      s.add(m[1]);
      const h = art.querySelector('h3');
      const t = h ? h.textContent.trim() : '';
      r.push({ id: m[1], t });
    }); return r; })()`);
    if (!je2) je2 = [];
    for (const j of je2) {
      if (sentC >= 50) break;
      const jUrl = `https://hk.jobsdb.com/job/${j.id}`;
      if (rejUrls.has(jUrl) || sentUrls.has(jUrl)) continue;
      await d.nav(`https://hk.jobsdb.com/job/${j.id}`); await d.s(800);
      const u = await d.url(); const txt = await d.text();
      if (u.includes('apps.apple.com') || txt.includes('not found') || txt.includes('no longer')) { saveRej({jobId:j.id,title:j.t,company:''},'expired'); continue; }
      const title = (await d.e(`document.querySelector('h1')?.textContent?.trim()||''`)) || j.t;
      const company = await d.e(`document.querySelector('[data-automation="advertiserName"]')?.textContent?.trim()||document.querySelector('[data-automation="jobAdvertiser"]')?.textContent?.trim()||''`);
      await d.asyncApply({jobId: j.id, title, company}); await d.s(500);
    }
  }

  // LLM Developer
  if (sentC < 50) {
    console.log('\n--- LLM Developer ---');
    await d.nav('https://hk.jobsdb.com/llm-developer-jobs');
    await d.s(2000);
    let jl = await d.e(`(() => { const s = new Set(), r = []; document.querySelectorAll('article').forEach(art => { 
      const link = art.querySelector('a[href*="/job/"]');
      if (!link) return;
      const m = link.href.match(/\\/job\\/(\\d+)/);
      if (!m || s.has(m[1])) return;
      s.add(m[1]);
      const h = art.querySelector('h3');
      const t = h ? h.textContent.trim() : '';
      r.push({ id: m[1], t });
    }); return r; })()`);
    if (!jl) jl = [];
    for (const j of jl) {
      if (sentC >= 50) break;
      const jUrl = `https://hk.jobsdb.com/job/${j.id}`;
      if (rejUrls.has(jUrl) || sentUrls.has(jUrl)) continue;
      await d.nav(`https://hk.jobsdb.com/job/${j.id}`); await d.s(800);
      const u = await d.url(); const txt = await d.text();
      if (u.includes('apps.apple.com') || txt.includes('not found') || txt.includes('no longer')) { saveRej({jobId:j.id,title:j.t,company:''},'expired'); continue; }
      const title = (await d.e(`document.querySelector('h1')?.textContent?.trim()||''`)) || j.t;
      const company = await d.e(`document.querySelector('[data-automation="advertiserName"]')?.textContent?.trim()||document.querySelector('[data-automation="jobAdvertiser"]')?.textContent?.trim()||''`);
      await d.asyncApply({jobId: j.id, title, company}); await d.s(500);
    }
  }

  // ML page 3
  if (sentC < 50) {
    console.log('\n--- ML Page 3 ---');
    await d.nav('https://hk.jobsdb.com/machine-learning-jobs?page=3');
    await d.s(2000);
    let j3 = await d.e(`(() => { const s = new Set(), r = []; document.querySelectorAll('article').forEach(art => { 
      const link = art.querySelector('a[href*="/job/"]');
      if (!link) return;
      const m = link.href.match(/\\/job\\/(\\d+)/);
      if (!m || s.has(m[1])) return;
      s.add(m[1]);
      const h = art.querySelector('h3');
      const t = h ? h.textContent.trim() : '';
      r.push({ id: m[1], t });
    }); return r; })()`);
    if (!j3) j3 = [];
    for (const j of j3) {
      if (sentC >= 50) break;
      const jUrl = `https://hk.jobsdb.com/job/${j.id}`;
      if (rejUrls.has(jUrl) || sentUrls.has(jUrl)) continue;
      await d.nav(`https://hk.jobsdb.com/job/${j.id}`); await d.s(800);
      const u = await d.url(); const txt = await d.text();
      if (u.includes('apps.apple.com') || txt.includes('not found') || txt.includes('no longer')) { saveRej({jobId:j.id,title:j.t,company:''},'expired'); continue; }
      const title = (await d.e(`document.querySelector('h1')?.textContent?.trim()||''`)) || j.t;
      const company = await d.e(`document.querySelector('[data-automation="advertiserName"]')?.textContent?.trim()||document.querySelector('[data-automation="jobAdvertiser"]')?.textContent?.trim()||''`);
      await d.asyncApply({jobId: j.id, title, company}); await d.s(500);
    }
  }

  console.log(`\n=== FINAL: ${sentC}/50 ===`);
  console.log(JSON.stringify(sentJ.map(j => `${j.role} @ ${j.company}`), null, 2));
}

main().catch(err => { console.error('FATAL:', err); process.exit(1); });
