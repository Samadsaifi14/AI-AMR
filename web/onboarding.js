'use strict';
(() => {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const toggle = document.getElementById('motion-toggle');
  let paused = reduce.matches;
  let restoreInProgress = false;
  let saveTimer;
  let savePending = false;
  let dbPromise;
  let persistenceMessageShown = false;

  function motion() {
    document.body.classList.toggle('motion-paused', paused);
    toggle.setAttribute('aria-pressed', String(paused));
    toggle.textContent = paused ? 'Enable motion' : 'Pause motion';
  }
  toggle.addEventListener('click', () => { paused = !paused; motion(); });
  reduce.addEventListener('change', event => { paused = event.matches; motion(); });
  motion();

  function openDb() {
    if (!('indexedDB' in window)) return Promise.reject(new Error('This browser does not provide local experiment storage.'));
    if (!dbPromise) dbPromise = new Promise((resolve, reject) => {
      const request = indexedDB.open('amr-research-workspace', 1);
      request.onupgradeneeded = () => request.result.createObjectStore('workflows', {keyPath: 'id'});
      request.onsuccess = () => resolve(request.result);
      request.onerror = () => reject(request.error || new Error('Could not open local experiment storage.'));
    });
    return dbPromise;
  }
  async function readSaved() {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const request = db.transaction('workflows', 'readonly').objectStore('workflows').get('current');
      request.onsuccess = () => resolve(request.result || null);
      request.onerror = () => reject(request.error || new Error('Could not read saved work.'));
    });
  }
  async function writeSaved(record) {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction('workflows', 'readwrite');
      transaction.objectStore('workflows').put(record);
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error || new Error('Could not save work in this browser.'));
      transaction.onabort = () => reject(transaction.error || new Error('The browser stopped saving this work.'));
    });
  }
  async function deleteSaved() {
    const db = await openDb();
    return new Promise((resolve, reject) => {
      const transaction = db.transaction('workflows', 'readwrite');
      transaction.objectStore('workflows').delete('current');
      transaction.oncomplete = resolve;
      transaction.onerror = () => reject(transaction.error || new Error('Could not clear saved work.'));
    });
  }
  function showSaved(record) {
    const card = document.getElementById('resume-card');
    card.hidden = !record;
    if (record) {
      document.getElementById('resume-description').textContent = record.result
        ? 'Your setup, last result and downloadable experiment are saved in this browser.'
        : record.dataset === 'upload'
          ? 'Your saved CSV and setup are stored in this browser. Resume to review the setup and run it again.'
          : 'Your saved setup is stored in this browser. Resume to review it and run the experiment again.';
    }
  }
  async function saveWorkflow() {
    if (restoreInProgress || busy || !datasetReady) return;
    const dataset = document.getElementById('dataset').value;
    const configuration = document.getElementById('configuration').value;
    let csv = window.__restoredCsv || '';
    if (dataset === 'upload') {
      const file = document.getElementById('observations').files[0];
      if (file) {
        if (file.size > 10 * 1024 * 1024) {
          status('This CSV is larger than the browser upload limit, so it cannot be saved for resume. It remains available for this session.', true);
          return;
        }
        csv = await file.text();
      }
    } else {
      csv = '';
    }
    const savedResult = currentResult?.report && currentResult?.archive ? currentResult : null;
    const record = {id: 'current', dataset, configuration, csv, result: savedResult, savedAt: new Date().toISOString(), stage: savedResult ? 'results' : 'setup'};
    try {
      await writeSaved(record);
      showSaved(record);
      persistenceMessageShown = false;
    } catch (error) {
      if (!persistenceMessageShown) {
        status('The browser could not save this work for later. You can continue now; keep the tab open and download the experiment when it finishes. ' + error.message, true);
        persistenceMessageShown = true;
      }
    }
  }
  function scheduleSave() {
    clearTimeout(saveTimer);
    savePending = true;
    saveTimer = setTimeout(() => {
      saveTimer = null;
      saveWorkflow().catch(() => {}).finally(() => { savePending = false; });
    }, 500);
  }

  document.getElementById('start-demo').addEventListener('click', async () => {
    if (busy) return;
    restoreInProgress = true;
    try {
      document.getElementById('dataset').value = 'demo';
      await setDataset();
      document.getElementById('advanced-config').open = false;
      restoreInProgress = false;
      await saveWorkflow();
      window.__guidedDemo = true;
      document.getElementById('next-step').textContent = 'Demo started. The app is checking the synthetic data, fitting the research model, and testing it on a held-out synthetic source.';
      document.getElementById('experiment').scrollIntoView({behavior: paused ? 'instant' : 'smooth'});
      launch('train');
    } catch (error) {
      window.__guidedDemo = false;
      status('The demo could not be started. Check the connection and try again. ' + error.message, true);
    } finally {
      restoreInProgress = false;
    }
  });

  document.getElementById('start-upload').addEventListener('click', async () => {
    if (busy) return;
    restoreInProgress = true;
    try {
      document.getElementById('dataset').value = 'upload';
      await setDataset();
      const cfg = JSON.parse(document.getElementById('configuration').value);
      cfg.split = {mode: 'internal'};
      document.getElementById('configuration').value = JSON.stringify(cfg, null, 2);
      syncDesign();
      document.getElementById('experiment').scrollIntoView({behavior: paused ? 'instant' : 'smooth'});
      document.getElementById('observations').focus({preventScroll: true});
      status('Choose your de-identified AST CSV. Your file stays in this browser. The app saves your setup here so you can resume later.');
    } catch (error) {
      status('The data workflow could not be prepared. Check the connection and try again. ' + error.message, true);
    } finally {
      restoreInProgress = false;
      scheduleSave();
    }
  });

  document.getElementById('resume-work').addEventListener('click', async () => {
    if (busy) return;
    restoreInProgress = true;
    try {
      const record = await readSaved();
      if (!record) throw new Error('No saved workflow was found in this browser.');
      document.getElementById('dataset').value = record.dataset;
      await setDataset();
      document.getElementById('configuration').value = record.configuration;
      window.__restoredCsv = record.csv || '';
      syncDesign();
      if (record.result) {
        currentResult = record.result;
        bundle = record.result.archive;
        report = record.result.report;
        modelReady = false;
        render(record.result);
        sync();
        document.getElementById('results').scrollIntoView({behavior: paused ? 'instant' : 'smooth'});
        status('Saved result restored. You can review or download it now; run the experiment again in this tab before making a new research prediction.');
      } else {
        sync();
        document.getElementById('experiment').scrollIntoView({behavior: paused ? 'instant' : 'smooth'});
        if (record.dataset === 'upload' && !record.csv) {
          status('Your saved setup was restored, but the CSV was not saved. Select the file again to continue.', true);
          document.getElementById('observations').focus({preventScroll: true});
        } else {
          status('Saved setup restored. Review the selected source and choose Check my data or Train & test. The model must be run again before prediction.');
        }
      }
    } catch (error) {
      status('Saved work could not be restored. It may have been cleared by the browser. ' + error.message, true);
    } finally {
      restoreInProgress = false;
    }
  });

  document.getElementById('clear-saved').addEventListener('click', async () => {
    try {
      await deleteSaved();
      window.__restoredCsv = '';
      showSaved(null);
      status('Saved workflow and its local CSV were cleared from this browser.');
    } catch (error) {
      status('Could not clear the saved workflow. ' + error.message, true);
    }
  });

  document.getElementById('dataset').addEventListener('change', () => { window.__restoredCsv = ''; scheduleSave(); });
  document.getElementById('configuration').addEventListener('change', scheduleSave);
  document.getElementById('observations').addEventListener('change', async () => {
    window.__restoredCsv = '';
    if (document.getElementById('observations').files[0]) await saveWorkflow();
  });
  document.getElementById('configuration').addEventListener('input', scheduleSave);

  document.addEventListener('beforeunload', event => {
    if (busy || savePending) {
      event.preventDefault();
      event.returnValue = '';
    }
  });

  document.addEventListener('amr:state', event => {
    const {busy: running, modelReady: ready, result} = event.detail;
    let message = 'Choose a path above. You can explore the demo without a laboratory file.';
    if (running) message = 'Working on this device. Keep this tab open while the analysis runs.';
    else if (ready) message = 'Model fitted for research. Review errors, try an isolate, and download the experiment ZIP.';
    else if (result?.blocked) message = 'Training blocked. Read the reason below and correct the source data; do not invent missing measurements.';
    else if (result?.metrics && !ready) message = 'Saved result is available. Rerun the experiment before making a new research prediction.';
    else if (result?.action === 'audit') message = 'Data check complete. Review exclusions and laboratory provenance before training.';
    document.getElementById('next-step').textContent = message;
    for (const id of ['start-demo', 'start-upload', 'resume-work', 'clear-saved']) document.getElementById(id).disabled = running;
    if (!running && window.__guidedDemo && !result) window.__guidedDemo = false;
    if (!running && window.__guidedDemo && result) {
      window.__guidedDemo = false;
      document.getElementById('results').scrollIntoView({behavior: paused ? 'instant' : 'smooth'});
      const heading = document.getElementById('results').querySelector('h2');
      heading.setAttribute('tabindex', '-1');
      heading.focus({preventScroll: true});
    }
    if (!running) scheduleSave();
  });

  readSaved().then(showSaved).catch(() => {
    document.getElementById('resume-card').hidden = true;
    if (!persistenceMessageShown) {
      document.getElementById('next-step').textContent = 'This browser cannot provide automatic resume storage. The demo and analysis still work; download the experiment when it finishes.';
      persistenceMessageShown = true;
    }
  });

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      for (const entry of entries) if (entry.isIntersecting) {
        entry.target.classList.add('revealed');
        observer.unobserve(entry.target);
      }
    }, {threshold: .06});
    for (const element of document.querySelectorAll('.journey li,.section-title,.home-card')) {
      element.classList.add('reveal');
      observer.observe(element);
    }
  }
})();
