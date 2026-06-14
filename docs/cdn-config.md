# CDN 配置

## 域名

| 项 | 值 |
|---|---|
| 业务域名 | `jcc.np5.top` |
| CDN CNAME | `nrnx2qs8.free-hw.fusionscdn.com` |
| 源站 IP | `45.113.1.61` |
| 回源协议 | HTTPS |
| 回源端口 | 443 |
| 回源 Host | `jcc.np5.top` |

用户访问业务域名：

```text
https://jcc.np5.top
```

不要直接访问 CDN CNAME 域名。

## DNS 配置

域名解析应配置：

```text
主机记录：jcc
记录类型：CNAME
记录值：nrnx2qs8.free-hw.fusionscdn.com
```

同一个 `jcc` 主机记录不能同时保留 A 记录和 CNAME。旧记录应删除或暂停：

```text
jcc A 45.113.1.61
```

## HTTPS 配置

CDN 证书应匹配：

```text
jcc.np5.top
```

源站也应继续保留 HTTPS 证书，供 CDN HTTPS 回源使用。

## 推荐缓存规则

| 路径 | 策略 | 原因 |
|---|---|---|
| `/static/*` | 强制缓存 7-30 天 | CSS、JS、favicon、验证码图片 |
| `/api/live-comps/assets/*` | 强制缓存 7-30 天 | 实时阵容本地化图片 |
| `/favicon.ico` | 强制缓存 30 天 | 图标资源 |
| `/api/*` | 不缓存 / BYPASS | 登录、互动、后台接口必须实时 |
| `/admin*` | 不缓存 / BYPASS | 管理员后台不能缓存 |
| `/auth*` | 不缓存 / BYPASS | 登录注册不能缓存 |
| `/me*` | 不缓存 / BYPASS | 个人中心不能缓存 |
| `/lineup/*` | 不缓存 / BYPASS | 涉及隐藏权限和浏览统计 |
| `/` | 不缓存或极短缓存 | 首页包含用户状态和实时排行 |

## 验证命令

检查 DNS：

```powershell
nslookup jcc.np5.top 1.1.1.1
```

检查访问：

```powershell
curl.exe -I https://jcc.np5.top/
curl.exe -I https://jcc.np5.top/static/styles.css
curl.exe https://jcc.np5.top/api/health
```

如果响应头出现 `X-VIA`、`X-Cache-Status` 等字段，说明请求经过 CDN。
