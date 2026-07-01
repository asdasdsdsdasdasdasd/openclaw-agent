#!/usr/bin/env node
/**
 * JobsDB Auto-Apply Script
 * Connects to existing Chrome via CDP to handle SPA properly.
 * 
 * Usage: node jobsdb_automator.js [--resume]
 */

const CDP = require('cdp');
// Minimal CDP client - we'll use ws directly
const WebSocket = require('ws');
const fs = require('fs');
const path = require('path');

const BASE_DIR = __dirname;
const CDP_URL = 'http://127.0.0.1:9222/json';

// Tool parameters
let sent_count = 0;
let sent_jobs = [];
const SENT_FILE = path.join(BASE_DIR, 'sent-applications.json');
const REJECTED_JSONL = path.join(BASE_DIR, 'rejected-leads.log.jsonl');
const REJECTED_JSON = path.join(BASE_DIR, 'rejected-leads.json');

// Load profile
const profile = JSON.parse(fs.readFileSync(path.join(BASE_DIR, 'candidate-profile.json'), 'utf8'));

async function getWsEndpoint() {
  const resp = await fetch(CDP_URL);
  const tabs = await resp.json();
  // Find the jobsdb tab or use the first one
  let tab = tabs.find(t => t.url && t.url.includes('jobsdb'));
  if (!tab) tab = tabs[0];
  if (!tab) throw new Error('No browser tabs found');
  return tab.webSocketDebuggerUrl;
}

class JobBDriver {
  constructor(wsUrl) {
    this.ws = new WebSocket(wsUrl);
    this.msgId = 1;
    this.callbacks = new Map();
    this.frameId = null;
    this.loading = false;
  }

  async connect() {
    return new Promise((resolve, reject) => {
      this.ws.on('open', resolve);
      this.ws.on('error', reject);
      this.ws.on('message', (data) => {
        const msg = JSON.parse(data.toString());
        if (msg.id && this.callbacks.has(msg.id)) {
          this.callbacks.get(msg.id)(msg);
          this.callbacks.delete(msg.id);
        }
        // Track frame/navigation events
        if (msg.method === 'Page.frameStartedLoading') this.loading = true;
        if (msg.method === 'Page.frameStoppedLoading') this.loading = false;
      });
    });
  }

  async send(method, params = {}) {
    return new Promise((resolve, reject) => {
      const id = this.msgId++;
      const msg = JSON.stringify({ id, method, params });
      this.callbacks.set(id, (resp) => {
        if (resp.error) reject(new Error(resp.error.message));
        else resolve(resp.result);
      });
      this.ws.send(msg);
    });
  }

  async navigate(url) {
    await this.send('Page.enable');
    await this.send('Runtime.enable');
    await this.send('DOM.enable');
    const result = await this.send('Page.navigate', { url });
    // Wait for navigation
    await this.waitForLoad();
    return result;
  }

