# Authoring reference

Use source IDs printed by `pdfx text`. One source ID may appear exactly once in
`content.md` and maps to one contiguous location in the PDF.

```markdown
# タイトル
> {{s1.2|書誌情報を含むリード文}}。

## 1. 見出し

{{s2.8|短い主張A}}、{{s2.9|短い主張B}}。

:::note 補足
{{s3.4|原文に基づく補足}}。
:::

:::deriv 導出メモ
{{s4.7|仮定を説明する}}。
= {{s4.8|E_0 = \frac{1}{2}kQ_R^2}}
:::

:::media figure
@crop p5 10 22 80 48
{{s5.31|図1　日本語キャプション}}
:::

:::media table
@crop p8 18 20 64 62
{{s8.24|表1　日本語キャプション}}
:::

:::media compare
@crop p9 8 20 84 34
{{s9.18|比較対象A}}
@crop p10 8 18 84 38
{{s10.21|比較対象B}}
:::
```

`= `で始まる行は中央配置の数式になる。Visible text supports TeX-like
fractions, roots, subscripts, superscripts, Greek letters, relations, and
operators. Inline math may use `\(...\)` or `$...$`.

Crop coordinates are `page x y width height` in page-relative percentages.
Use `figure` for one figure, `table` for one table, and `compare` for exactly
two directly comparable items. Each crop includes only the complete media and
its original caption. Caption source IDs must belong to the cropped page.

Write one short atomic claim per source ID. If one Japanese sentence uses two
separated source locations, divide the sentence into two linked spans. Do not
create a group link, reuse an ID, or place several IDs in one span.
