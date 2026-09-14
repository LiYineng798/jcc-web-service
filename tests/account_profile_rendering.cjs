// Run only against tests/serve_account_profile_preview.py (fictional SQLite data).
const { chromium, webkit } = require("playwright");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const base = process.env.ACCOUNT_PROFILE_PREVIEW_URL || "http://127.0.0.1:5113";
const out = "instance/profile-checks";
async function loaded(page) {
  await page.locator(".pf-loading").waitFor({ state: "detached" });
}
async function select(page, id) {
  await page.locator(`#tab-${id}`).click();
  await page.locator(`#profile-panel[aria-labelledby="tab-${id}"]`).waitFor();
  await loaded(page);
}
(async () => {
  fs.mkdirSync(out, { recursive: true });
  for (const [name, engine] of [
    ["chromium", chromium],
    ["webkit", webkit],
  ]) {
    const browser = await engine.launch(
      name === "chromium"
        ? { channel: process.env.PLAYWRIGHT_CHROMIUM_CHANNEL || "msedge" }
        : {},
    );
    const context = await browser.newContext({
      viewport: { width: 1440, height: 900 },
    });
    const page = await context.newPage(),
      errors = [],
      requests = [];
    page.on("pageerror", (error) => {
      errors.push(error.message);
      console.error(
        "Browser error at",
        page.url(),
        error.stack,
        requests.slice(-6),
      );
    });
    page.on("request", (request) => {
      if (request.url().includes("/api/")) requests.push(request.url());
    });
    await page.goto(`${base}/__preview/login`);
    await page.locator(".pf-recent-row").first().waitFor();
    assert(
      !requests.some((url) =>
        /\/api\/me\/reports|view=mine|view=favorites/.test(url),
      ),
      "inactive workspaces are loaded on demand",
    );
    const summary = await (
      await context.request.get(`${base}/api/me/dashboard`)
    ).json();
    assert.equal(
      (await page.locator(".pf-stat > strong").allTextContents()).join(","),
      [
        summary.published_lineups,
        summary.received_likes,
        summary.received_favorites,
        summary.received_copies,
      ].join(","),
    );
    for (const width of [1440, 1366, 1024, 768, 390, 320]) {
      await page.setViewportSize({
        width,
        height: width >= 1024 ? (width === 1440 ? 900 : 768) : 844,
      });
      for (const theme of ["light", "dark"]) {
        await page.evaluate((theme) => {
          document.documentElement.dataset.theme = theme;
          localStorage.setItem("theme", theme);
        }, theme);
        const bounds = await page.evaluate(() => ({
          width: innerWidth,
          height: innerHeight,
          sw: document.documentElement.scrollWidth,
          sh: document.documentElement.scrollHeight,
          footer: document.querySelector(".pf-footer").getBoundingClientRect()
            .bottom,
        }));
        assert(
          bounds.sw <= bounds.width + 1,
          `${name}/${width}/${theme}: no horizontal overflow`,
        );
        if (width >= 1024)
          assert(
            bounds.sh <= bounds.height + 1,
            `${name}/${width}: document does not scroll vertically`,
          );
        if (width >= 1366)
          assert(
            bounds.footer < bounds.height,
            `${name}/${width}: complete overview fits without scrolling`,
          );
        for (const tab of await page.locator("[role=tab]").all()) {
          const box = await tab.boundingBox();
          assert(box.x >= 0 && box.x + box.width <= width + 1);
        }
        if ([1440, 390].includes(width))
          await page.screenshot({
            path: `${out}/${name}-${width}-${theme}.png`,
            fullPage: width > 760,
            animations: "disabled",
          });
      }
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    await page.evaluate(() => {
      document.documentElement.dataset.theme = "light";
      localStorage.setItem("theme", "light");
    });
    await page.reload();
    await page.locator(".pf-recent-row").first().waitFor();
    await page
      .getByRole("button", { name: "切换为夜间模式", exact: true })
      .click();
    await page.reload();
    await page.locator(".pf-recent-row").first().waitFor();
    assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
    await page
      .getByRole("button", { name: "切换为白天模式", exact: true })
      .click();
    await select(page, "mine");
    let count = 0,
      ids = new Set();
    do {
      await loaded(page);
      for (const href of await page
        .locator(".pf-lineup-card h2 a")
        .evaluateAll((nodes) => nodes.map((n) => n.getAttribute("href"))))
        ids.add(href);
      count++;
      if (
        await page
          .getByRole("button", { name: "下一页", exact: true })
          .isDisabled()
      )
        break;
      await page.getByRole("button", { name: "下一页", exact: true }).click();
    } while (count < 10);
    assert.equal(
      ids.size,
      summary.published_lineups,
      "all own lineups reachable, including entries after twenty",
    );
    await page.getByRole("searchbox").fill("仙灵九五");
    await page.getByRole("button", { name: "搜索", exact: true }).click();
    await loaded(page);
    assert.equal(await page.locator(".pf-lineup-card").count(), 1);
    await page.getByRole("button", { name: "清空搜索", exact: true }).click();
    await loaded(page);
    const banned = page
      .getByRole("link", { name: "查看封禁与重审", exact: true })
      .first();
    if (!(await banned.count())) {
      await page.getByRole("button", { name: "下一页", exact: true }).click();
      await loaded(page);
    }
    assert(
      (await banned.getAttribute("href")).startsWith(
        "/me/lineup-notifications/",
      ),
    );
    for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }]) {
      await page.setViewportSize(viewport);
      const pagerBounds = await page.locator('.pf-pagination').boundingBox();
      assert(pagerBounds.y + pagerBounds.height < viewport.height, 'lineup pagination fits in the initial desktop viewport');
    }
    await page.screenshot({ path: `${out}/${name}-mine.png`, fullPage: true });
    await select(page, "favorites");
    const favoriteCount = (
      await (
        await context.request.get(
          `${base}/api/lineups?view=favorites&page=1&page_size=6`,
        )
      ).json()
    ).total;
    const favorite = page.getByRole("button", { name: /^取消收藏：/ }).first();
    const card = favorite.locator("xpath=ancestor::article");
    const favoriteId = (await card.locator("h2 a").getAttribute("href"))
      .split("/")
      .pop();
    await favorite.click();
    await loaded(page);
    assert.equal(
      (
        await (
          await context.request.get(
            `${base}/api/lineups?view=favorites&page=1&page_size=6`,
          )
        ).json()
      ).total,
      favoriteCount - 1,
    );
    const me = await (await context.request.get(`${base}/api/me`)).json();
    await context.request.post(`${base}/api/lineups/${favoriteId}/favorite`, {
      headers: { "X-CSRF-Token": me.csrf_token },
    });
    await select(page, "views");
    if (name === "chromium") {
      await context.grantPermissions(["clipboard-read", "clipboard-write"]);
      await page
        .getByRole("button", { name: /^复制阵容码：/ })
        .first()
        .click();
      await page.locator(".jcc-notification.is-success").first().waitFor();
      assert(
        (await page.evaluate(() => navigator.clipboard.readText())).startsWith(
          "#OTHERDEMO",
        ),
      );
    } else {
      await page.evaluate(() =>
        Object.defineProperty(navigator, "clipboard", {
          configurable: true,
          value: undefined,
        }),
      );
      await page
        .getByRole("button", { name: /^复制阵容码：/ })
        .first()
        .click();
      await page.locator(".jcc-notification.is-success").first().waitFor();
    }
    await select(page, "reports");
    await page.getByRole("button", { name: "已处理", exact: true }).click();
    assert(await page.locator(".pf-report-card").count());
    assert(
      (
        await page.locator(".pf-report-card .pf-status").allTextContents()
      ).every((x) => x === "已处理"),
    );
    await page.getByRole("searchbox").fill("不存在的匹配");
    await page.getByRole("button", { name: "搜索", exact: true }).click();
    await page.getByText("没有找到匹配的内容", { exact: true }).waitFor();
    await page.getByRole("button", { name: "清除筛选", exact: true }).click();
    await page.route("**/api/me/recent-copies", (route) =>
      route.fulfill({ status: 503, json: { error: "测试网络错误" } }),
    );
    await select(page, "copies");
    await page.getByText("测试网络错误", { exact: true }).waitFor();
    await page.unroute("**/api/me/recent-copies");
    await page.getByRole("button", { name: "重新加载", exact: true }).click();
    await loaded(page);
    await page.locator(".pf-lineup-card").first().waitFor();
    // A slow request must never replace the next workspace.
    let release;
    const held = new Promise((resolve) => {
      release = resolve;
    });
    await page.route("**/api/me/reports", async (route) => {
      await held;
      await route.fulfill({ json: [] }).catch(() => {});
    });
    await select(page, "mine");
    const reportRequest = page.waitForRequest("**/api/me/reports");
    await page.locator("#tab-reports").click();
    await reportRequest;
    await select(page, "favorites");
    release();
    await page.unroute("**/api/me/reports");
    assert.equal(
      await page.locator("#profile-panel").getAttribute("aria-labelledby"),
      "tab-favorites",
    );
    // Avatar dialog uses the existing save API and synchronizes both profile avatars.
    await page.goto(`${base}/me#avatar`);
    await page.locator(".avatar-dialog[open]").waitFor();
    const newColor = name === "chromium" ? "#637bb2" : "#b56949";
    await page.locator("#avatarHex").fill(newColor);
    await page.getByRole("button", { name: "保存头像", exact: true }).click();
    await page.locator(".avatar-dialog[open]").waitFor({ state: "detached" });
    const saved = await (await context.request.get(`${base}/api/me`)).json();
    assert.equal(saved.user.avatar_color, newColor);
    await page.reload();
    await page.locator(".avatar-dialog[open]").waitFor();
    await page.getByRole("button", { name: "取消", exact: true }).click();
    assert.equal(await page.locator(".pf-avatar").count(), 2);
    await select(page, "mine");
    await page.locator("#tab-mine").focus();
    await page.keyboard.press("ArrowRight");
    await page
      .locator('#profile-panel[aria-labelledby="tab-favorites"]')
      .waitFor();
    await loaded(page);
    assert.equal(
      await page.evaluate(() => document.activeElement.id),
      "tab-favorites",
    );
    await page.reload();
    await page
      .locator('#profile-panel[aria-labelledby="tab-favorites"]')
      .waitFor();
    await loaded(page);
    for (const width of [320, 390, 768]) {
      await page.setViewportSize({ width, height: 844 });
      for (const tab of ["mine", "favorites", "views", "copies", "reports"]) {
        await select(page, tab);
        assert(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth + 1,
          ),
          `${name}/${width}/${tab}: content fits`,
        );
        if (width <= 760) {
          await page.evaluate(() =>
            window.scrollTo(0, document.documentElement.scrollHeight),
          );
          const nav = await page.locator(".pf-tabs").boundingBox();
          assert(
            Math.abs(nav.y + nav.height - 844) <= 1,
            "mobile navigation stays at viewport bottom",
          );
        }
      }
      await select(page, "overview");
      if (width <= 760)
        assert.equal(
          await page.evaluate(() => scrollY),
          0,
          "mobile tab change starts at top",
        );
    }
    await page.setViewportSize({ width: 1440, height: 900 });
    // Empty accounts have genuine zero/empty states; admin public profile is unavailable by design.
    await page.goto(`${base}/__preview/login?user=empty`);
    await loaded(page);
    await page.locator(".pf-stats[aria-busy=false]").waitFor();
    assert.deepEqual(
      await page.locator(".pf-stat > strong").allTextContents(),
      ["0", "0", "0", "0"],
    );
    await select(page, "mine");
    await page
      .getByRole("link", { name: "发布第一套阵容", exact: true })
      .waitFor();
    await page.goto(`${base}/__preview/login?user=admin`);
    await page.locator(".pf-stats[aria-busy=false]").waitFor();
    assert.equal(
      await page.getByRole("link", { name: "公开主页", exact: false }).count(),
      0,
    );
    await page.getByRole("button", { name: "退出登录", exact: true }).click();
    await page.waitForURL(base + "/");
    assert.equal(
      (await (await context.request.get(`${base}/api/me`)).json()).user,
      null,
    );
    assert.deepEqual(errors, [], `${name}: no runtime errors`);
    await browser.close();
    console.log(
      `${name}: responsive layout, real data, pagination, search, favorites, copy, filters, retry, race isolation, avatar, keyboard, deep links, empty/admin/logout passed`,
    );
  }
})().catch((error) => {
  console.error(error);
  process.exit(1);
});