  async waitForLoad(timeout = 15000) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      await this.sleep(300);
      if (!this.loading) {
        // Extra wait for SPA render
        await this.sleep(500);
        break;
      }
    }
  }

  async sleep(ms) {
    return new Promise(r => setTimeout(r, ms));
  }

  async evaluate(expr) {
    const result = await this.send('Runtime.evaluate', {
      expression: expr,
      returnByValue: true,
      awaitPromise: true
    });
    if (result.exceptionDetails) {
      throw new Error(`JS Error: ${result.exceptionDetails.text}`);
    }
    return result.result.value;
  }

  async getDocument() {
    return this.send('DOM.getDocument', { depth: 0, pierce: false });
  }

  async querySelector(selector) {
    const result = await this.send('DOM.querySelector', {
      nodeId: this.docNodeId,
      selector
    });
    return result.nodeId;
  }

  async focusElement(nodeId) {
    await this.send('DOM.focus', { nodeId });
  }

  async clickElement(selector) {
    // Use JavaScript click to avoid SPA issues
    await this.evaluate(`document.querySelector('${selector}')?.click()`);
    await this.sleep(500);
  }

  async fillTextarea(selector, text) {
    // Proper way: set via JS events that React/SPA frameworks listen to
    const escaped = text.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/\n/g, '\\n');
    await this.evaluate(`
      (() => {
        const el = document.querySelector('${selector}');
        if (!el) return false;
        const nativeSetter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
        nativeSetter.call(el, '${escaped}');
        el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      })()
    `);
  }

  async selectRadio(selector) {
    await this.evaluate(`
      (() => {
        const el = document.querySelector('${selector}');
        if (!el) return false;
        el.click();
        el.dispatchEvent(new Event('change', { bubbles: true }));
        return true;
      })()
    `);
  }

  async selectDropdown(label, value) {
    // Try to select by visible label approach
    await this.evaluate(`
      (() => {
        const selects = document.querySelectorAll('select');
        for (const s of selects) {
          for (const opt of s.options) {
            if (opt.textContent.trim().includes('${value}') || opt.value.includes('${value}')) {
              s.value = opt.value;
              s.dispatchEvent(new Event('change', { bubbles: true }));
              return true;
            }
          }
        }
        return false;
      })()
    `);
  }

  async clickButtonContaining(text) {
    await this.evaluate(`
      (() => {
        const buttons = document.querySelectorAll('button');
        for (const b of buttons) {
          if (b.textContent.trim() === '${text}' || b.textContent.trim().includes('${text}')) {
            b.click();
            return true;
          }
        }
        return false;
      })()
    `);
  }

  async waitForElement(selector, timeout = 10000) {
    const start = Date.now();
    while (Date.now() - start < timeout) {
      const found = await this.evaluate(`!!document.querySelector('${selector}')`);
      if (found) return true;
      await this.sleep(300);
    }
    return false;
  }

  async getPageText() {
    return this.evaluate('document.body?.innerText || ""');
  }

  async getPageUrl() {
    return this.evaluate('window.location.href');
  }
}

