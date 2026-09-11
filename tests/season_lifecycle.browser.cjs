// Each engine gets its own temporary SQLite/files and real workers. No production calls.
const {chromium, webkit, request} = require('playwright');
const {spawn} = require('node:child_process');
const readline = require('node:readline');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');

async function server() {
  const child = spawn(process.env.PYTHON || 'python', ['tests/serve_season_lifecycle.py', '--port', '0', '--stdio-control'], {stdio:['pipe','pipe','pipe']});
  let diagnostics = '';
  child.stderr.on('data', b => { diagnostics = (diagnostics + b).slice(-12000); });
  const ready = await new Promise((resolve,reject) => {
    const timer = setTimeout(() => { child.stdin.end(); reject(Error('Rehearsal startup timeout: '+diagnostics)); }, 180000);
    const lines = readline.createInterface({input:child.stdout});
    lines.on('line', line => {
      if (line.startsWith('REHEARSAL_READY=')) { clearTimeout(timer); resolve(JSON.parse(line.slice(16))); }
    });
    child.once('error', e => {clearTimeout(timer);reject(e);});
    child.once('exit', code => {clearTimeout(timer);reject(Error('Server exited '+code+': '+diagnostics));});
  });
  return {...ready, close: async () => {
    if (child.exitCode !== null) return;
    const stopped = new Promise(resolve => child.once('exit',resolve));
    child.stdin.end();
    await stopped;
  }};
}

