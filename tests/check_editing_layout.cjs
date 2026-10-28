const assert=require('node:assert/strict');
const {chromium}=require(process.argv[2]);
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe',headless:true});
 try{
  const page=await browser.newPage({viewport:{width:1400,height:1000}}),errors=[];
  page.on('pageerror',error=>errors.push(error.message));
  await page.addInitScript(()=>{localStorage.setItem('engelmig-tutorial-v1-fechamento','seen');localStorage.removeItem('engelmig-secondary-navigation-open');});
  await page.goto(process.argv[3]+'/fechamento',{waitUntil:'domcontentloaded'});
  await page.locator('#editingProgramButtons [data-editor-open]').first().waitFor({state:'attached'});
  assert.deepEqual(await page.locator('[data-editor-open]').evaluateAll(elements=>elements.map(element=>element.dataset.editorOpen)),['cadcraft','pdfcraft','photocraft']);
  assert.equal(await page.locator('#operationsBubble,#operationsMenu,#croquiOperation,[data-tab="map"],[data-tab="photo-reader"]').count(),0);
  assert.equal(await page.locator('nav[aria-label="Menu principal"] > .nav').count(),4);
  assert.equal(await page.locator('#secondaryNavigation').evaluate(element=>element.open),false);
  await page.locator('.nav[data-tab="conductors"]').click();
  assert.equal(await page.locator('#tab-conductors h1').textContent(),'Edição');
  await page.locator('#secondaryNavigation > summary').click();
  await page.locator('.nav[data-tab="profiles"]').click();
  assert.equal(await page.locator('#operationStages').isVisible(),true);
  assert.equal(await page.locator('#operationStages .stage-link').count(),4);
  await page.locator('#secondaryNavigation > summary').click();
  assert.equal(await page.locator('#secondaryNavigation').evaluate(element=>element.open),false);
  await page.locator('.nav[data-tab="conductors"]').click();
  if(process.argv[4])await page.screenshot({path:process.argv[4]});
  await page.setViewportSize({width:390,height:844});
  for(const stage of await page.locator('#operationStages .stage-link').all())assert.equal(await stage.isVisible(),true);
  assert.deepEqual(errors,[]);
  console.log('Edição: três editores, abas removidas, quatro etapas sempre visíveis e menu recolhível OK (desktop/móvel)');
 }finally{await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