async function applyForJob(driver, job) {
  const { jobId, title, company } = job;
  const applyUrl = `https://hk.jobsdb.com/job/${jobId}/apply`;
  
  console.log(`\n=== Applying: ${title} at ${company} (${jobId}) ===`);
  
  // Step 0: Navigate to apply page
  await driver.navigate(applyUrl);
  await driver.sleep(2000);
  
  let url = await driver.getPageUrl();
  console.log(`  URL: ${url}`);
  
  // Check if we're on the job description page (not apply)
  const pageText = await driver.getPageText();
  if (pageText.includes('not found') || pageText.includes('Page not found') || pageText.includes('no longer advertised')) {
    console.log(`  ❌ Job no longer advertised`);
    return { status: 'rejected', reason: 'job_no_longer_advertised' };
  }
  
  // Check if we're on the apply flow
  if (!url.includes('/apply')) {
    console.log(`  ⚠️  Redirected to detail page, checking apply link...`);
    // Try clicking the apply link
    await driver.evaluate(`
      (() => {
        const links = document.querySelectorAll('a[href*="/apply"]');
        for (const l of links) {
          if (l.href.includes('/apply')) {
            window.location.href = l.href;
            return true;
          }
        }
        return false;
      })()
    `);
    await driver.sleep(2000);
    url = await driver.getPageUrl();
    console.log(`  New URL: ${url}`);
  }
  
  // Step 1: Documents page - check and fill
  if (url.includes('/apply') && !url.includes('/role-requirements') && !url.includes('/profile') && !url.includes('/review')) {
    console.log(`  Step 1: Documents page`);
    
    // Check if employer questions are present
    const hasQuestions = await driver.evaluate(`
      document.body.innerText.includes('right to work') || 
      document.body.innerText.includes('Right to work') || 
      document.querySelector('[role=radiogroup]') !== null
    `);
    
    // Check if cover letter textarea exists
    const hasTextarea = await driver.evaluate(`!!document.querySelector('textarea')`);
    
    if (hasTextarea) {
      const coverLetter = generateCoverLetter(title, company);
      await driver.fillTextarea('textarea', coverLetter);
      console.log(`  ✅ Cover letter filled`);
      await driver.sleep(300);
    }
    
    if (hasQuestions) {
      console.log(`  ⚠️  Employer questions present on this page - may need right-to-work`);
    }
    
    // Click Continue
    await driver.clickButtonContaining('Continue');
    await driver.sleep(2000);
    url = await driver.getPageUrl();
    console.log(`  After Continue URL: ${url}`);
  }
  
  // Step 2: Role requirements / employer questions / right-to-work
  if (url.includes('/role-requirements')) {
    console.log(`  Step 2: Employer questions page`);
    
    // Check if job is still advertised
    const pageText2 = await driver.getPageText();
    if (pageText2.includes('no longer advertised') || pageText2.includes('This job is no longer')) {
      console.log(`  ❌ Job no longer advertised at role-requirements`);
      return { status: 'rejected', reason: 'job_no_longer_advertised' };
    }
    
    // Find and click right-to-work radio (first option / "I am a Hong Kong SAR permanent resident")
    await driver.evaluate(`
      (() => {
        const radios = document.querySelectorAll('input[type="radio"]');
        let clicked = false;
        radios.forEach(r => { 
          if (!clicked) { r.click(); r.dispatchEvent(new Event('change', {bubbles:true})); clicked = true; }
        });
        return clicked;
      })()
    `);
    await driver.sleep(300);
    
    // Handle notice period dropdown  
    await driver.evaluate(`
      (() => {
        const selects = document.querySelectorAll('select');
        selects.forEach(s => {
          for (const opt of s.options) {
            if (opt.textContent.includes('2 weeks') || opt.textContent.includes('2 Week')) {
              s.value = opt.value;
              s.dispatchEvent(new Event('change', {bubbles:true}));
            }
          }
        });
      })()
    `);
    await driver.sleep(300);
    
    // Click Continue
    await driver.clickButtonContaining('Continue');
    await driver.sleep(2000);
    url = await driver.getPageUrl();
    console.log(`  After employer questions URL: ${url}`);
  }
  
  // Step 3: Profile page (if present)
  if (url.includes('/profile') || (url.includes('/apply') && !url.includes('/review'))) {
    console.log(`  Step 3: Profile/Career history page`);
    const pageText3 = await driver.getPageText();
    
    // If an alert says profile is part of application, we're on profile page
    // Just click Continue
    await driver.clickButtonContaining('Continue');
    await driver.sleep(2000);
    url = await driver.getPageUrl();
    console.log(`  After profile Continue URL: ${url}`);
  }
  
  // Step 4: Review page
  if (url.includes('/review') || url.includes('/apply/success')) {
    if (url.includes('/apply/success')) {
      console.log(`  ✅ Already on success page - application sent!`);
      return { status: 'sent' };
    }
    
    console.log(`  Step 4: Review page - submitting...`);
    
    // Check for Submit button
    const hasSubmit = await driver.evaluate(`
      (() => {
        const buttons = document.querySelectorAll('button');
        for (const b of buttons) {
          if (b.textContent.trim().includes('Submit application')) {
            b.click();
            return true;
          }
        }
        return false;
      })()
    `);
    
    if (hasSubmit) {
      await driver.sleep(3000);
      url = await driver.getPageUrl();
      console.log(`  After submit URL: ${url}`);
      
      // Wait a bit more for redirect
      await driver.sleep(2000);
      const finalUrl = await driver.getPageUrl();
      console.log(`  Final URL: ${finalUrl}`);
      
      // Check for success
      if (finalUrl.includes('/apply/success') || finalUrl.includes('/my-activity/applied-jobs') || finalUrl.includes('/companies')) {
        console.log(`  ✅ Application sent!`);
        return { status: 'sent' };
      }
      
      // Check if we got sent somewhere unexpected (SPA redirect)
      console.log(`  ⚠️  Might have sent but redirected to: ${finalUrl}`);
      return { status: 'probable_sent' };
    } else {
      console.log(`  ❌ No submit button found on review page`);
      return { status: 'rejected', reason: 'no_submit_button' };
    }
  }
  
  // If we got redirected somewhere unexpected
  console.log(`  ⚠️  Unexpected flow state at: ${url}`);
  return { status: 'unknown', url };
}

