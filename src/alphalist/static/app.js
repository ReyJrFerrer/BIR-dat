'use strict';

const initialForms = new WeakMap();
let busy = false;
let navigating = false;
const drawer = document.querySelector('#employee-drawer');
const toast = document.querySelector('#notification');
const status = document.querySelector('#export-status');
const pdfControl = document.querySelector('.pdf-menu summary');
const noWorkbook = pdfControl?.getAttribute('aria-disabled') === 'true';
const formValues = form => JSON.stringify([...new FormData(form)].filter(([key]) => key !== 'csrf'));
const dirtyForms = () => [...document.querySelectorAll('[data-correction]')].filter(form => initialForms.has(form) && initialForms.get(form) !== formValues(form));

function updateDownloads() {
  const blocked = busy || dirtyForms().length > 0;
  document.querySelectorAll('[data-download]').forEach(link => {
    link.setAttribute('aria-disabled', String(blocked));
    link.tabIndex = blocked ? -1 : 0;
  });
  const pdf = document.querySelector('.pdf-menu');
  pdfControl?.setAttribute('aria-disabled', String(blocked || noWorkbook));
  if (pdf && blocked) pdf.open = false;
  if (status) status.textContent = busy ? (document.querySelector('[data-upload]') ? 'Preparing workbook…' : 'Checking changes…') : blocked ? 'Save your changes before downloading.' : status.dataset.savedStatus || status.textContent;
}

function askConfirmation(replace = false) {
  const dialog = document.querySelector('#confirm-dialog');
  document.querySelector('#confirm-title').textContent = replace ? 'Import a different workbook?' : 'Discard unsaved changes?';
  document.querySelector('#confirm-copy').textContent = replace ? 'The new workbook will replace this review after it is successfully prepared.' : 'Your saved review will be kept.';
  dialog.querySelector('[data-confirm="no"]').textContent = replace ? 'Keep current review' : 'Keep editing';
  dialog.querySelector('[data-confirm="yes"]').textContent = replace ? 'Import workbook' : 'Discard changes';
  dialog.returnValue = 'no';
  dialog.showModal();
  return new Promise(resolve => dialog.addEventListener('close', () => resolve(dialog.returnValue === 'yes'), {once: true}));
}
document.querySelectorAll('[data-confirm]').forEach(button => button.addEventListener('click', () => button.closest('dialog').close(button.dataset.confirm)));

let toastTimer;
let toastStarted;
let toastRemaining = 6000;
function pauseToast() {
  clearTimeout(toastTimer);
  if (toastStarted) toastRemaining = Math.max(0, toastRemaining - (Date.now() - toastStarted));
  toastStarted = null;
}
function startToastTimer() {
  clearTimeout(toastTimer);
  toastStarted = Date.now();
  toastTimer = setTimeout(() => { toast.hidden = true; }, toastRemaining);
}
if (toast) {
  toast.querySelector('button').addEventListener('click', () => { toast.hidden = true; pauseToast(); });
  toast.addEventListener('mouseenter', pauseToast);
  toast.addEventListener('mouseleave', () => { if (!toast.contains(document.activeElement)) startToastTimer(); });
  toast.addEventListener('focusin', pauseToast);
  toast.addEventListener('focusout', () => { if (!toast.matches(':hover')) startToastTimer(); });
  if (!toast.hidden) {
    const message = toast.querySelector('div').textContent;
    toast.querySelector('div').textContent = '';
    requestAnimationFrame(() => { toast.querySelector('div').textContent = message; });
    startToastTimer();
  }
}

