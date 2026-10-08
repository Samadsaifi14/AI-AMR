'use strict';
(() => {
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)');
  const toggle=document.getElementById('motion-toggle');
  let paused=reduce.matches;
  function motion(){document.body.classList.toggle('motion-paused',paused);toggle.setAttribute('aria-pressed',String(paused));toggle.textContent=paused?'Enable motion':'Pause motion';}
  toggle.addEventListener('click',()=>{paused=!paused;motion();});
  reduce.addEventListener('change',e=>{paused=e.matches;motion();});motion();
  document.getElementById('start-demo').addEventListener('click',async()=>{
    if(busy)return;
    document.getElementById('dataset').value='demo';await setDataset();
    status('Practice data loaded. Click Audit data first. Synthetic results do not measure real-world accuracy.');
    document.getElementById('experiment').scrollIntoView({behavior:paused?'instant':'smooth'});
    document.getElementById('audit').focus({preventScroll:true});
  });
  document.getElementById('start-upload').addEventListener('click',async()=>{
    if(busy)return;
    document.getElementById('dataset').value='upload';await setDataset();
    // Uploaded cohorts need a reviewed design, not a public study ID as an implicit holdout.
    const cfg=JSON.parse(document.getElementById('configuration').value);cfg.split={mode:'internal'};
    document.getElementById('configuration').value=JSON.stringify(cfg,null,2);syncDesign();
    status('Select your de-identified observations CSV, set the actual input format and standard/version, then audit. Internal evaluation is exploratory.');
    document.getElementById('experiment').scrollIntoView({behavior:paused?'instant':'smooth'});
    document.getElementById('observations').focus({preventScroll:true});
  });
  document.addEventListener('amr:state',e=>{
    const {busy:running,modelReady:ready,result:r}=e.detail;
    let message='Choose a source and review its settings, then click Audit data.';
    if(running)message='Working on this device. Keep the tab open; Stop discards the session model.';
    else if(ready)message='Model fitted for research. Review its errors, test an isolate, and download the ZIP before leaving.';
    else if(r?.blocked)message='Training blocked. Read the reason below and correct the source data; do not invent missing measurements.';
    else if(r?.action==='audit')message='Audit complete. Review exclusions and laboratory provenance before training.';
    document.getElementById('next-step').textContent=message;
    for(const id of ['start-demo','start-upload'])document.getElementById(id).disabled=running;
  });
  if('IntersectionObserver' in window){const observer=new IntersectionObserver(entries=>{for(const e of entries)if(e.isIntersecting){e.target.classList.add('revealed');observer.unobserve(e.target);}},{threshold:.06});for(const el of document.querySelectorAll('.journey li,.section-title')){el.classList.add('reveal');observer.observe(el);}}
})();