(async () => {
  fs.mkdirSync('instance/season-lifecycle-checks', {recursive:true});
  for (const [name, engine] of [['chromium',chromium],['webkit',webkit]]) {
    const fixture = await server();
    console.log(`${name}: isolated rehearsal server ready`);
    const browser = await engine.launch();
    const auth = await request.newContext({baseURL:fixture.url});
    try {
      assert.equal((await auth.post('/api/login',{data:{username:'previewadmin',password:'Preview1234'}})).status(),200);
      const csrf = (await (await auth.get('/api/me')).json()).csrf_token;
      const context = await browser.newContext({storageState:await auth.storageState(),viewport:{width:1440,height:1000}});
      const page = await context.newPage();
      const errors = [];
      context.on('page', p => p.on('pageerror',e=>errors.push(e.message)));
      page.on('pageerror',e=>errors.push(e.message));
      const call = async (method,path,data) => {
        const response=await auth[method](path,{data,headers:{'X-CSRF-Token':csrf}});
        assert(response.ok(), `${path}: ${await response.text()}`);
        return response.json();
      };
      // Create the separate lineup classification through the actual admin dialog.
      await page.goto(fixture.url+'/admin');
      await page.locator('.admin-sidebar [data-admin-nav-toggle="live-comps"]').click();
      await page.locator('.admin-sidebar [data-admin-tab="live-comps"][data-admin-workspace="seasons"]').click();
      await page.getByRole('button',{name:'新增赛季',exact:true}).click();
      await page.locator('#liveSeasonIdInput').fill('s99');
      await page.locator('#liveSeasonNameInput').fill('S99 本地演练');
      assert.equal(await page.locator('#liveSeasonStatusInput').inputValue(),'hidden');
      await page.locator('#liveSeasonStatusInput').selectOption('hidden');
      await page.getByRole('button',{name:'创建赛季',exact:true}).click();
      await page.locator('#liveSeasonIdInput').waitFor({state:'detached'});
      await page.locator('.admin-sidebar [data-admin-tab="season-packages"]').click();
      const root=page.locator('#seasonPackageRoot');
      await root.getByText('将更新包拖到这里',{exact:true}).waitFor();
      let currentRevision=0;
      const releases=[];
      for (let index=0;index<3;index++) {
        if(index) await root.getByRole('button',{name:'移除 '+path.basename(fixture.packages[index-1]),exact:true}).click();
        await root.locator('input[type=file]').setInputFiles(fixture.packages[index]);
        const packageId=['s99-99_1-rehearsal-r1','s99-99_2-rehearsal-r1','s99-99_2-rehearsal-r2'][index];
        await root.getByRole('heading',{name:packageId,exact:true}).waitFor({timeout:90000});
        await root.getByRole('link',{name:'预览资料库',exact:true}).waitFor({timeout:90000});
        const previewPromise=page.waitForEvent('popup');
        await root.getByRole('link',{name:'预览资料库',exact:true}).click();
        const preview=await previewPromise;
        await preview.locator('.season-preview-banner').waitFor();
        if(index>0) {
          await preview.getByRole('tab',{name:'演练阶段奖励',exact:true}).click();
          await preview.getByText('演练阶段',{exact:true}).waitFor();
          assert.equal(await preview.getByRole('tab',{name:'演练规则表',exact:true}).count(),index===1?1:0);
        }
        const simPromise=page.waitForEvent('popup');
        await root.getByRole('link',{name:'预览模拟器',exact:true}).click();
        const sim=await simPromise;
        await sim.locator('.season-preview-banner').waitFor();
        const hero=index===0?'奥恩':`演练弈子补丁${index}`;
        await sim.getByRole('button',{name:'上阵 '+hero,exact:true}).click();
        assert.equal(await sim.locator('.hex-cell.has-unit').count(),1);
        await sim.close();
        await preview.close();
        await root.getByRole('button',{name:'资料差异',exact:true}).click();
        await root.getByRole('button',{name:'重新比较',exact:true}).click();
        await page.waitForFunction(()=>!Array.from(document.querySelectorAll('#seasonPackageRoot button')).find(b=>b.textContent==='审核并发布')?.disabled);
        await root.getByRole('button',{name:'审核并发布',exact:true}).click();
        const dialog=root.locator('dialog');
        if(await dialog.locator('input[type=checkbox]').count()) await dialog.locator('input[type=checkbox]').check();
        await dialog.getByRole('button',{name:'确认发布',exact:true}).click();
        await root.getByText('版本已发布，关键页面检查通过。',{exact:true}).waitFor({timeout:90000});
        await root.getByText('已发布为当前资料版本。',{exact:true}).waitFor();
        const listing=await (await auth.get('/api/admin/season-packages')).json();
        const active=listing.seasons.find(s=>s.season_id==='s99').active;
        assert.equal(active.revision,++currentRevision);
        releases.push(active.release_id);
        console.log(`${name}: ${['initial','update','hotfix'][index]} published`);
        if(index===0) {
          for(const surface of ['library','simulator']) await call('put',`/api/admin/season-display/${surface}/s99`,{status:'active'});
          await call('put','/api/admin/season-display/simulator/s99',{is_default:true});
        }
        await page.evaluate(()=>window.scrollTo(0,0));
        await page.screenshot({path:`instance/season-lifecycle-checks/${name}-${['initial','update','hotfix'][index]}.png`});
      }
      const live=await auth.post('/api/admin/live-comps/uploads/preview',{headers:{'X-CSRF-Token':csrf},multipart:{season_id:'s99',file:{name:'live.json',mimeType:'application/json',buffer:Buffer.from(JSON.stringify(fixture.live))}}});
      assert.equal(live.status(),201);
      const jid=(await live.json()).job_id;
      await call('post',`/api/admin/live-comps/uploads/${jid}/start`,{});
      const deadline=Date.now()+30000;
      while(true) {
        const job=await (await auth.get(`/api/admin/live-comps/uploads/${jid}`)).json();
        if(job.status==='completed') break;
        assert(job.status!=='failed' && Date.now()<deadline,JSON.stringify(job));
        await new Promise(resolve=>setTimeout(resolve,200));
      }
      await call('put','/api/admin/live-comps/seasons/s99',{status:'active',default_season_id:'s99'});
      const normal=await call('post','/api/lineups',{name:'S99 普通演练阵容',code:'#REHEARSALONLY1',season_id:'s99'});
      const view=await context.newPage();
      await view.goto(fixture.url+'/tools/seasons/s99');
      await view.getByRole('tab',{name:'演练阶段奖励',exact:true}).waitFor();
      assert.equal(await view.locator('.season-preview-banner').count(),0);
      await view.goto(fixture.url+'/tools/lineup-simulator?season_id=s18');
      await view.getByRole('button',{name:'上阵 奥恩',exact:true}).waitFor();
      await view.goto(fixture.url+'/tools/lineup-simulator?season_id=s99');
      await view.getByRole('button',{name:'上阵 演练弈子补丁2',exact:true}).click();
      assert.equal(await view.locator('.hex-cell.has-unit').count(),1);
      await view.goto(fixture.url+'/');
      await view.locator('#seasonFilterToggle').click();
      await view.locator('#seasonFilterMenu').getByText('S99 本地演练',{exact:true}).waitFor();
      const liveLink=view.locator('a[href*="/live-comps/"]').first();
      // Use the actual rendered details link rather than a guessed page route.
      await view.locator('#seasonFilterToggle').click();
      await liveLink.waitFor();
      await liveLink.click();
      await view.locator('.formation-cell.has-unit, .formation-cell .unit-portrait, #formationBoard img').first().waitFor();
      await view.goto(fixture.url+'/lineup/new');
      await view.locator('#editorSeasonToggle').click();
      await view.locator('#editorSeasonMenu').getByRole('button',{name:'S99 本地演练',exact:true}).click();
      assert.equal(await view.locator('#seasonSelect').inputValue(),'s99');
      await call('post','/api/admin/seasons/s99/rollback',{expected_revision:3,release_id:releases[0]});
      await view.goto(fixture.url+'/tools/seasons/s99');
      assert.equal(await view.getByRole('tab',{name:'演练阶段奖励',exact:true}).count(),0);
      assert.equal((await (await auth.get(`/api/lineups/${normal.id}`)).json()).code,'#REHEARSALONLY1');
      assert.deepEqual(errors,[]);
      await context.close();
      console.log(`${name}: create season, 3 full ZIP uploads, previews, publication, both catalogs, live/normal lineups and rollback passed`);
    } finally { await auth.dispose(); await browser.close(); await fixture.close(); }
  }
})().catch(e=>{console.error(e);process.exitCode=1;});