function revealTarget(hash = location.hash, root = document) {
  let id;
  try { id = decodeURIComponent(hash.replace(/^#/, '')); } catch { return; }
  if (!id) return;
  const target = root.querySelector(`#${CSS.escape(id)}`);
  if (!target) return;
  let parent = target;
  while (parent) {
    if (parent.tagName === 'DETAILS') parent.open = true;
    parent = parent.parentElement;
  }
  target.scrollIntoView({block: 'nearest'});
  (target.querySelector('input, select, button') || target).focus({preventScroll: true});
}
window.addEventListener('hashchange', () => { if (location.hash) revealTarget(); });
if (location.hash) revealTarget();

function inlineError(form, message) {
  const error = form.querySelector('.form-error');
  error.hidden = false;
  error.textContent = message;
  error.tabIndex = -1;
  error.focus();
}

async function postForm(form) {
  const response = await fetch(form.action, {method: 'POST', body: new FormData(form), headers: {Accept: 'application/json'}});
  let data;
  try { data = await response.json(); } catch { throw new Error("We couldn't save your changes. Try again."); }
  if (!response.ok) throw new Error(data.detail || 'The request could not be completed. Try again.');
  return data;
}

function bindForms(root = document) {
  root.querySelectorAll('[data-correction]').forEach(form => {
    initialForms.set(form, formValues(form));
    form.addEventListener('input', updateDownloads);
    form.addEventListener('change', updateDownloads);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      if (busy) return;
      busy = true;
      updateDownloads();
      const button = form.querySelector('button[type="submit"]');
      const label = button.textContent;
      button.disabled = true;
      button.textContent = 'Checking changes…';
      form.querySelector('.form-error').hidden = true;
      try {
        const data = await postForm(form);
        const employee = form.closest('[data-employee-key]');
        if (employee) sessionStorage.setItem('return-employee', employee.dataset.employeeKey);
        navigating = true;
        location.assign(data.redirect);
      } catch (error) {
        inlineError(form, error.message);
        busy = false;
        button.disabled = false;
        button.textContent = label;
        updateDownloads();
      }
    });
  });
}
bindForms();

let drawerTrigger;
let drawerLoad = 0;
async function openEmployee(link) {
  if (!drawer || busy) return;
  if (dirtyForms().length && !await askConfirmation()) return;
  // Explicitly discarded forms return to their saved values before opening a record.
  dirtyForms().forEach(form => form.reset());
  updateDownloads();
  const url = new URL(link.href, location.origin);
  const load = ++drawerLoad;
  drawerTrigger = link;
  drawer.removeAttribute('aria-labelledby');
  const content = document.querySelector('#drawer-content');
  content.innerHTML = '<p class="empty" role="status">Loading employee…</p>';
  drawer.showModal();
  try {
    const response = await fetch(`${url.pathname}?fragment=1`);
    if (!response.ok) throw new Error('The employee could not be loaded. Close this panel and try again.');
    const html = await response.text();
    if (load !== drawerLoad || !drawer.open) return;
    content.innerHTML = html;
    bindForms(content);
    drawer.setAttribute('aria-labelledby', 'employee-title');
    content.querySelector('[data-close-employee]').focus();
    if (url.hash) revealTarget(url.hash, content);
    else content.querySelector('input:not([type="hidden"])')?.focus();
  } catch (error) {
    if (load !== drawerLoad || !drawer.open) return;
    content.innerHTML = '<div class="employee-editor"><p class="form-error" role="alert"></p><button class="secondary" data-close-employee>Close</button></div>';
    content.querySelector('p').textContent = error.message;
    content.querySelector('button').focus();
  }
}
async function closeEmployee() {
  if (busy) return;
  const form = drawer?.querySelector('form') || document.querySelector('[data-correction]');
  if (form && initialForms.get(form) !== formValues(form) && !await askConfirmation()) return;
  if (drawer?.open) {
    drawerLoad++;
    drawer.close();
    document.querySelector('#drawer-content').replaceChildren();
    updateDownloads();
    if (drawerTrigger?.isConnected) drawerTrigger.focus();
  } else { navigating = true; location.assign('/review#employees'); }
}
drawer?.addEventListener('cancel', event => { event.preventDefault(); closeEmployee(); });

document.addEventListener('click', async event => {
  const close = event.target.closest('[data-close-employee]');
  if (close) { event.preventDefault(); await closeEmployee(); return; }
  const employee = event.target.closest('[data-employee]');
  if (employee && drawer) { event.preventDefault(); await openEmployee(employee); return; }
  const totals = event.target.closest('[data-open-totals]');
  if (totals) { document.querySelector('#totals-dialog').showModal(); return; }
  if (event.target.closest('[data-close-dialog]')) { event.target.closest('dialog').close(); return; }
  const link = event.target.closest('a');
  if (link?.hasAttribute('data-download')) {
    event.preventDefault();
    if (busy || dirtyForms().length) { updateDownloads(); return; }
    await downloadFile(link);
    return;
  }
  if (event.target.closest('.pdf-menu summary') && (busy || dirtyForms().length || event.target.closest('summary').getAttribute('aria-disabled') === 'true')) event.preventDefault();
  if (link && link.getAttribute('href').startsWith('#')) {
    event.preventDefault();
    history.replaceState(null, '', link.getAttribute('href'));
    revealTarget(link.hash);
    return;
  }
  if (link && !link.hasAttribute('data-download') && dirtyForms().length && new URL(link.href).pathname !== location.pathname) {
    event.preventDefault();
    if (await askConfirmation()) { navigating = true; location.assign(link.href); }
  }
});

document.addEventListener('click', event => {
  const menu = document.querySelector('.pdf-menu');
  if (menu && !menu.contains(event.target)) menu.open = false;
});
document.addEventListener('keydown', event => {
  if (event.key === 'Tab') {
    const modal = document.querySelector('#confirm-dialog[open]') || document.querySelector('dialog[open]');
    if (modal) {
      const controls = [...modal.querySelectorAll('a[href], button:not(:disabled), input:not([type="hidden"]):not(:disabled), select:not(:disabled), textarea:not(:disabled), summary, [tabindex]:not([tabindex="-1"])')]
        .filter(control => control.getClientRects().length && control.getAttribute('aria-disabled') !== 'true');
      const first = controls[0];
      const last = controls[controls.length - 1];
      if (first && (!modal.contains(document.activeElement) || (!event.shiftKey && document.activeElement === last) || (event.shiftKey && document.activeElement === first))) {
        event.preventDefault();
        (event.shiftKey ? last : first).focus();
      }
    }
  }
  const menu = document.querySelector('.pdf-menu');
  if (event.key === 'Escape' && menu?.open) { menu.open = false; menu.querySelector('summary').focus(); }
});
window.addEventListener('beforeunload', event => {
  if (!navigating && (busy || dirtyForms().length)) { event.preventDefault(); event.returnValue = ''; }
});

async function downloadFile(link) {
  if (link.hasAttribute('aria-busy')) return;
  const kind = link.getAttribute('href').split('/').pop();
  const label = kind === 'dat' ? 'DAT' : kind === 'draft' ? 'draft PDF' : 'final PDF';
  link.setAttribute('aria-busy', 'true');
  try {
    const response = await fetch(link.href);
    if (!response.ok) throw new Error();
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = response.headers.get('content-disposition')?.match(/filename="([^"]+)"/)?.[1] || `alphalist.${kind === 'dat' ? 'dat' : 'pdf'}`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } catch {
    let error = document.querySelector('#download-error');
    if (!error) {
      error = document.createElement('p'); error.id = 'download-error'; error.className = 'form-error'; error.setAttribute('role', 'alert');
      document.querySelector('main').prepend(error);
    }
    error.textContent = `We couldn't generate your ${label}. Try downloading again.`;
    error.tabIndex = -1; error.focus();
  } finally { link.removeAttribute('aria-busy'); }
}

