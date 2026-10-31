# 融资与融券

[打开网页](https://tztzpub.github.io/margin-balance-monitor/)

两张同步时间轴曲线：融资余额、融券余额的20个交易日变化率。
支持起止日期、YTD、常用时间范围、同步游标和独立纵轴缩放。

数据来自东方财富 Choice 的全市场账户统计接口 `RPTA_WEB_MARGIN_DAILYTRADE`。
变化率为当日余额除以20个交易日前余额减一，先使用完整历史计算，再筛选展示区间。

GitHub Actions 每天北京时间08:35、18:35、22:35检查数据并发布到GitHub Pages；
实际启动时间由GitHub调度。也可以在Actions中手动运行 `Refresh and publish`。
接口失败、历史缺失或校验不通过时，任务失败，线上保留上次成功发布的页面。
数据日期与最近核查时间在页面上分别显示。

本地生成：

```sh
pip install -r requirements.txt
python refresh.py
python build.py
```

`build.py` 是唯一页面生成器，`index.html` 为自包含输出，可单独下载打开。
