# news-bot

每天早上自动抓取 RSS 新闻并推送到飞书群。

## 使用方法

1. 新建飞书自定义机器人，拿到 webhook
2. 在 GitHub 仓库里设置 Secret：
   - `FEISHU_WEBHOOK`
3. 修改 `feeds.txt`，一行一个 RSS 源
4. 可选设置：
   - `FEISHU_KEYWORD`：飞书消息标题里显示的主题名称
   - `FEISHU_MATCH_KEYWORDS`：真正用于筛选新闻的关键词列表，多个关键词用英文逗号分隔
5. 手动运行一次 Actions 测试

## 定时说明

`.github/workflows/daily-news.yml` 里：

```yaml
- cron: '3 23 * * *'
```