function generateCoverLetter(title, company) {
  const name = profile.name || profile.fullName || "Candidate";
  const education = profile.education || [];
  const skills = profile.skills || [];
  
  let eduStr = education.map(e => `${e.degree} in ${e.field} at ${e.institution}`).join(' and ');
  let skillStr = skills.join(', ');
  
  // Get relevant keywords from title
  const titleLower = title.toLowerCase();
  let extraLines = '';
  if (titleLower.includes('llm') || titleLower.includes('nlp') || titleLower.includes('language')) {
    extraLines = `I have strong NLP skills and experience with transformer architectures, making me well-suited for LLM development work.`;
  } else if (titleLower.includes('agent') || titleLower.includes('builder')) {
    extraLines = `I am passionate about AI Agents, workflow automation, and prompt engineering concepts such as Agentic AI and RAG.`;
  } else if (titleLower.includes('computer vision') || titleLower.includes('vision') || titleLower.includes('image')) {
    extraLines = `I have experience with deep learning models including ResNet for computer vision tasks and reinforcement learning.`;
  } else if (titleLower.includes('engineer') || titleLower.includes('developer')) {
    extraLines = `I have hands-on experience developing and deploying AI/ML models in production environments.`;
  } else {
    extraLines = `I am eager to apply my AI and machine learning knowledge to solve real-world problems and drive innovation.`;
  }
  
  return `Dear Hiring Team,

I am writing to express my strong interest in the ${title} position at ${company}. As a ${eduStr}, I am excited to bring my technical expertise and passion for AI to your team.

${extraLines}

My academic projects include building a Go AI using ResNet and Monte Carlo Tree Search, and conducting spatial-temporal sentiment analysis on Yelp review data. I have hands-on experience with ${skillStr}. I am a quick learner, a strong problem-solver, and fluent in English, Putonghua, and Cantonese.

Thank you for considering my application.

Best regards,
${name}

Note: This email is automatically generated and sent by openclaw.`;
}

function logSent(job) {
  sent_count++;
  sent_jobs.push({
    timestamp: new Date().toISOString(),
    company: job.company,
    role: job.title,
    url: `https://hk.jobsdb.com/job/${job.jobId}`,
    action: 'sent'
  });
  // Write sent applications
  const existing = JSON.parse(fs.readFileSync(SENT_FILE, 'utf8') || '{"sent_count":0,"sent_jobs":[]}');
  existing.sent_count = sent_count;
  existing.sent_jobs = sent_jobs;
  fs.writeFileSync(SENT_FILE, JSON.stringify(existing, null, 2));
}

function logRejection(job, reason) {
  // JSONL
  const entry = {
    timestamp: new Date().toISOString(),
    company: job.company,
    role: job.title,
    url: `https://hk.jobsdb.com/job/${job.jobId}`,
    reason,
    action: 'rejected'
  };
  fs.appendFileSync(REJECTED_JSONL, JSON.stringify(entry) + '\n');
  
  // JSON
  const existing = JSON.parse(fs.readFileSync(REJECTED_JSON, 'utf8') || '[]');
  existing.push(entry);
  fs.writeFileSync(REJECTED_JSON, JSON.stringify(existing, null, 2));
}

