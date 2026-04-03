# news-bot

每天早上自动抓取 RSS 新闻并推送到飞书群。

## 使用方法

1. 新建飞书自定义机器人，拿到 webhook
2. 在 GitHub 仓库里设置 Secret：
   - `FEISHU_WEBHOOK`
3. 修改 `feeds.txt`，一行一个 RSS 源
4. 手动运行一次 Actions 测试

## 定时说明

`.github/workflows/daily-news.yml` 里：

```yaml
- cron: '3 23 * * *'