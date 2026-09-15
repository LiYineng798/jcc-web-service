// Run only against serve_account_profile_preview.py with disposable fictional data.
const { chromium, webkit, expect } = require("playwright/test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const base = process.env.ACCOUNT_PROFILE_PREVIEW_URL || "http://127.0.0.1:5114";
const out = "instance/profile-dialog-checks";

(async () => {
  fs.mkdirSync(out, { recursive: true });
  for (const [engineName, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const browser = await engine.launch(
      engineName === "chromium" ? { channel: "msedge" } : {},
    );
    try {
      const context = await browser.newContext({
        viewport: { width: 1440, height: 900 },
      });
      const admin = await browser.newContext();
      await context.request.get(`${base}/__preview/login?user=empty`);
      await admin.request.get(`${base}/__preview/login?user=admin`);
      const token = (await (await context.request.get(`${base}/api/me`)).json())
        .csrf_token;
      const adminToken = (
        await (await admin.request.get(`${base}/api/me`)).json()
      ).csrf_token;
      const api = async (path, method = "GET", data, elevated = false) => {
        const response = await (elevated ? admin : context).request.fetch(
          `${base}${path}`,
          {
            method,
            data,
            headers: { "X-CSRF-Token": elevated ? adminToken : token },
          },
        );
        assert(
          response.ok(),
          `${method} ${path}: ${response.status()} ${await response.text()}`,
        );
        return response.status() === 204 ? null : response.json();
      };
      const season = (await api("/api/lineup-seasons")).seasons[0].id;
      const prefix = `浮窗验收${engineName}${Date.now()}`;
      const create = (suffix) =>
        api("/api/lineups", "POST", {
          name: prefix + suffix,
          code: `#DIALOG${Date.now()}${suffix}`,
          season_id: season,
          status: "normal",
        });
      const moderate = async (
        id,
        action,
        reason = "请修正阵容码与赛季的对应关系。",
      ) => {
        const detail = await api(`/api/lineups/${id}/moderation`);
        return api(
          `/api/admin/lineups/${id}/moderation/${action}`,
          "POST",
          { version: detail.lineup.version, reason },
          true,
        );
      };
      const ordinary = await create("A");
      const restricted = await create("B");
      await moderate(restricted.id, "ban");
      for (let i = 0; i < 6; i++)
        await moderate((await create(`N${i}`)).id, "ban");
      const page = await context.newPage();
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto(`${base}/me#mine`);
      await page.locator(".pf-lineup-card").first().waitFor();
      const search = async (query) => {
        await page.getByRole("searchbox").fill(query);
        const response = page.waitForResponse(
          (r) => r.url().includes("/api/lineups?") && r.url().includes("q="),
        );
        await page.getByRole("button", { name: "搜索", exact: true }).click();
        await response;
        await page.locator(".pf-loading").waitFor({ state: "detached" });
      };
      const close = () =>
        page.getByRole("button", { name: "关闭浮窗", exact: true }).click();
      const openNormal = async () => {
        await search(ordinary.name);
        await page
          .getByRole("button", { name: "编辑阵容", exact: true })
          .click();
        await page.locator("#pfEditName").waitFor();
      };
      await openNormal();
      const originalUrl = page.url();
      await expect(page.locator("#pfEditName")).toHaveValue(ordinary.name);
      // The browser's top-layer dialog contains keyboard focus and locks the background.
      for (let i = 0; i < 10; i++) {
        await page.keyboard.press("Tab");
        assert(
          await page.evaluate(
            () =>
              document.activeElement === document.body ||
              !!document.activeElement.closest("dialog"),
          ),
        );
      }
      assert.equal(
        await page.evaluate(() => document.body.style.overflow),
        "hidden",
      );
      await page.keyboard.press("Escape");
      await expect(page.locator("dialog[open]")).toHaveCount(0);
      await expect(
        page.getByRole("button", { name: "编辑阵容", exact: true }),
      ).toBeFocused();
      assert.equal(page.url(), originalUrl);
      assert.equal(await page.evaluate(() => document.body.style.overflow), "");

      await page.getByRole("button", { name: "编辑阵容", exact: true }).click();
      await page.locator("#pfEditName").fill(ordinary.name + "草稿");
      await close();
      await expect(
        page.getByText("还有未保存的修改", { exact: true }),
      ).toBeVisible();
      await page.getByRole("button", { name: "继续编辑", exact: true }).click();
      await expect(page.locator("#pfEditName")).toHaveValue(
        ordinary.name + "草稿",
      );
      await page.keyboard.press("Escape");
      await page.getByRole("button", { name: "放弃修改", exact: true }).click();
      assert.equal(
        (await api(`/api/lineups/${ordinary.id}`)).name,
        ordinary.name,
      );

      // A concurrent edit must retain the draft and require an explicit reload.
      await page.getByRole("button", { name: "编辑阵容", exact: true }).click();
      await page.locator("#pfEditName").fill(ordinary.name + "草稿");
      await api(`/api/lineups/${ordinary.id}`, "PUT", {
        ...ordinary,
        name: ordinary.name + "服务器",
        version: ordinary.version,
      });
      await page.getByRole("button", { name: "保存修改", exact: true }).click();
      await expect(
        page.getByText("你的输入已保留。", { exact: false }),
      ).toBeVisible();
      await expect(page.locator("#pfEditName")).toHaveValue(
        ordinary.name + "草稿",
      );
      await page
        .getByRole("button", { name: "重新加载最新阵容", exact: true })
        .click();
      await page
        .getByRole("button", { name: "放弃输入并加载", exact: true })
        .click();
      await expect(page.locator("#pfEditName")).toHaveValue(
        ordinary.name + "服务器",
      );
      await page.locator("#pfEditName").fill(ordinary.name + "保存");
      await page
        .locator("#pfEditCode")
        .fill("分享文案 ＃SHORT #DIALOGVALID123456789");
      await page.getByRole("checkbox", { name: /隐藏阵容/ }).check();
      let releaseSave, saveStarted;
      const saveGate = new Promise((resolve) => {
        releaseSave = resolve;
      });
      const started = new Promise((resolve) => {
        saveStarted = resolve;
      });
      let writes = 0;
      await page.route(`**/api/lineups/${ordinary.id}`, async (route) => {
        if (route.request().method() !== "PUT") return route.continue();
        writes++;
        saveStarted();
        await saveGate;
        await route.continue();
      });
      await page.getByRole("button", { name: "保存修改", exact: true }).click();
      await started;
      await expect(
        page.getByRole("button", { name: "关闭浮窗", exact: true }),
      ).toBeDisabled();
      await page.keyboard.press("Escape");
      await expect(page.locator("dialog[open]")).toHaveCount(1);
      releaseSave();
      await expect(page.locator("dialog[open]")).toHaveCount(0);
      await page.unroute(`**/api/lineups/${ordinary.id}`);
      await expect(page.locator(".pf-lineup-card h2")).toHaveText(
        ordinary.name + "保存",
      );
      await expect(page.getByRole("searchbox")).toHaveValue(ordinary.name);
      assert.equal(page.url(), originalUrl);
      assert.equal(writes, 1);
      const persisted = await api(`/api/lineups/${ordinary.id}`);
      assert.equal(persisted.code, "#DIALOGVALID123456789");
      assert.equal(persisted.status, "hidden");

      // An unavailable original season must never silently become the default.
      await page.route(`**/api/lineups/${ordinary.id}`, (route) =>
        route.fulfill({
          json: {
            ...persisted,
            can_edit: true,
            season_id: "unavailable-season",
          },
        }),
      );
      await page.getByRole("button", { name: "编辑阵容", exact: true }).click();
      await expect(page.locator("#pfEditSeason")).toHaveValue("");
      await expect(
        page.getByText("原赛季已不可用，请重新选择后保存。"),
      ).toBeVisible();
      assert.equal(
        await page
          .locator("#pfEditSeason")
          .evaluate((node) => node.checkValidity()),
        false,
      );
      await close();
      await expect(page.locator("dialog[open]")).toHaveCount(0);
      await page.unroute(`**/api/lineups/${ordinary.id}`);

      // Mark only the revision actually displayed; a newer notice stays unread.
      await search(restricted.name);
      let raced = false;
      await page.route(
        `**/api/me/lineup-notifications/${restricted.id}`,
        async (route) => {
          if (!raced && route.request().method() === "PUT") {
            raced = true;
            await moderate(restricted.id, "release", "更新的处理结果");
          }
          await route.continue();
        },
      );
      await page
        .getByRole("button", { name: "查看封禁与重审", exact: true })
        .click();
      await expect(
        page.getByText("已读状态未更新：", { exact: false }),
      ).toBeVisible();
      assert.equal(
        (await api(`/api/lineups/${restricted.id}/moderation`)).moderation
          .notice_state,
        "unread",
      );
      await page
        .getByRole("button", { name: "重新加载最新通知", exact: true })
        .click();
      await expect(page.locator(".pf-record-heading")).toContainText(
        "已解除封禁",
      );
      await expect
        .poll(
          async () =>
            (await api(`/api/lineups/${restricted.id}/moderation`)).moderation
              .notice_state,
        )
        .toBe("read");
      await page.unroute(`**/api/me/lineup-notifications/${restricted.id}`);
      await close();
      await moderate(restricted.id, "ban");
      await page.reload();
      await page.locator(".pf-lineup-card").first().waitFor();
      await search(restricted.name);
      let failedRead = false;
      await page.route(
        `**/api/me/lineup-notifications/${restricted.id}`,
        (route) => {
          if (!failedRead && route.request().method() === "PUT") {
            failedRead = true;
            return route.fulfill({
              status: 503,
              json: { error: "模拟网络暂时不可用" },
            });
          }
          return route.continue();
        },
      );
      await page
        .getByRole("button", { name: "查看封禁与重审", exact: true })
        .click();
      await expect(
        page.getByText("已读状态未更新：", { exact: false }),
      ).toBeVisible();
      await page
        .getByRole("button", { name: "重新加载最新通知", exact: true })
        .click();
      await expect
        .poll(
          async () =>
            (await api(`/api/lineups/${restricted.id}/moderation`)).moderation
              .notice_state,
        )
        .toBe("read");
      await page.unroute(`**/api/me/lineup-notifications/${restricted.id}`);
      await page
        .getByRole("button", { name: "修改并申请重审", exact: true })
        .click();
      await page.locator("#pfEditName").fill(restricted.name + "修改");
      await page.locator("#pfEditCode").fill("#DIALOGREVISION123");
      assert.equal(await page.getByRole("checkbox").count(), 0);
      const revisionRequest = page.waitForRequest(
        (r) =>
          r.url().endsWith(`/api/lineups/${restricted.id}/revision`) &&
          r.method() === "POST",
      );
      await page
        .getByRole("button", { name: "提交修改并申请重审", exact: true })
        .click();
      assert(!Object.hasOwn((await revisionRequest).postDataJSON(), "status"));
      await expect(page.locator(".pf-record-heading")).toContainText("待审核");
      assert.equal(
        await page
          .getByRole("button", { name: "修改并申请重审", exact: true })
          .count(),
        0,
      );
      const pending = await api(`/api/lineups/${restricted.id}/moderation`);
      assert.equal(pending.lineup.code, restricted.code);
      assert.equal(pending.moderation.proposal.code, "#DIALOGREVISION123");
      assert.equal(page.url(), originalUrl);
      await page.screenshot({ path: `${out}/${engineName}-revision.png` });
      await close();

      // Header and overview entry share the in-page inbox; list state survives details.
      await page.getByRole("button", { name: /^查看通知/ }).click();
      await page.locator(".pf-notice-open").first().waitFor();
      await page
        .getByRole("button", { name: "通知下一页", exact: true })
        .click();
      await expect(page.locator(".pf-dialog .pf-pagination")).toContainText(
        "2 /",
      );
      const pageTwoIds = await page
        .locator(".pf-notice-row")
        .evaluateAll((nodes) => nodes.map((n) => n.dataset.noticeId));
      await page.locator(".pf-notice-open").first().click();
      await page.locator(".pf-moderation-detail").waitFor();
      await page
        .getByRole("button", { name: "返回通知列表", exact: true })
        .click();
      await expect(page.locator(".pf-dialog .pf-pagination")).toContainText(
        "2 /",
      );
      assert.deepEqual(
        await page
          .locator(".pf-notice-row")
          .evaluateAll((nodes) => nodes.map((n) => n.dataset.noticeId)),
        pageTwoIds,
      );
      await page.getByRole("button", { name: /^已读/ }).click();
      await page.locator(".pf-notice-open").first().waitFor();
      await page
        .getByRole("button", { name: "标记未读", exact: true })
        .first()
        .click();
      await page.getByRole("button", { name: /^未读/ }).click();
      await page.locator(".pf-notice-row.is-unread").first().waitFor();
      const totalUnread = (
        await api(
          "/api/me/lineup-notifications?status=unread&page=1&page_size=1",
        )
      ).counts.unread;
      await expect(page.locator(".pf-notice-count")).toHaveText(
        String(totalUnread),
      );
      assert.equal(page.url(), originalUrl);
      await page.screenshot({ path: `${out}/${engineName}-notifications.png` });
      // Backdrop clicks close without changing the underlying workspace.
      await page.mouse.click(2, 2);
      await expect(page.locator("dialog[open]")).toHaveCount(0);
      await expect(page.getByRole("searchbox")).toHaveValue(restricted.name);
      await page.locator("#tab-overview").click();
      await page.getByRole("button", { name: /查看阵容处理通知/ }).click();
      await page.locator(".pf-notice-open").first().waitFor();
      await close();

      // Every dialog stays within the viewport in light/dark themes on narrow screens.
      for (const width of [390, 320]) {
        await page.setViewportSize({ width, height: 844 });
        for (const theme of ["light", "dark"]) {
          await page.evaluate((t) => {
            document.documentElement.dataset.theme = t;
          }, theme);
          await page.getByRole("button", { name: /^查看通知/ }).click();
          await page.locator(".pf-notice-open").first().waitFor();
          for (const screen of ["notifications", "detail", "edit"]) {
            if (screen === "detail") {
              await page
                .locator(
                  `.pf-notice-row:has(.pf-dialog-status-banned) .pf-notice-open`,
                )
                .first()
                .click();
              await page.locator(".pf-moderation-detail").waitFor();
            }
            if (screen === "edit") {
              await page
                .getByRole("button", { name: "修改并申请重审", exact: true })
                .click();
              await page.locator("#pfEditName").waitFor();
            }
            const bounds = await page
              .locator(".pf-dialog")
              .evaluate((node) => ({
                x: node.getBoundingClientRect().x,
                right: node.getBoundingClientRect().right,
                y: node.getBoundingClientRect().y,
                bottom: node.getBoundingClientRect().bottom,
                sw: node.scrollWidth,
                cw: node.clientWidth,
              }));
            assert(
              bounds.x >= 0 &&
                bounds.right <= width &&
                bounds.y >= 0 &&
                bounds.bottom <= 844 &&
                bounds.sw <= bounds.cw + 1,
              JSON.stringify({ width, theme, screen, bounds }),
            );
            await expect(
              page.getByRole("button", { name: "关闭浮窗", exact: true }),
            ).toBeInViewport();
            if (width === 390)
              await page.screenshot({
                path: `${out}/${engineName}-${width}-${theme}-${screen}.png`,
              });
          }
          await close();
        }
      }
      await page.goto(`${base}/me#lineup-notifications`);
      await page.locator(".pf-notice-open").first().waitFor();
      assert.equal(new URL(page.url()).pathname, "/me");
      await close();
      assert.equal(new URL(page.url()).hash, "");
      assert.deepEqual(errors, []);
      console.log(
        `${engineName}: local dialogs, edits/conflicts, re-review, read revisions, pagination, focus, mobile/themes passed`,
      );
    } finally {
      await browser.close();
    }
  }
})().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