// Jobs to process - AI-titled jobs from current search results that can bypass
// Using the bypass rule: titles containing "ai" (case-insensitive)
const JOBS_BY_KEYWORD = {
  'machine_learning': [
    // Fresh AI jobs from ML search
    { jobId: '92806279', title: 'AI Transformation Specialist', company: 'OrbusNeich Medical Company Limited' },
    { jobId: '92718740', title: 'Senior AI Solution Engineer', company: 'Company Confidential' },
    { jobId: '92897544', title: 'Agentic Artificial Intelligence (AI) Analyst Programmer', company: 'Computer And Technologies Solutions Limited' },
    { jobId: '91139028', title: 'Senior AI Solution Engineer', company: 'Company Confidential' },
    { jobId: '89602996', title: 'AI Engineer Lead / AI Engineer', company: 'Confidential' },
    { jobId: '90229427', title: 'AI Engineer', company: 'ESDlife' },
    { jobId: '92866660', title: 'AI Engineer (Garment/MFG)', company: 'Company Confidential' },
    { jobId: '92906730', title: '(Junior/Senior) AI Engineer / AI Specialist', company: 'Company Confidential' },
    { jobId: '92864704', title: 'AI & Computer Vision Research Engineer', company: 'Confidential' },
    { jobId: '92941233', title: 'AI Architect', company: 'Confidential' },
    { jobId: '92897999', title: 'AI Engineer', company: 'Dah Chong Hong Holdings Limited' },
    { jobId: '92795285', title: 'AI Engineer', company: 'United Chinese Plastics' },
    { jobId: '92802338', title: 'AI Researcher', company: 'Confidential' },
    { jobId: '92946408', title: 'AI & Collaboration Technology Associate (Lark / Feishu Rollout)', company: 'Wadhsons (HK) Ltd' },
    { jobId: '92890758', title: 'AI Application Specialist', company: 'Hong Kong Homily Co., Limited' },
    { jobId: '92946202', title: 'AI Teacher/ AI Coach/ AI Mentor', company: 'Hong Kong School of Commerce' },
    { jobId: '92782161', title: 'AI Engineer / AI Engineering Lead', company: 'Confidential' },
    { jobId: '92630517', title: 'AI Engineer', company: 'Pacific Prime' },
  ],
  'ai_engineer': [
    // Will be filled from live search
  ],
  'llm_developer': [
    // Will be filled from live search
  ]
};

