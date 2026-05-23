# 小宇宙播客 RSS 生成器

通过小宇宙 API 获取播客全量剧集列表，生成标准 RSS XML。

> 本项目出于学习目的，代码全部由 DeepSeek V4 Flash 编写。

## 前置条件

- Python 3.7+
- 一个小宇宙账号
- 能抓 HTTP 请求的工具（Surge、Charles、Proxyman、Wireshark 等）

## 安装

保存 `xyz_interactive.py` 到本地即可。

```bash
# 交互模式
python3 ~/Desktop/xyz_interactive.py

# 直接指定播客 PID 下载
python3 ~/Desktop/xyz_interactive.py 61791d921989541784257779

# 重新配置 token
python3 ~/Desktop/xyz_interactive.py --setup
```

## 首次使用：获取 Token

需要两个凭证：

- **x-jike-refresh-token** — 长期有效的刷新令牌，在 Cookie 中
- **x-jike-device-id** — 设备标识，在请求头中

用抓包工具拦截一个 `api.xiaoyuzhoufm.com` 的请求，从 Request Headers 中提取这两个值即可。

首次运行脚本会自动进入配置流程：

```
$ python3 ~/Desktop/xyz_interactive.py

如何获取 refresh token 和 device id
─────────────────────────────────────

请粘贴你从抓包中获取到的值:

x-jike-refresh-token: [粘贴]
x-jike-device-id:     [粘贴]

正在验证...
[✓] 验证通过
```

验证成功后配置自动保存，之后运行不再需要抓包。

## 使用方法

### 交互模式

```
$ python3 ~/Desktop/xyz_interactive.py

=======================================================
  小宇宙播客 RSS 生成器 (交互版)
=======================================================

正在拉取订阅列表...

你的订阅列表:─────────────────────────────────────────────
   1. [248集] | 不开玩笑 Jokes Aside                     | 61791d921989541784257779
   2. [  6集] | 狗叫狗叫                                 | 66c9ac588cc27a7fc1a1f73b
   3. [232集] | 散场通道|关于电影的一切                    | 5ec4dc4a418a84a04683e755
   ...

共 42 个订阅

输入编号下载，多个用英文逗号隔开（如 1,3,5），q 退出: 1

── 不开玩笑 Jokes Aside ──
  正在获取剧集列表 (PID: 61791d921989541784257779)...
  [✓] 不开玩笑 Jokes Aside: 248 集
  [✓] 保存: ~/Downloads/xyz_不开玩笑 Jokes Aside_42577779.xml  (585 KB)
```

### 直接模式

```bash
python3 ~/Desktop/xyz_interactive.py 61791d921989541784257779
```

PID 可以从播客网页版 URL 获取：`https://www.xiaoyuzhoufm.com/podcast/{PID}`。

## 输出

- 保存位置：`~/Downloads/xyz_播客名_pid后八位.xml`

## 已知问题

- Access token 有效期极短，大规模分页中可能过期，脚本会自动续期重试
- Device ID 和 refresh token 绑定，不可更换设备 ID
- 所有请求都模拟自小宇宙 iOS app 的行为，理论上不会触发风控

## License

MIT