const rows = [...document.querySelectorAll('[data-record]')];
if (rows.length) {
  const search = document.querySelector('#employee-search');
  const filter = document.querySelector('#employee-filter');
  let page = 0;
  function renderEmployees() {
    const term = search.value.toLowerCase().trim();
    const compact = term.replace(/[ -]/g, '');
    const matched = rows.filter(row => (row.dataset.search.includes(term) || row.dataset.search.replace(/[ -]/g, '').includes(compact)) && (filter.value === 'all' || row.dataset.attention === 'true'));
    const pages = Math.max(1, Math.ceil(matched.length / 10));
    page = Math.min(page, pages - 1);
    rows.forEach(row => { row.hidden = true; });
    matched.slice(page * 10, page * 10 + 10).forEach(row => { row.hidden = false; });
    document.querySelector('#match-count').textContent = `${matched.length} ${matched.length === 1 ? 'match' : 'matches'}`;
    document.querySelector('#page-description').textContent = matched.length ? `Showing ${page * 10 + 1}–${Math.min(page * 10 + 10, matched.length)} of ${matched.length}` : '0 employees';
    document.querySelector('#page-number').textContent = `${page + 1} / ${pages}`;
    document.querySelector('#previous-page').disabled = page === 0;
    document.querySelector('#next-page').disabled = page === pages - 1;
    document.querySelector('#empty-employees').hidden = matched.length > 0;
  }
  search.addEventListener('input', () => { page = 0; renderEmployees(); });
  filter.addEventListener('change', () => { page = 0; renderEmployees(); });
  document.querySelector('#previous-page').addEventListener('click', () => { page--; renderEmployees(); });
  document.querySelector('#next-page').addEventListener('click', () => { page++; renderEmployees(); });
  renderEmployees();
}

