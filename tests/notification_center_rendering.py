"""Run against serve_notification_preview.py; mutates fictional feedback only."""
import os
import time
from pathlib import Path
from playwright.sync_api import sync_playwright, expect

BASE=os.environ.get('NOTIFICATION_PREVIEW_URL','http://127.0.0.1:5160')
OUT=Path(__file__).resolve().parents[1]/'instance/notification-review'
OUT.mkdir(parents=True,exist_ok=True)


def run():
    with sync_playwright() as p:
        browser=getattr(p, os.environ.get('NOTIFICATION_BROWSER','chromium')).launch()
        reply_text=f'已完成核验，谢谢你的建议。<script>这只是普通文本</script>（验证 {time.time_ns()}）'
        user=browser.new_context(viewport={'width':1440,'height':1000})
        page=user.new_page()
        errors=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        page.goto(BASE+'/__preview__/login/user')
        page.locator('#lineupNotificationToggle').click()
        expect(page.locator('.ln-item')).to_have_count(5)
        page.screenshot(path=str(OUT/'home-inbox.png'),full_page=True)
        page.goto(BASE+'/me#lineup-notifications')
        expect(page.locator('.pf-dialog')).to_be_visible()
        expect(page.get_by_role('heading',name='通知中心',exact=True)).to_be_visible()
        expect(page.locator('.pf-notice-row')).to_have_count(5)
        page.get_by_role('button',name='互动消息',exact=True).click()
        expect(page.locator('.pf-notice-row')).to_have_count(3)
        page.screenshot(path=str(OUT/'account-interactions.png'),full_page=True)
        page.locator('.pf-notice-open').first.click()
        expect(page.get_by_role('heading',name='收到的互动',exact=True)).to_be_visible()
        expect(page.get_by_role('link',name='查看我的阵容')).to_be_visible()
        page.get_by_role('button',name='返回通知列表').click()
        page.get_by_role('button',name='反馈进度',exact=True).click()
        expect(page.locator('.pf-notice-row')).to_have_count(2)
        page.locator('.pf-notice-open').first.click()
        expect(page.locator('.pf-feedback-timeline li').first).to_be_visible()
        page.screenshot(path=str(OUT/'feedback-desktop.png'),full_page=True)
        page.set_viewport_size({'width':390,'height':844})
        page.screenshot(path=str(OUT/'feedback-mobile.png'),full_page=True)
        assert page.locator('.pf-dialog').evaluate('el=>el.scrollWidth<=el.clientWidth+1')
        page.keyboard.press('Escape')
        expect(page.locator('.pf-dialog')).to_have_count(0)

        admin=browser.new_context(viewport={'width':1440,'height':1000})
        staff=admin.new_page()
        staff.on('pageerror',lambda e:errors.append(str(e)))
        staff.goto(BASE+'/__preview__/login/admin')
        staff.locator('button[data-admin-tab="guestbook"]:visible').first.click()
        guestcard=staff.locator('.admin-card').filter(has_text='游客留言只供站长阅读')
        expect(guestcard).to_have_count(1)
        expect(guestcard.get_by_role('button',name='查看进度 / 回复用户')).to_have_count(0)
        staff.get_by_role('button',name='查看进度 / 回复用户',exact=True).first.click()
        expect(staff.locator('.fb-dialog')).to_be_visible()
        staff.get_by_label('处理进度',exact=True).select_option('resolved')
        staff.get_by_label('站内回复',exact=True).fill(reply_text)
        staff.get_by_role('button',name='发送回复 / 更新进度').click()
        expect(staff.get_by_text('已保存，用户可查看最新进度和回复。')).to_be_visible()
        staff.screenshot(path=str(OUT/'admin-reply.png'),full_page=True)
        staff.set_viewport_size({'width':390,'height':844})
        staff.screenshot(path=str(OUT/'admin-reply-mobile.png'),full_page=True)
        assert staff.locator('.fb-dialog').evaluate('el=>el.scrollWidth<=el.clientWidth+1')
        staff.locator('.fb-head button').click()
        expect(staff.locator('.fb-dialog')).to_have_count(0)

        page.goto(BASE+'/me#lineup-notifications')
        page.get_by_role('button',name='反馈进度',exact=True).click()
        page.locator('.pf-notice-row').filter(has_text='给站长的留言').locator('.pf-notice-open').click()
        expect(page.get_by_text(reply_text,exact=True)).to_be_visible()
        expect(page.locator('.pf-feedback-timeline')).to_contain_text('已解决')
        page.keyboard.press('Escape')
        page.evaluate("document.documentElement.dataset.theme='dark'")
        page.goto(BASE+'/me#lineup-notifications')
        page.evaluate("document.documentElement.dataset.theme='dark'")
        expect(page.locator('.pf-dialog')).to_be_visible()
        page.screenshot(path=str(OUT/'inbox-dark-mobile.png'),full_page=True)
        assert not errors,errors
        browser.close()
        print('PASS: homepage inbox, categories, interaction detail, feedback timeline, admin reply, guest exclusion, mobile layout, escaping and keyboard close; no page errors.')


if __name__=='__main__':
    run()
