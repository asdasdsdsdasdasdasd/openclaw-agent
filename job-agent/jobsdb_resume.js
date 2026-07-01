#!/usr/bin/env node
/**
 * Resume script - continues from where last run stopped
 * Goes deeper: page 4-5, more keywords
 */
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
  else if (t.includes('research') || t.includes('scientist')) extra = 'My academic background in AI research and hands-on project experience make me well-suited for this role.';
  else if (t.includes('analyst') || t.includes('data')) extra = 'I have strong analytical skills and experience working with data pipelines, ML models, and deriving insights from complex datasets.';
  return `Dear Hiring Team,\n\nI am writing to express my strong interest in the ${title} position at ${company}. As a ${eduStr}, I am excited to bring my technical expertise and passion for AI to your team.\n\n${extra}\n\nMy academic projects include building a Go AI using ResNet and Monte Carlo Tree Search, and conducting spatial-temporal sentiment analysis on Yelp review data. I have hands-on experience with ${skillStr}. I am a quick learner, a strong problem-solver, and fluent in English, Putonghua, and Cantonese.\n\nThank you for considering my application.\n\nBest regards,\n${PROFILE.name || PROFILE.fullName || 'Candidate'}\n\nNote: This email is automatically generated and sent by openclaw.`;
}

function saveSent(job) {
  sentC++; sentJ.push({timestamp: new Date().toISOString(), company: job.company||'', role: job.title||'', url: `https://hk.jobsdb.com/job/${job.jobId}`, action: 'sent'});
  fs.writeFileSync(SENT_FILE, JSON.stringify({sent_count: sentC, sent_jobs: sentJ}, null, 2));
  console.log(`✅ (${sentC}/50) ${(job.title||'').substring(0,40)} @ ${(job.company||'').substring(0,30)}`);
}
function saveRej(job, reason) {
  const e = {timestamp: new Date().toISOString(), company: job.company||'', role: job.title||'', url: `https://hk.jobsdb.com/job/${job.jobId}`, reason, action: 'rejected'};
  fs.appendFileSync(REJ_JSONL, JSON.stringify(e)+'\n');
  try { const a = JSON.parse(fs.readFileSync(REJ_JSON,'utf8')||'[]'); a.push(e); fs.writeFileSync(REJ_JSON, JSON.stringify(a,null,2)); } catch(_) { fs.writeFileSync(REJ_JSON, JSON.stringify([e],null,2)); }
}

async function getTab() {
  const r = await fetch('http://127.0.0.1:9222/json');
  const tabs = await r.json();
  let tab = tabs.find(x => x.url && x.url.includes('jobsdb.com') && !x.url.includes('static'));
  if (!tab) tab = tabs[0];
  return tab;
}

class Bot {
  async connect() {
    const tab = await getTab();
    console.log('Tab:', (tab.url||'').substring(0,80));
    this.ws = new WebSocket(tab.webSocketDebuggerUrl);
    this._id = 1; this._cbs = new Map(); this._navR = null;
    return new Promise((ok,fail)=>{this.ws.on('open',ok);this.ws.on('error',fail);this.ws.on('message',d=>{const m=JSON.parse(d.toString());if(m.id&&this._cbs.has(m.id)){this._cbs.get(m.id)(m);this._cbs.delete(m.id);}if(m.method==='Page.frameStoppedLoading'&&this._navR){this._navR();this._navR=null;}});});
  }
  s(ms){return new Promise(r=>setTimeout(r,ms));}
  async send(method,params={}){return new Promise((ok,fail)=>{const id=this._id++;this._cbs.set(id,r=>{if(r.error)fail(new Error(r.error.message));else ok(r.result);});this.ws.send(JSON.stringify({id,method,params}));});}
  async goto(url){try{await this.send('Page.enable');await this.send('Runtime.enable');await this.send('DOM.enable');}catch(_){}return new Promise(ok=>{const t=setTimeout(()=>{this._navR=null;ok();},8000);this._navR=()=>{clearTimeout(t);setTimeout(ok,400);};this.send('Page.navigate',{url}).catch(()=>{clearTimeout(t);ok();});});}
  async nav(url){try{await this.goto(url);}catch(_){}await this.s(2000);}
  async e(expr){try{const r=await this.send('Runtime.evaluate',{expression:expr,returnByValue:true,awaitPromise:true,timeout:5000});if(r.exceptionDetails)return null;return r.result.value;}catch(_){return null;}}
  async url(){return(await this.e('window.location.href'))||'';}
  async text(){return(await this.e('document.body?.innerText||""'))||'';}
  async clickBtn(t){return this.e(`(()=>{const t=${JSON.stringify(t)}.toLowerCase();for(const b of document.querySelectorAll('button')){if(b.textContent.trim().toLowerCase().includes(t)){b.scrollIntoView();b.click();return true;}}return false;})()`);}
  async fillTA(text){return this.e(`(()=>{const el=document.querySelector('textarea');if(!el)return false;const s=Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype,"value").set;s.call(el,${JSON.stringify(text)});el.dispatchEvent(new Event("input",{bubbles:true}));el.dispatchEvent(new Event("change",{bubbles:true}));return true;})()`);}