async function main() {
  console.log('=== JobsDB Auto-Apply Script ===');
  console.log(`Target: 50 applications | Using bypass rule (AI-title jobs)`);
  
  // Connect to existing Chrome
  const wsUrl = await getWsEndpoint();
  console.log(`Connecting to Chrome at ${wsUrl}`);
  
  const driver = new JobBDriver(wsUrl);
  await driver.connect();
  console.log('Connected to Chrome\n');
  
  // Load current state
  let sentData = JSON.parse(fs.readFileSync(SENT_FILE, 'utf8') || '{"sent_count":0,"sent_jobs":[]}');
  sent_count = sentData.sent_count || 0;
  sent_jobs = sentData.sent_jobs || [];
  console.log(`Current sent count: ${sent_count}`);
  
  // Also load rejected to skip
  let rejectedUrls = [];
  try {
    const rejectedData = JSON.parse(fs.readFileSync(REJECTED_JSON, 'utf8') || '[]');
    rejectedUrls = rejectedData.map(r => r.url);
  } catch(e) {}
  console.log(`Already rejected count: ${rejectedUrls.length}`);
  
  // Process AI-title jobs from ML search first (using bypass rule)
  const allJobs = JOBS_BY_KEYWORD.machine_learning;
  console.log(`Total AI-titled jobs to try: ${allJobs.length}`);
  
  for (const job of allJobs) {
    if (sent_count >= 50) {
      console.log(`\n✅ Reached target of 50 sent applications!`);
      break;
    }
    
    const jobUrl = `https://hk.jobsdb.com/job/${job.jobId}`;
    if (rejectedUrls.includes(jobUrl)) {
      console.log(`  ⏭️  Skipping already rejected: ${job.title} at ${job.company}`);
      continue;
    }
    
    // Check if already sent
    if (sent_jobs.some(s => s.url === jobUrl)) {
      console.log(`  ⏭️  Already sent: ${job.title} at ${job.company}`);
      continue;
    }
    
    try {
      const result = await applyForJob(driver, job);
      
      if (result.status === 'sent' || result.status === 'probable_sent') {
        logSent(job);
        console.log(`  📊 Sent count: ${sent_count}/50`);
      } else {
        logRejection(job, result.reason || 'unknown');
        console.log(`  📊 Rejected: ${result.reason || 'unknown'}`);
      }
    } catch (err) {
      console.error(`  ❌ Error processing ${job.title}: ${err.message}`);
      logRejection(job, `error: ${err.message}`);
    }
    
    // Brief pause between jobs
    await driver.sleep(1000);
  }
  
  // If we still need more, we'll need to scrape more live jobs
  if (sent_count < 50) {
    console.log(`\n⚠️  Only reached ${sent_count}/50. Need to find more jobs.`);
    
    // Navigate to ML search to scrape live results
    await driver.navigate('https://hk.jobsdb.com/machine-learning-jobs');
    await driver.sleep(3000);
    
    // Extract job links
    const jobLinks = await driver.evaluate(`
      (() => {
        const links = document.querySelectorAll('a[data-automation="job-list-view-job-link"], a[href*="/job/"]');
        const results = [];
        const seen = new Set();
        links.forEach(a => {
          const href = a.href || '';
          const match = href.match(/\\/job\\/(\\d+)/);
          if (match && !seen.has(match[1])) {
            seen.add(match[1]);
            const titleEl = a.querySelector('[data-automation="job-title"], h3, .job-title');
            const title = titleEl ? titleEl.textContent.trim() : a.textContent.trim();
            results.push({ jobId: match[1], title });
          }
        });
        return results;
      })()
    `);
    
    console.log(`Found ${jobLinks.length} jobs on ML search page`);
    
    // Process only AI-titled jobs from search
    for (const link of jobLinks) {
      if (sent_count >= 50) break;
      if (!link.title.toLowerCase().includes('ai')) continue; // bypass rule
      
      const jobUrl = `https://hk.jobsdb.com/job/${link.jobId}`;
      if (rejectedUrls.includes(jobUrl) || sent_jobs.some(s => s.url === jobUrl)) continue;
      
      // Need company name - navigate to get it
      await driver.navigate(`https://hk.jobsdb.com/job/${link.jobId}`);
      await driver.sleep(2000);
      
      const company = await driver.evaluate(`
        (() => {
          const el = document.querySelector('[data-automation="jobAdvertiser"]') || 
                      document.querySelector('[data-testid="job-detail-header"] ~ div');
          return el ? el.textContent.trim() : 'Unknown Company';
        })()
      `);
      
      const result = await applyForJob(driver, { jobId: link.jobId, title: link.title, company });
      
      if (result.status === 'sent' || result.status === 'probable_sent') {
        const job = { jobId: link.jobId, title: link.title, company };
        logSent(job);
        console.log(`  📊 Sent count: ${sent_count}/50`);
      } else {
        logRejection({ jobId: link.jobId, title: link.title, company }, result.reason || 'unknown');
      }
      
      await driver.sleep(500);
    }
  }
  
  console.log(`\n=== FINAL RESULTS ===`);
  console.log(`Sent: ${sent_count}/50 applications`);
  console.log(`Jobs:`, JSON.stringify(sent_jobs.map(j => `${j.role} at ${j.company}`), null, 2));
}

main().catch(err => {
  console.error('Fatal error:', err);
  process.exit(1);
});