const upload = document.querySelector('[data-upload]');
if (upload) {
  const input = upload.querySelector('[type="file"]');
  const zone = upload.querySelector('.dropzone');
  function selectedFile() {
    const file = input.files[0];
    document.querySelector('#file-selection').hidden = !file;
    if (!file) return;
    document.querySelector('#file-name').textContent = file.name;
    document.querySelector('#file-size').textContent = `${(file.size / 1024 / 1024).toFixed(2)} MB`;
    upload.querySelector('.form-error').hidden = true;
    if (!file.name.toLowerCase().endsWith('.xlsx')) inlineError(upload, 'Select an XLSX workbook.');
    else if (file.size > 10 * 1024 * 1024) inlineError(upload, 'Select a workbook smaller than 10 MB.');
  }
  input.addEventListener('change', selectedFile);
  document.querySelector('#remove-file').addEventListener('click', () => { input.value = ''; selectedFile(); input.focus(); });
  zone.addEventListener('dragover', event => { event.preventDefault(); zone.classList.add('drag-over'); });
  zone.addEventListener('dragleave', () => zone.classList.remove('drag-over'));
  zone.addEventListener('drop', event => {
    event.preventDefault(); zone.classList.remove('drag-over');
    if (busy) return;
    const transfer = new DataTransfer();
    if (event.dataTransfer.files[0]) transfer.items.add(event.dataTransfer.files[0]);
    input.files = transfer.files; selectedFile();
  });
  upload.addEventListener('submit', async event => {
    event.preventDefault();
    if (busy || !input.files.length) return;
    if (input.files[0].size > 10 * 1024 * 1024 || !input.files[0].name.toLowerCase().endsWith('.xlsx')) { selectedFile(); return; }
    if (upload.dataset.replace === 'true' && !await askConfirmation(true)) return;
    busy = true;
    const button = upload.querySelector('button[type="submit"]');
    button.disabled = true;
    upload.querySelector('.loading-status').hidden = false;
    upload.querySelector('.form-error').hidden = true;
    // Capture the selected file before disabling its input.
    const pending = postForm(upload);
    input.disabled = true;
    document.querySelector('#remove-file').disabled = true;
    updateDownloads();
    try {
      const data = await pending;
      navigating = true; location.assign(data.redirect);
    } catch (error) {
      inlineError(upload, error.message);
      busy = false; button.disabled = false; input.disabled = false;
      document.querySelector('#remove-file').disabled = false;
      upload.querySelector('.loading-status').hidden = true;
      updateDownloads();
    }
  });
}

const employeeKey = new URLSearchParams(location.search).get('employee');
if (drawer && employeeKey) {
  const link = document.querySelector(`[data-employee][href^="/employee/${CSS.escape(employeeKey)}"]`);
  if (link) {
    const target = link.cloneNode(true);
    target.href = `/employee/${encodeURIComponent(employeeKey)}${location.hash}`;
    openEmployee(target).then(() => { drawerTrigger = link; });
  }
}
if (drawer && !employeeKey) {
  const returnKey = sessionStorage.getItem('return-employee');
  sessionStorage.removeItem('return-employee');
  if (returnKey) {
    const link = document.querySelector(`.employee-table [href="/employee/${CSS.escape(returnKey)}"]`);
    if (link) {
      while (link.closest('tr').hidden && !document.querySelector('#next-page').disabled) document.querySelector('#next-page').click();
      link.focus({preventScroll: true});
    }
  }
}
