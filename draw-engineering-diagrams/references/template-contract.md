# 模板接口与自定义图

## 通用字段

JSON 使用 `kind`、`title`、可选 `subtitle`。输出宽度为 1600 px，高度按模板内容决定。`role` 只能取 `structure`、`layer`、`resource`、`command`、`transaction`、`neutral`。

## lanes

`lanes` 是 1–5 个对象：`title`、可选 `role`、`nodes`。每道 1–4 个节点，各节点包含 `title`、可选 `body` 和 `role`。内部箭头默认表达从左到右的顺序；泳道本身只表示分区，**不自动表示跨泳道依赖**。跨泳道关系重要时，使用自定义 SVG 画出具体连接，或改用更合适的布局。

## state

`states` 为三个对象：唯一 `id`、`title`、`body`、`role`。`transitions` 为 `from`、`to`、`label`、`role`、`route`。

- `direct`：到右侧相邻状态，标签放在中间通道。
- `upper`：卡片上方升级边，最多两条。
- `lower`：卡片下方返回边，最多两条。

若多条边共用同一起终点，需调整端口避免覆盖，不能只改变颜色。非三态、自环或多条交叉边不要强套此模板。

## timeline

`milestones` 为 2–5 个对象：`date`、`title`、`role`。`date` 可以是真实日期、季度或阶段标签；不能由参考图的日期推断新项目计划。

## 自定义 SVG

从 `scripts/draw_diagram.py` 导入 `Canvas` 可复用 panel/text/card/edge/circle；创建画布后设置 `canvas.title`，使用 `save()`。`edge()` 要求每一段水平或垂直。`card()` 检查估计文字高度；它不是浏览器排版验证器。

```python
import sys
from pathlib import Path
skill = Path('/absolute/path/to/draw-engineering-diagrams')
sys.path.insert(0, str(skill / 'scripts'))
from draw_diagram import Canvas, STYLE, preview

c = Canvas(1600, 720, '共享内存：分配与归还', '分别标注 pool、块和持有者')
c.title = '共享内存：分配与归还'
c.panel(48, 152, 1504, 480, STYLE['panel'], STYLE['border'])
c.card(100, 240, 360, 170, {'title':'Freelist', 'body':'按大小分级的空闲块', 'role':'resource'})
c.card(620, 240, 360, 170, {'title':'在用块', 'body':'writer 与 owner 持有', 'role':'command'})
c.edge([(472,325),(606,325)], 'resource')
c.edge([(800,422),(800,510),(280,510),(280,422)], 'resource')
c.text('最后引用释放 → 归还 → 下一轮复用', 300, 530, 800, 20, STYLE['secondary'])
c.save('memory.svg')
preview('memory.svg', 'memory.png', None)
```

SVG 优先使用 rect/circle/line/polyline/path/text/tspan 和简单分组。保留 `<text>` 以便后续编辑。避免远端资源、脚本、滤镜和复杂 clipPath；不把原始图转换成一张嵌入图片冒充可编辑图。发布到飞书前按相关技能处理 SVG 的语义损失与预览检查。
