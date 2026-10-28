// Verificação opcional com Playwright e Edge instalados no ambiente de teste.
const assert=require('node:assert/strict');
const {chromium}=require(process.argv[2]);
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true,args:['--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 try{
  const page=await browser.newPage({viewport:{width:1400,height:1000}});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.addInitScript(()=>localStorage.setItem('engelmig-tutorial-v1-fechamento','seen'));
  await page.goto(process.argv[3]+'/fechamento',{waitUntil:'domcontentloaded',timeout:90000});
  await page.locator('#editingPrograms').waitFor({state:'attached',timeout:90000});
  assert.equal(await page.locator('#operationsBubble, #operationsMenu, #croquiOperation').count(),0);
  assert.equal(await page.locator('#secondaryNavigation').evaluate(element=>element.open),false);
  await page.locator('.nav[data-tab="book"]').click();
  await page.locator('#addPoint').click();
  if(!await page.locator('#laborFinder').evaluate(element=>element.open))await page.locator('#laborFinder > summary').click();
  const search=page.locator('#laborSearch');await search.fill('60007');
  await page.waitForFunction(()=>document.querySelector('#laborList [data-labor]')?.textContent.includes('60007'));
  assert.match(await search.getAttribute('placeholder'),/nome ou código/);
  await search.fill('transformador');
  await page.waitForFunction(()=>document.querySelector('#laborList [data-labor]')?.textContent.toUpperCase().includes('TRANSFORMADOR'));
  await page.locator('.nav[data-tab="conductors"]').click();
  await page.locator('#editingPrograms').waitFor({state:'visible'});
  await page.waitForFunction(()=>document.querySelectorAll('#editingProgramButtons [data-editor-open]').length===3);
  assert.deepEqual(await page.locator('#editingProgramButtons [data-editor-open]').evaluateAll(elements=>elements.map(element=>element.dataset.editorOpen).sort()),['cadcraft','pdfcraft','photocraft']);
  await page.locator('#operationStages').waitFor({state:'visible'});
  if(process.argv[5]){
   const id=process.argv[5];await page.locator('#editingProgramButtons [data-editor-open="'+id+'"]').click();
   await page.locator('#operationFrames iframe[data-operation="'+id+'"][data-ready="true"]').waitFor({timeout:90000});
   await page.frameLocator('iframe[data-operation="'+id+'"]').locator('canvas').waitFor({state:'visible'});
   console.log('Editor incorporado carregado: '+id);
   if(id==='cadcraft'||id==='pdfcraft'){
    let downloads=0;page.on('download',()=>downloads++);
    const testName='teste-integrado-'+Date.now()+'.'+(id==='cadcraft'?'dxf':'pdf');
    await page.evaluate(({id,testName})=>{
     const frame=document.querySelector('iframe[data-operation="'+id+'"]');
     let text='0\nSECTION\n2\nENTITIES\n0\nLINE\n8\n0\n10\n0\n20\n0\n11\n10\n21\n10\n0\nENDSEC\n0\nEOF\n';
     if(id==='pdfcraft'){
      // PDF sintético de uma página, sem fontes ou imagens externas.
      text='%PDF-1.4\n';const offsets=[0];
      const objects=['<< /Type /Catalog /Pages 2 0 R >>','<< /Type /Pages /Kids [3 0 R] /Count 1 >>','<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Resources << >> /Contents 4 0 R >>','<< /Length 0 >>\nstream\n\nendstream'];
      objects.forEach((body,index)=>{offsets.push(text.length);text+=(index+1)+' 0 obj\n'+body+'\nendobj\n';});
      const xref=text.length;text+='xref\n0 5\n0000000000 65535 f \n'+offsets.slice(1).map(offset=>String(offset).padStart(10,'0')+' 00000 n \n').join('')+'trailer\n<< /Size 5 /Root 1 0 R >>\nstartxref\n'+xref+'\n%%EOF\n';
     }
     const bytes=new TextEncoder().encode(text).buffer;
     frame.contentWindow.postMessage({type:id+':open',name:testName,bytes},location.origin,[bytes]);
    },{id,testName});
    await page.waitForTimeout(1000);
    await page.frameLocator('iframe[data-operation="'+id+'"]').locator('canvas').click({position:{x:600,y:400}});
    await page.keyboard.press('Control+s');
    await page.locator('#operationSavedFiles button').filter({hasText:'Reabrir: '+testName}).waitFor({timeout:30000});
    assert.equal(downloads,0);
    console.log(id+': documento recebido e salvo no banco sem download externo');
    // Atrasa o primeiro POST para detectar salvamentos concorrentes fora de ordem.
    let inFlight=0,maxInFlight=0,requests=0;
    await page.route('**/api/operation-documents',async route=>{
     if(route.request().method()!=='POST')return route.continue();
     requests++;inFlight++;maxInFlight=Math.max(maxInFlight,inFlight);
     try{if(requests===1)await new Promise(resolve=>setTimeout(resolve,250));await route.fulfill({response:await route.fetch()});}
     finally{inFlight--;}
    });
    const queueName='teste-fila-'+Date.now()+'.txt';
    await page.frames().find(frame=>frame.url().includes('/operations/'+id+'/')).evaluate(({id,queueName})=>{
     for(const value of ['primeiro','segundo']){
      parent.postMessage({type:id+':dirty',dirty:true},location.origin);
      const bytes=new TextEncoder().encode(value).buffer;
      parent.postMessage({type:id+':save',name:queueName,bytes},location.origin,[bytes]);
     }
    },{id,queueName});
    await page.waitForFunction(async ({id,queueName})=>{
     const records=await api('/api/operation-documents?context='+encodeURIComponent(S.draftId)+'&operation='+id);
     return records.some(item=>item.name===queueName&&atob(item.data)==='segundo');
    },{id,queueName},{timeout:30000});
    await page.waitForFunction(()=>document.getElementById('operationNotice').textContent.includes('Documento salvo'));
    for(let attempt=0;requests<2&&attempt<50;attempt++)await page.waitForTimeout(100);
    await page.unrouteAll({behavior:'wait'});
    assert.equal(requests,2);assert.equal(maxInFlight,1);
    console.log(id+': fila preservou a versão mais recente com POST atrasado');
    if(id==='pdfcraft'){
     page.once('dialog',dialog=>dialog.accept());
     await page.locator('#operationSavedFiles button').filter({hasText:'Usar '+testName+' no croqui'}).click();
     await page.locator('#pdfBackgroundDialog').waitFor({state:'visible'});
     await page.locator('#pdfBackgroundUse').click();
     await page.locator('#operationsWorkspace').waitFor({state:'hidden'});
     await page.waitForFunction(()=>window.Book.summary().croqui_pages.length===1);
     console.log('PDF salvo aplicado ao croqui do fechamento');
    }
   }
  }
  if(process.argv[4])await page.screenshot({path:process.argv[4],fullPage:false});
  assert.deepEqual(errors,[]);
  console.log('Interface: busca por código/nome e três editores dentro de Edição OK');
 }finally{for(const context of browser.contexts())for(const page of context.pages())await page.unrouteAll({behavior:'ignoreErrors'});await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
