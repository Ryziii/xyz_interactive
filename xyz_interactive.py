#!/usr/bin/env python3
"""
小宇宙播客 RSS 生成器 (交互版)
读取你的订阅列表 → 选号 → 拉全集 → 生成 RSS

用法:
  python3 xyz_interactive.py               # 交互选择播客
  python3 xyz_interactive.py <PID>         # 直接拉（跳过选择）
  python3 xyz_interactive.py --setup       # 重新配置 token

首次使用:
  运行后会提示输入 refresh token 和 device id。
  获取方式看下面的说明。

配置保存: ~/.xyz_config.json (refresh token + device id)
输出目录: ~/Downloads/xyz_播客名_pid.xml
"""

import os, sys, time, re, json, urllib.request, urllib.error, ssl, html
ssl._create_default_https_context = ssl._create_unverified_context

CFG = os.path.expanduser('~/.xyz_config.json')
OUT_DIR = os.path.expanduser('~/Downloads')
LIMIT = 30

# ══════════════════════════════════════════════════
#  获取 refresh token 和 device id 的说明
# ══════════════════════════════════════════════════

HELP = """
如何获取 refresh token 和 device id
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

需要: Surge (iOS/macOS) 或任何能抓 HTTP 请求的工具

1. 打开小宇宙 app，随便点几个页面
2. Surge → HTTP Capture → Start
3. 等几秒后 Stop Capture
4. 在捕获记录里找一个 api.xiaoyuzhoufm.com 的请求

找到以下两个值:

  x-jike-refresh-token  (在 Cookie 头里, x-jike-refresh-token=...)
  x-jike-device-id      (在请求头里, x-jike-device-id: ...)

在 Surge 里可以在请求的 Header 面板中直接复制。

如果使用其他抓包工具:
  · 找 cookie 中的 x-jike-refresh-token 值
  · 找 x-jike-device-id 请求头的值

把这两个值粘贴到下面的提示中即可。
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

# ══════════════════════════════════════════════════
#  Token 管理
# ══════════════════════════════════════════════════

def load_cfg():
    if os.path.exists(CFG):
        with open(CFG) as f: return json.load(f)
    return {}

def save_cfg(c):
    with open(CFG, 'w') as f: json.dump(c, f, indent=2)

def refresh_token(rt, di):
    h = {'Content-Type': 'application/json', 'x-jike-refresh-token': rt,
         'x-jike-device-id': di, 'applicationid': 'app.podcast.cosmos'}
    req = urllib.request.Request('https://api.xiaoyuzhoufm.com/app_auth_tokens.refresh',
                                 data=b'{}', headers=h, method='POST')
    with urllib.request.urlopen(req, timeout=10) as r:
        d = json.loads(r.read())
        if d.get('success'):
            return d['x-jike-access-token'], d.get('x-jike-refresh-token', rt)
    return None, None

def setup_config():
    """交互式输入 refresh token 和 device id，保存配置"""
    print(HELP)
    print('请粘贴你从 Surge 中获取到的值:\n')
    
    rt = input('x-jike-refresh-token: ').strip()
    if not rt:
        print('[!] refresh token 不能为空')
        sys.exit(1)
    
    di = input('x-jike-device-id: ').strip()
    if not di:
        print('[!] device id 不能为空')
        sys.exit(1)
    
    # 验证：尝试 refresh
    print('\n正在验证...')
    at, nr = refresh_token(rt, di)
    if at:
        save_cfg({'rt': nr or rt, 'di': di})
        print(f'[✓] 验证通过，配置已保存到 {CFG}')
        return at, di
    else:
        print('[!] 验证失败，检查 refresh token 和 device id 是否正确')
        sys.exit(1)

def get_token():
    cfg = load_cfg()
    
    # 无配置或 --setup 参数
    if not cfg.get('rt') or not cfg.get('di') or '--setup' in sys.argv:
        return setup_config()
    
    rt = cfg['rt']
    di = cfg['di']
    
    # 尝试刷新
    at, nr = refresh_token(rt, di)
    if at:
        # 保存新的 refresh token（server 做了 rotation）
        cfg['rt'] = nr or rt
        save_cfg(cfg)
        return at, di
    
    # 刷新失败，提示重配
    print(f'\n[!] token 刷新失败（可能已过期），需要重新配置')
    ans = input('是否重新输入 refresh token? (y/N): ').strip().lower()
    if ans == 'y':
        return setup_config()
    else:
        sys.exit(1)

# ══════════════════════════════════════════════════
#  API
# ══════════════════════════════════════════════════

def api(path, data=None, token=None, device=None, method='POST'):
    hdr = {'Content-Type': 'application/json'}
    if token: hdr['x-jike-access-token'] = token
    if device: hdr['x-jike-device-id'] = device
    body = json.dumps(data, ensure_ascii=False).encode() if data else None
    url = f'https://api.xiaoyuzhoufm.com{path}'
    req = urllib.request.Request(url, data=body, headers=hdr, method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            c = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', ' ', r.read().decode('utf-8', 'replace'))
            return json.loads(c)
    except urllib.error.HTTPError as e:
        print(f'  [!] HTTP {e.code}')
        return None

# ══════════════════════════════════════════════════
#  获取订阅列表
# ══════════════════════════════════════════════════

def get_subscriptions(token, device):
    all_subs = []
    lmk = None
    page = 0
    while True:
        page += 1
        body = {'limit': 50, 'sortBy': 'subscribedAt'}
        if lmk: body['loadMoreKey'] = lmk
        r = api('/v1/subscription/list', body, token, device)
        if not r: break
        data = r.get('data', [])
        if not data: break
        all_subs.extend(data)
        lmk = r.get('loadMoreKey') or r.get('loadNextKey')
        if not lmk: break
    return all_subs

# ══════════════════════════════════════════════════
#  获取单播客全集
# ══════════════════════════════════════════════════

def get_episodes(token, device, pid):
    all_eps, lmk, page = [], None, 0
    while True:
        page += 1
        body = {'pid': pid, 'limit': LIMIT}
        if lmk: body['loadMoreKey'] = lmk
        r = api('/v1/episode/list', body, token, device)
        if not r: break
        eps = r.get('data', [])
        if not eps: break
        all_eps.extend(eps)
        lmk = r.get('loadMoreKey') or r.get('loadNextKey')
        if not lmk: break
        time.sleep(0.2)
    return all_eps

# ══════════════════════════════════════════════════
#  生成 RSS
# ══════════════════════════════════════════════════

def gen_rss(eps, pid):
    if not eps: return
    eps.sort(key=lambda x: x.get('pubDate',''), reverse=True)
    pt = eps[0].get('podcast',{})
    title = pt.get('title','播客')
    author = pt.get('author','')
    image = (pt.get('image') or {}).get('smallPicUrl','')
    xyz = sum(1 for e in eps if 'media.xyzcdn.net' in (e.get('enclosure',{}) or {}).get('url',''))

    print(f'  [✓] {title}: {len(eps)} 集, 高质量音频: {xyz}/{len(eps)}')

    items = '\n'.join(
        f'    <item>\n      <title><![CDATA[{e.get("title","").replace("]]>","]]]]><![CDATA[")}]]></title>\n'
        f'      <description><![CDATA[{(e.get("description") or "")[:1000].replace("]]>","]]]]><![CDATA[")}]]></description>\n'
        f'      <enclosure url="{e.get("enclosure",{}).get("url","")}" type="audio/mp4" length="0"/>\n'
        f'      <guid isPermaLink="false">xyz-{e.get("eid","")}</guid>\n'
        f'      <link>https://www.xiaoyuzhoufm.com/episode/{e.get("eid","")}</link>\n'
        f'      <pubDate>{e.get("pubDate","")}</pubDate>\n'
        f'      <itunes:duration>{e.get("duration",0)}</itunes:duration>\n'
        f'      <itunes:image href="{(e.get("image") or {}).get("smallPicUrl",image)}"/>\n    </item>'
        for e in eps
    )

    safe_name = re.sub(r'[\\/:*?"<>|]', '_', title)
    out_path = os.path.join(OUT_DIR, f'xyz_{safe_name}_{pid[-8:]}.xml')

    rss = f'''<?xml version="1.0" encoding="UTF-8"?>
<rss xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" version="2.0">
<channel>
  <title>{html.escape(title)} (全量 {len(eps)} 集)</title>
  <link>https://www.xiaoyuzhoufm.com/podcast/{pid}</link>
  <description>小宇宙 API 全量导出, {len(eps)} 集</description>
  <language>zh-cn</language>
  <itunes:author>{html.escape(author)}</itunes:author>
  <itunes:image href="{image}"/>
{items}
</channel>
</rss>'''
    with open(out_path, 'w', encoding='utf-8') as f: f.write(rss)
    print(f'  [✓] 保存: {out_path}  ({os.path.getsize(out_path)/1024:.0f} KB)')
    return out_path

# ══════════════════════════════════════════════════
#  交互
# ══════════════════════════════════════════════════

def vis_width(s):
    w = 0
    for c in s:
        if '\u4e00' <= c <= '\u9fff' or '\u3000' <= c <= '\u303f' or '\uff00' <= c <= '\uffef':
            w += 2
        else:
            w += 1
    return w

def pad_vis(s, width):
    return s + ' ' * max(0, width - vis_width(s))

def show_subs(subs):
    print('\n你的订阅列表:' + '─' * 45)

    titles = []
    max_vw = 0
    for s in subs:
        p = s.get('podcast', s)
        title = p.get('title', '?')
        vw = vis_width(title)
        if vw > 54:
            while vis_width(title) > 51 and title:
                title = title[:-1]
            title += '...'
            vw = vis_width(title)
        titles.append(title)
        if vw > max_vw: max_vw = vw

    for i, s in enumerate(subs, 1):
        p = s.get('podcast', s)
        pid = p.get('pid', '?')
        count = s.get('episodeCount', p.get('episodeCount', '?'))
        print(f'  {i:3d}. [{count:3d}集] | {pad_vis(titles[i-1], max_vw)} | {pid}')
    print(f'\n共 {len(subs)} 个订阅\n')

def choose_subs(subs):
    while True:
        try:
            inp = input('输入编号下载，多个用英文逗号隔开（如 1,3,5），q 退出: ').strip()
            if not inp: continue
            if inp.lower() == 'q':
                print('已退出')
                sys.exit(0)
            indices = [int(x.strip()) for x in inp.split(',')]
            chosen = []
            for i in indices:
                if 1 <= i <= len(subs):
                    chosen.append(subs[i-1].get('podcast', subs[i-1]))
                else:
                    print(f'  编号 {i} 超出范围')
            if chosen: return chosen
        except ValueError:
            print('  输入无效，请输入编号')

# ══════════════════════════════════════════════════
#  主函数
# ══════════════════════════════════════════════════

def main():
    print('=' * 55)
    print('  小宇宙播客 RSS 生成器 (交互版)')
    print('=' * 55)
    print()

    # 获取 token
    token, device = get_token()
    print(f'  AT: {token[:30]}...')
    print()

    # 命令行直接传 PID
    if len(sys.argv) > 1 and sys.argv[1] not in ('--setup',):
        pid = sys.argv[1]
        print(f'直接拉取 PID: {pid}')
        print(f'正在获取剧集列表...')
        eps = get_episodes(token, device, pid)
        if eps:
            gen_rss(eps, pid)
        else:
            print('[!] 未获取到剧集')
        return

    # 交互模式
    print('正在拉取订阅列表...')
    subs = get_subscriptions(token, device)
    if not subs:
        print('[!] 未获取到订阅列表')
        print('    可能是 token 无效，尝试 python3 xyz_interactive.py --setup 重新配置')
        return

    show_subs(subs)
    chosen = choose_subs(subs)

    for p in chosen:
        pid = p.get('pid', '')
        title = p.get('title', '?')
        print(f'\n── {title} ──')
        print(f'  正在获取剧集列表 (PID: {pid})...')
        eps = get_episodes(token, device, pid)
        if eps:
            gen_rss(eps, pid)
        else:
            print('  [!] 未获取到剧集')

if __name__ == '__main__':
    main()
