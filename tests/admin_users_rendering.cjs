const {chromium,webkit,request}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 fs.mkdirSync('instance/users-checks',{recursive:true});
 const auth=await request.newContext();
 assert.equal((await auth.post('http://127.0.0.1:5091/api/login',{data:{account:'previewadmin',password:'Preview1234'}})).status(),200);
 const storageState=await auth.storageState();
 for(const [name,engine] of [['edge',chromium],['webkit',webkit]]) {
 const browser=await engine.launch(name==='edge'?{channel:'msedge'}:{});
 const context=await browser.newContext({storageState});
 const page=await context.newPage(); const errors=[]; page.on('pageerror',e=>errors.push(e.message));
 await page.goto('http://127.0.0.1:5091/admin');
 await page.locator('.admin-sidebar [data-admin-tab="users"]').click();
 await page.locator('.admin-users-table').waitFor();
 for(const theme of ['light','dark'])for(const width of [320,390,768,1440]) {
 await page.setViewportSize({width,height:900});
 await page.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
 await page.waitForTimeout(500);
 assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),`${name} ${width} overflow`);
 assert.equal(await page.locator('.admin-user-person img').count(),10);
 assert(await page.locator('.admin-user-person img').first().evaluate(img=>img.complete&&img.naturalWidth>0));
 await page.screenshot({path:`instance/users-checks/${name}-${theme}-${width}.png`,fullPage:false});
 }
 await page.setViewportSize({width:1440,height:900});
 await page.getByRole('button',{name:'下一页',exact:true}).click();
 await page.getByText('第 2 / 3 页 · 共 25 条',{exact:true}).waitFor();
 await page.getByRole('button',{name:'上一页',exact:true}).click();
 await page.getByText('第 1 / 3 页 · 共 25 条',{exact:true}).waitFor();
 await page.getByRole('button',{name:'修改密码',exact:true}).first().click();
 await page.locator('#passwordInput').fill('abc12345');
 await page.locator('#confirmPasswordInput').fill('different1');
 await page.getByRole('button',{name:'保存新密码'}).click();
 await page.getByText('两次输入的密码不一致',{exact:true}).waitFor();
 await page.locator('#cancelPasswordButton').click();
 await page.getByRole('searchbox').fill('player23');
 await page.waitForFunction(()=>document.querySelectorAll('.admin-users-table tbody tr').length===1);
 assert((await page.locator('.admin-user-handle').textContent()).includes('player23'));
 await page.getByRole('searchbox').fill('no-such-user');
 await page.getByText('没有找到用户，请尝试其他用户名、昵称或邮箱',{exact:true}).waitFor();
 await page.getByRole('button',{name:'清空',exact:true}).click();
 await page.waitForFunction(()=>document.querySelectorAll('.admin-users-table tbody tr').length===10);
 assert.deepEqual(errors,[]); await browser.close(); console.log(name+' passed');
 }
 await auth.dispose();
})().catch(e=>{console.error(e);process.exit(1)});