  async applyOne(job) {
    const jUrl = `https://hk.jobsdb.com/job/${job.jobId}`;
    if (rejUrls.has(jUrl) || sentUrls.has(jUrl)) return;
    console.log(`\n▶ ${(job.title||'').substring(0,40)} @ ${(job.company||'').substring(0,30)}`);

    await this.nav(jUrl + '/apply');
    let txt = await this.text(); let u = await this.url();
    if (u.includes('apps.apple.com') || txt.includes('no longer') || txt.includes('not found')) { saveRej(job,'expired'); return; }
    if (!u.includes('/apply')) {
      const cl = await this.e(`document.querySelector('a[href*="/apply"]')?.href||''`);
      if (cl) { await this.nav(cl); await this.s(1500); u = await this.url(); } else { saveRej(job,'no_apply'); return; }
    }

    let seen = new Set(), rounds = 0;
    while (rounds++ < 12) {
      u = await this.url(); txt = await this.text();
      if (u.includes('apps.apple.com')||txt.includes('no longer')||txt.includes('not found')){saveRej(job,'expired');return;}
      if (u.includes('/apply/success')||txt.includes('application has been submitted')){saveSent(job);return;}
      if ((txt.includes('applied')&&txt.includes('jobsdb'))||u.includes('/my-activity')){saveSent(job);return;}
      if (seen.has(u)){await this.clickBtn('Continue')||await this.clickBtn('Submit');await this.s(2000);if((await this.url()).includes('/apply/success')){saveSent(job);return;}saveRej(job,'loop');return;}seen.add(u);

      if (u.includes('/review')||txt.includes('Submit application')){
        const ok = await this.e(`(()=>{for(const b of document.querySelectorAll('button')){if(b.textContent.trim().includes('Submit application')){b.scrollIntoView();b.click();return true;}}return false;})()`);
        if(ok){await this.s(4000);u=await this.url();txt=await this.text();if(u.includes('/apply/success')||u.includes('/my-activity')||u.includes('/companies')||txt.includes('applied')){saveSent(job);return;}saveRej(job,'submit_fail');return;}
        saveRej(job,'no_submit');return;
      }
      if (u.includes('/role-requirements')||txt.includes('right to work')){
        await this.e(`(()=>{const rr=document.querySelectorAll('input[type="radio"]');for(const r of rr){if(r.offsetParent!==null){r.scrollIntoView();r.click();r.dispatchEvent(new Event('change',{bubbles:true}));break;}}})()`);
        await this.s(200); await this.e(`(()=>{for(const s of document.querySelectorAll('select')){for(const o of s.options){if(o.textContent.includes('2 weeks')){s.value=o.value;s.dispatchEvent(new Event('change',{bubbles:true}));return;}}}})()`);
        await this.s(200); await this.clickBtn('Continue'); await this.s(1500); continue;
      }
      if(txt.includes('Your Jobsdb Profile is part')){await this.clickBtn('Continue');await this.s(1500);continue;}
      const hasTA=await this.e('!!document.querySelector("textarea")');
      if(hasTA){await this.fillTA(genCL(job.title,job.company));await this.s(300);}
      if(await this.clickBtn('Continue')||await this.clickBtn('Next')){await this.s(1500);continue;}
      const cl2=await this.e(`document.querySelector('a[href*="/apply"]')?.href||''`);
      if(cl2){await this.nav(cl2);await this.s(1500);continue;}
      console.log(`  ? ${u.substring(0,70)}`);saveRej(job,'unknown');return;
    }
    saveRej(job,'max_iter');
  }
}

async function processKeyword(d, keyword, label) {
  console.log(`\n=== ${label} ===`);
  // Pages 1-5
  for (let page = 1; page <= 5; page++) {
    if (sentC >= 50) return;
    const url = page === 1 ? `https://hk.jobsdb.com/${keyword}-jobs` : `https://hk.jobsdb.com/${keyword}-jobs?page=${page}`;
    await d.nav(url);
    await d.s(2000);
    
    const jobs = await d.e(`(()=>{const s=new Set(),r=[];document.querySelectorAll('article').forEach(art=>{const link=art.querySelector('a[href*="/job/"]');if(!link)return;const m=link.href.match(/\\/job\\/(\\d+)/);if(!m||s.has(m[1]))return;s.add(m[1]);const h=art.querySelector('h3');const t=h?h.textContent.trim():'';r.push({id:m[1],t});});return r;})()`);
    if (!jobs || jobs.length === 0) { console.log(`  Page ${page}: no jobs`); break; }
    console.log(`  Page ${page}: ${jobs.length} jobs`);
    
    for (const j of jobs) {
      if (sentC >= 50) return;
      const jUrl = `https://hk.jobsdb.com/job/${j.id}`;
      if (rejUrls.has(jUrl) || sentUrls.has(jUrl)) continue;
      
      await d.nav(`https://hk.jobsdb.com/job/${j.id}`); await d.s(800);
      const u = await d.url(); const txt = await d.text();
      if (u.includes('apps.apple.com')||txt.includes('not found')||txt.includes('no longer')){saveRej({jobId:j.id,title:j.t,company:''},'expired');continue;}
      const title = (await d.e(`document.querySelector('h1')?.textContent?.trim()||''`))||j.t;
      const company = await d.e(`document.querySelector('[data-automation="advertiserName"]')?.textContent?.trim()||document.querySelector('[data-automation="jobAdvertiser"]')?.textContent?.trim()||document.querySelector('button[data-automation="advertiserName"]')?.textContent?.trim()||''`);
      
      const comp = company || (j.t || '');
      await d.applyOne({jobId: j.id, title, company: comp});
      await d.s(300);
    }
  }
}

async function main() {
  console.log(`State: ${sentC} sent, ${rejUrls.size} rejected, target 50`);
  if (sentC >= 50) { console.log('Already at target!'); return; }

  const d = new Bot();
  await d.connect();
  console.log('Connected\n');

  // Scan remaining pages + additional keywords
  const searches = [
    { k: 'machine-learning', l: 'Machine Learning (pages 4-5)' },
    { k: 'ai-engineer', l: 'AI Engineer (pages 4-5)' },
    { k: 'artificial-intelligence', l: 'Artificial Intelligence' },
    { k: 'computer-vision', l: 'Computer Vision' },
    { k: 'llm-developer', l: 'LLM Developer (pages 3-5)' },
  ];

  for (const s of searches) {
    if (sentC >= 50) break;
    await processKeyword(d, s.k, s.l);
  }

  console.log(`\n=== FINAL: ${sentC}/50 ===`);
  console.log(JSON.stringify(sentJ.map(j => `${j.role} @ ${j.company}`).filter(Boolean), null, 2));
}

main().catch(err => { console.error('FATAL:', err); process.exit(1); });
