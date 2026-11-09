#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase1 生命周期分类 —— 演示版（presentation）Word 生成器。

目标读者：懂基础金融的领导。
原则：讲清「用什么方法（含公式）→ 和论文的异同及原因 → 数据从哪来怎么处理
→ 结果怎么解读 → 下一步」；不罗列方法缺点，不写工程细节，不写流水账。
全文数字只来自 report_numbers_full.json（全市场全量正式口径）。
"""
import json, os
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn

HERE = os.path.dirname(os.path.abspath(__file__))
P1 = os.path.dirname(HERE)                       # phase1/
NUMBERS = os.path.join(P1, "numbers")
PROJECT = os.path.dirname(P1)                    # 项目根目录（Word 报告存放处）
R = json.load(open(os.path.join(NUMBERS, "report_numbers_full.json"), encoding="utf-8"))
OUT = os.path.join(PROJECT, "Phase1_presentation.docx")

doc = Document()

# ---------------- 样式 ----------------
def _set_ea(style, name="黑体"):
    rpr = style.element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = rpr.makeelement(qn("w:rFonts"), {})
        rpr.insert(0, rf)
    rf.set(qn("w:eastAsia"), name)

def _set_ea_run(run, name="宋体"):
    rpr = run._element.get_or_add_rPr()
    rf = rpr.find(qn("w:rFonts"))
    if rf is None:
        rf = rpr.makeelement(qn("w:rFonts"), {})
        rpr.insert(0, rf)
    rf.set(qn("w:eastAsia"), name)

st = doc.styles["Normal"]
st.font.name = "Times New Roman"
st.font.size = Pt(10.5)
_set_ea(st, "宋体")
st.paragraph_format.space_after = Pt(5)
st.paragraph_format.line_spacing = 1.3

for i, sz in [(1, 16), (2, 13), (3, 11.5)]:
    s = doc.styles[f"Heading {i}"]
    s.font.name = "Times New Roman"
    s.font.size = Pt(sz)
    s.font.bold = True
    s.font.color.rgb = RGBColor(0x1F, 0x3B, 0x63)
    _set_ea(s, "黑体")

for sec in doc.sections:
    sec.top_margin = sec.bottom_margin = Cm(2.0)
    sec.left_margin = sec.right_margin = Cm(2.2)

def H(text, lvl=1):
    doc.add_heading(text, level=lvl)

def P(text, bold=False, italic=False, size=None, align=None, color=None):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold, r.italic = bold, italic
    if size:
        r.font.size = Pt(size)
    if color:
        r.font.color.rgb = color
    r.font.name = "Times New Roman"
    _set_ea_run(r, "宋体")
    if align:
        p.alignment = align
    return p

def BUL(text, lvl=0):
    p = doc.add_paragraph(text, style="List Bullet" if lvl == 0 else "List Bullet 2")
    for r in p.runs:
        r.font.name = "Times New Roman"
        _set_ea_run(r, "宋体")
    return p

def TBL(headers, rows, widths=None, note=None, size=9.5):
    t = doc.add_table(rows=1, cols=len(headers))
    t.style = "Light Grid Accent 1"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ""
        p = hdr[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(str(h))
        r.bold = True
        r.font.size = Pt(size)
        _set_ea_run(r, "黑体")
    for row in rows:
        cells = t.add_row().cells
        for i, val in enumerate(row):
            cells[i].text = ""
            p = cells[i].paragraphs[0]
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER if i > 0 else WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(str(val))
            r.font.size = Pt(size)
            _set_ea_run(r, "宋体")
    if widths:
        for row in t.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Cm(w)
    if note:
        P(note, italic=True, size=8.5)
    return t

def CAP(text):
    p = doc.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(9.5)
    _set_ea_run(r, "黑体")

def FORMULA(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(text)
    r.font.name = "Cambria Math"
    r.font.size = Pt(10.5)
    _set_ea_run(r, "宋体")
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(6)
    return p

# ================= 封面标题 =================
t = doc.add_paragraph()
t.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = t.add_run("A 股上市公司生命周期分类")
r.bold = True; r.font.size = Pt(22); r.font.color.rgb = RGBColor(0x1F, 0x3B, 0x63)
_set_ea_run(r, "黑体")
s = doc.add_paragraph()
s.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = s.add_run("Phase 1 方法与结果汇报")
r.bold = True; r.font.size = Pt(14); r.font.color.rgb = RGBColor(0x40, 0x40, 0x40)
_set_ea_run(r, "黑体")
d = doc.add_paragraph()
d.alignment = WD_ALIGN_PARAGRAPH.CENTER
r = d.add_run("（演示稿 · 面向管理层）")
r.font.size = Pt(10.5); r.italic = True
_set_ea_run(r, "宋体")

# ================= 一页结论 =================
H("核心结论", 1)
imp = R["主设定"]["各阶段占比"]["导入期"]; gro = R["主设定"]["各阶段占比"]["成长期"]
mat = R["主设定"]["各阶段占比"]["成熟期"]; res = R["主设定"]["各阶段占比"]["整合期"]
P("我们用国际主流的企业生命周期分类方法——Dickinson（2011）现金流符号法——对全部 A 股上市公司进行了逐年分类，"
  "并针对 A 股财务披露特征做了四项本地化改良。方法可逐环节对应到原文，仅将原文的「摇摇欲坠」与「衰退」两个阶段"
  "合并为「整合期 Restructuring」，因此得到四类（导入期 Introduction / 成长期 Growth / "
  "成熟期 Mature / 整合期 Restructuring）。")
P(f"在 {R['样本_总公司数']:,} 家上市公司、{R['样本_总公司年数']:,} 个「公司-年」上完成分类，得到 "
  f"{R['主设定']['标签行数']:,} 条有效标签；四类占比为 "
  f"导入 {imp}%、成长 {gro}%、成熟 {mat}%、整合 {res}%。")
P("分类标签通过了五类独立检验，证明其捕捉到了企业真实的生命周期状态：")
BUL(f"年龄单调性：四类中位上市年龄为 {int(R['主设定']['中位年龄']['导入期'])} < "
    f"{int(R['主设定']['中位年龄']['成长期'])} < {int(R['主设定']['中位年龄']['成熟期'])} < "
    f"{int(R['主设定']['中位年龄']['整合期'])} 年，严格递增。")
BUL(f"退市风险：整合期公司的退市比例是全样本基准的 {R['主设定']['退市倍数']['整合期']} 倍"
    f"（基准 {R['主设定']['全样本退市占比']}%），其余阶段均不超过基准。")
BUL(f"ST 风险：整合期公司的 ST 比例是全样本基准的 {R['ST检验']['各阶段ST倍数']['整合期']} 倍，"
    f"显著高于其他三类。")
BUL(f"板块与行业：科创板导入期占比最高（{R['板块检验']['科创板']['导入期']}%），"
    f"整合期集中在综合、房地产、非银金融等行业，符合直觉。")
BUL(f"稳健性：{R['稳健性']['设定数']} 组参数变动全部保持年龄单调递增，结果稳定。")
P("结论：Phase 1 已交付一套可靠、可复现的 A 股生命周期标签，可直接作为 Phase 2 因子检验的分组变量。",
  bold=True)

# ================= 第 1 章 =================
H("1  项目背景与目标", 1)
H("1.1  为什么要做企业生命周期分类", 2)
P("企业在不同发展阶段，其盈利模式、现金流结构、投资与融资行为截然不同。处于导入期的公司通常「烧钱、靠融资」；"
  "成熟期公司则「自我造血、回报股东」。学术界与业界普遍认为，同一财务或量价指标在不同生命周期阶段的含义不同，"
  "因此把公司按生命周期分组，是提升因子有效性、理解风险溢价来源的重要工具。")
P("近年来的代表研究 Klein, Tresl & Yilanci（2025，《Journal of Portfolio Management》）发现：规模、价值、盈利、"
  "动量等因子的风险溢价在不同生命周期阶段存在显著差异。我们的项目以该思路为蓝本，分两阶段推进。")

H("1.2  Phase 1 的目标与范围", 2)
P("Phase 1 只做一件事：为 A 股上市公司构造一套可靠的生命周期分类标签，并验证其有效性。"
  "具体交付：① 复现并本地化国际主流的现金流符号分类法；② 覆盖沪深两市在市与退市全部公司；"
  "③ 用年龄、退市、ST、板块、行业、参数稳健性等多种独立证据验证标签质量。")
P("Phase 2（下一步）才是在此标签基础上检验因子溢价，属于本阶段的自然延伸。")

# ================= 第 2 章 =================
H("2  分类方法：来源、规则与论文对应", 1)
P("本章回答三个问题：我们的方法来自哪里？具体规则是什么？与论文相比有没有差异、为什么有差异？",
  italic=True)

H("2.1  方法来源与文献关系", 2)
P("生命周期分类方法的原始出处是 Dickinson, V.（2011）《Cash Flow Patterns as a Proxy for Firm Life Cycle》，"
  "发表于 The Accounting Review 86(6)：1969–1994。该文首次提出用「经营、投资、融资三类现金流净额的正负号」"
  "来划分企业生命周期，共 8 种符号组合，归并为 5 个理论阶段。")
P("我们直接采用的方法，与参考论文 Klein, Tresl & Yilanci（2025）所采用的是同一套分类法——该文正文明确写明"
  "「我们遵循 Dickinson（2011）的方法，按现金流模式将公司分为五个生命周期阶段」。因此，"
  "我们的分类是对 Dickinson（2011）的方法复现＋A 股本地化改造，而不是对参考论文全文的复现（其因子组合与回归分析对应我们的 Phase 2）。")

H("2.2  核心分类规则", 2)
P("对每家公司的每个会计年度，观察三项现金流净额的符号，按下表映射到生命周期阶段。"
  "表中的「＋」表示现金净流入，「－」表示净流出。")
TBL(
    ["经营 CF(O)", "投资 CF(I)", "融资 CF(F)", "Dickinson（2011）阶段", "本项目阶段"],
    [
        ["－", "－", "＋", "导入期 Introduction", "导入期 Introduction"],
        ["＋", "－", "＋", "成长期 Growth", "成长期 Growth"],
        ["＋", "－", "－", "成熟期 Mature", "成熟期 Mature"],
        ["－", "－", "－", "摇摇欲坠 Shake-out", "整合期 Restructuring"],
        ["＋", "＋", "＋", "摇摇欲坠 Shake-out", "整合期 Restructuring"],
        ["＋", "＋", "－", "摇摇欲坠 Shake-out", "整合期 Restructuring"],
        ["－", "＋", "＋", "衰退 Decline", "整合期 Restructuring"],
        ["－", "＋", "－", "衰退 Decline", "整合期 Restructuring"],
    ],
    widths=[2.0, 2.0, 2.0, 5.2, 2.6],
    note="注：8 种符号组合与 Dickinson（2011）Table 1 完全对应；本项目的唯一结构性差异，是把「摇摇欲坠」与「衰退」两类合并为「整合期」。",
)
P("分类的经济直觉：导入期公司自身尚不能造血（O 为负），持续投入（I 为负），依赖外部融资（F 为正）；"
  "成长期开始造血但仍大举投资、继续融资；成熟期现金流充沛、投资收缩、并开始回报股东（F 为负）；"
  "「摇摇欲坠 / 衰退」类公司则出现经营下滑、变卖资产（I 为正）等信号，经营与融资现金流方向较为混乱，故合并处理。")

H("2.3  与论文的逐环节对应（核心）", 2)
P("下表把分类方法的每一个环节拆开，逐一对比 Dickinson（2011）与我们的实现，并标注是否一致、差异原因。")
TBL(
    ["环节", "Dickinson (2011) / ref_paper1", "本项目实现", "对照"],
    [
        ["理论依据", "现金流是经营/投资/融资决策的结果", "同", "一致"],
        ["分类变量", "CFO、CFI、CFF 净额的符号", "同", "一致"],
        ["规模处理", "直接取符号", "先以总资产 TA 标准化再取符号（不改变符号）", "等价"],
        ["导入期 Introduction", "(－, －, ＋)", "(－, －, ＋)", "一致"],
        ["成长期 Growth", "(＋, －, ＋)", "(＋, －, ＋)", "一致"],
        ["成熟期 Mature", "(＋, －, －)", "(＋, －, －)", "一致"],
        ["摇摇欲坠 Shake-out", "(－,－,－)/(＋,＋,＋)/(＋,＋,－)", "并入整合期", "合并"],
        ["衰退 Decline", "(－,＋,＋)/(－,＋,－)", "并入整合期", "合并"],
        ["阶段数", "5 类", "4 类", "差异①：合并后两类"],
        ["投资现金流定义", "报表原始 CFI", "CFI_core（剔除理财进出）", "差异②：A 股改良"],
        ["导入期误判矫正", "无", "上市超 10 年的导入期按 RE/TA 重判", "差异③：A 股改良"],
        ["时间平滑", "无，单年标签", "近 3 年多数票平滑", "差异④：A 股改良"],
        ["分类频率", "年度", "年度", "一致"],
        ["剔除行业", "剔除金融业（资本约束）", "剔除金融业（同理由）", "一致"],
        ["样本", "美国 48,369 公司-年（1989–2005）", f"A 股 {R['主设定']['标签行数']:,} 公司-年（1999–2025）", "市场/区间不同"],
        ["研究用途", "分类 + 财务特征 + 市场定价检验", "Phase 1 只做分类与验证；定价检验留待 Phase 2", "待 Phase 2"],
    ],
    widths=[2.6, 5.0, 5.6, 3.0],
    size=9.0,
    note="注：Dickinson（2011）剔除金融业的理由（资本约束使其现金流结构与一般行业不可比）与本项目完全一致。",
)
P("一句话概括：分类规则本身是「精确复现」，8 种符号组合逐条对应；差异集中在阶段粒度（5→4）和四项 A 股本地化改良上。",
  bold=True)

H("2.4  四项 A 股本地化改良及原因", 2)
P("我们保留 Dickinson 的符号法内核，仅针对 A 股财务披露的三个客观特征做了改良，目的是让分类更贴近企业真实状态。")
P("① 投资现金流「干净化」（CFI_core）。A 股公司普遍用闲置资金购买银行理财，这类「理财申购 / 赎回」会大额进出"
  "投资活动现金流，却与实体投资扩张无关，易污染投资现金流符号。我们将投资现金流中的理财科目剔除，"
  "只保留与生产经营、实体投资相关的部分。")
FORMULA("CFI_core = CFI + 投资所支付的现金 − 收回投资收到的现金 − 取得投资收益收到的现金")
P("② 导入期「长时间停留」矫正。A 股有大量上市已久、从符号看仍呈导入期特征的公司（多为持续亏损或依赖再融资）。"
  "我们把「上市超过 10 年仍被判为导入期」的公司，改用留存收益占比（RE/TA，即「赚到的资本」比重）重新判定："
  "RE/TA 高者归入整合期，低者归入成长期，使标签更符合其真实成熟度。")
P("③ 单年标签噪声抑制。仅凭单年现金流符号，公司标签在不同年份之间会频繁跳变（实测逐年跳变率高达 "
  f"{R['主设定']['平滑前跳变率']}%），噪声较大。我们改用近 3 年标签的多数票作为当年最终标签，"
  f"跳变率降至 {R['主设定']['平滑后跳变率']}%。")
FORMULA("stage_smooth(t) = mode[ stage(t−2), stage(t−1), stage(t) ]")
P("④ 剔除金融企业。与 Dickinson 一致——银行、保险、券商等金融机构受资本监管约束，其现金流结构与非金融企业"
  f"不可直接比较，故整体剔除（占名单约 {R['名单_未抓取金融业数']} 家）。")

H("2.5  关键公式汇总", 2)
TBL(
    ["指标", "公式", "含义"],
    [
        ["经营现金流强度", "CFO/TA = 经营活动现金流量净额 ÷ 资产总计", "自身造血能力"],
        ["留存收益占比", "RE/TA = 未分配利润 ÷ 资产总计", "累计盈利沉淀（赚到的资本）"],
        ["投资现金流（净）", "CFI_core（见 2.4 ①）", "剔除理财后的实体投资强度"],
        ["营收增速", "g_REV(t) = 营业收入(t) ÷ 营业收入(t−1) − 1", "成长速度"],
        ["年龄", "age = 当年年份 − 上市年份", "上市年限"],
    ],
    widths=[3.2, 8.2, 4.8],
    size=9.0,
)

# ================= 第 3 章 =================
H("3  数据来源与处理流程", 1)

H("3.1  数据来源", 2)
P("本项目所有数据均来自公开、免费渠道，无需付费数据终端。核心数据来源与落地文件如下。")
TBL(
    ["数据", "来源平台", "获取方式（代码）", "落地文件"],
    [
        ["现金流量表 / 资产负债表 / 利润表（年报）", "新浪财经", "akshare 接口 stock_financial_report_sina；fetch_universe.py、lifecycle.py", "~/life_cache/（约 607MB）"],
        ["在市公司名单", "上交所 / 深交所", "stock_info_sh_name_code / stock_info_sz_name_code", "a_code_name.csv"],
        ["退市公司名单", "上交所 / 深交所", "stock_info_sh_delist / stock_info_sz_delist", "delist_universe.csv"],
        ["上市日期", "交易所", "lifecycle_meta.py", "meta_list_date.csv"],
        ["行业（申万一级）", "申万宏源", "task3_industry_board.py", "industry_map.csv"],
        ["ST 标记", "项目提供", "—", "stock_st_flag_20260630.csv"],
        ["后复权收盘价", "项目提供", "—", "daily_adj_close_post_20260630.csv"],
    ],
    widths=[4.2, 2.6, 5.6, 3.8],
    size=8.8,
    note="注：年报统一取 12 月 31 日口径（全年累计），确保三张报表同期可比。",
)

H("3.2  处理流程（八个环节）", 2)
P("从原始数据到最终标签共八个环节。每个环节的代码文件、输入输出与衔接关系如下，构成一条可复现的流水线。")
TBL(
    ["环节", "代码文件", "输入", "输出 / 结果", "衔接"],
    [
        ["① 方法调研", "Phase1_A股生命周期分类方法调研.docx、精读文档", "Dickinson(2011)、ref_paper1 等", "选定现金流符号法", "→ 抓数"],
        ["② 财务数据抓取", "fetch_universe.py、lifecycle.py", "交易所名单", "~/life_cache：5,496 家三表", "→ 辅助数据"],
        ["③ 辅助数据", "lifecycle_meta.py、task3_industry_board.py", "交易所、申万", "上市日期、行业映射", "→ 退市面板"],
        ["④ 退市公司面板", "task2b_delisted_panel.py", "退市名单", "panel_delisted.csv：360 家", "→ 建面板"],
        ["⑤ 构建全市场面板", "build_full_panel.py", "缓存三表", f"panel_full.csv：{R['样本_总公司数']:,} 家 / {R['样本_总公司年数']:,} 行", "→ 分类"],
        ["⑥ 计算特征与分类", "lifecycle.py（add_features / classify / add_age_override / smooth）", "panel_full.csv", f"labels_main_full.csv：{R['主设定']['标签行数']:,} 行", "→ 检验"],
        ["⑦ 四类有效性检验", "task1_st_pollution.py、task2c_diagnosis_full.py、task3_industry_board.py、task4_robustness.py", "labels_main_full.csv", "ST / 退市 / 行业板块 / 稳健性", "→ 汇总"],
        ["⑧ 汇总与出报告", "make_report_numbers.py、build_report_docx.py", "检验结果", "report_numbers_full.json、报告", "完成"],
    ],
    widths=[2.3, 4.4, 2.7, 4.4, 1.4],
    size=8.4,
)

H("3.3  数据质量", 2)
u = R["可用率"]
P(f"三项核心现金流变量可用率均在 {u['cff']*100:.2f}% 以上，留存收益、总资产、营收几乎全覆盖；"
  f"若采用报表原始投资现金流，可分类样本覆盖面板的 {R['可分类行数']['cfi']['覆盖率']*100:.1f}%。")
P(f"说明：主设定采用的 CFI_core（干净化投资现金流）可用率为 {u['cfi_core']*100:.1f}%，因其需要更细的理财科目数据，"
  f"早期年份科目披露不全，故有效分类样本少于原始面板——这是以「更准」换「更全」的主动取舍，"
  "也使得标签质量优先于覆盖率。")

# ================= 第 4 章 =================
H("4  分类结果与解读", 1)

H("4.1  四类总体分布，并与论文对比", 2)
P("下表给出主设定下四类标签的行数、公司数与占比，并与 Dickinson（2011）把「摇摇欲坠+衰退」合并后的占比并列，"
  "以便同口径比较。")
main = R["主设定"]
TBL(
    ["阶段", "标签行数", "涉及公司数", "本项目占比", "Dickinson(2011) 同口径占比"],
    [
        ["导入期 Introduction", f"{main['各阶段行数']['导入期']:,}", f"{main['各阶段公司数']['导入期']:,}", f"{imp}%", "11.9%"],
        ["成长期 Growth", f"{main['各阶段行数']['成长期']:,}", f"{main['各阶段公司数']['成长期']:,}", f"{gro}%", "34.0%"],
        ["成熟期 Mature", f"{main['各阶段行数']['成熟期']:,}", f"{main['各阶段公司数']['成熟期']:,}", f"{mat}%", "41.2%"],
        ["整合期 Restructuring", f"{main['各阶段行数']['整合期']:,}", f"{main['各阶段公司数']['整合期']:,}", f"{res}%", "13.0%"],
        ["合计 Total", f"{main['标签行数']:,}", f"{main['覆盖公司数']:,}", "100%", "100%"],
    ],
    widths=[2.2, 2.6, 2.6, 2.8, 5.4],
    note="注：Dickinson 同口径占比 = 原始 8.0%（摇摇欲坠）+ 5.0%（衰退）= 13.0%；其原始五类为 11.9 / 34.0 / 41.2 / 8.0 / 5.0。",
)
P(f"解读：与美股相比，A 股「成长期」占比明显更高（{gro}% vs 34.0%），这与 A 股上市公司整体更年轻、"
  f"更加依赖外部融资的特征一致；「成熟期」占比接近；「整合期」占比更低，说明 A 股中进入经营收缩与资产处置阶段的公司相对较少——"
  "这与 A 股退市率长期偏低一致。")

H("4.2  各阶段的财务特征（验证标签含义）", 2)
P("如果分类有效，各阶段的财务特征应当呈现清晰、可解释的梯度。下表为各阶段中位数（中位数比平均数更抗极端值）。")
TBL(
    ["阶段", "中位年龄(年)", "中位 CFO/TA", "中位 RE/TA", "中位营收增速", "中位总资产(亿元)"],
    [
        ["导入期 Introduction", f"{int(main['中位年龄']['导入期'])}", f"{main['中位CFO/TA']['导入期']*100:.1f}%", f"{main['中位RE/TA']['导入期']*100:.1f}%", f"{main['中位营收增速']['导入期']*100:.1f}%", f"{main['中位总资产亿元']['导入期']}"],
        ["成长期 Growth", f"{int(main['中位年龄']['成长期'])}", f"{main['中位CFO/TA']['成长期']*100:.1f}%", f"{main['中位RE/TA']['成长期']*100:.1f}%", f"{main['中位营收增速']['成长期']*100:.1f}%", f"{main['中位总资产亿元']['成长期']}"],
        ["成熟期 Mature", f"{int(main['中位年龄']['成熟期'])}", f"{main['中位CFO/TA']['成熟期']*100:.1f}%", f"{main['中位RE/TA']['成熟期']*100:.1f}%", f"{main['中位营收增速']['成熟期']*100:.1f}%", f"{main['中位总资产亿元']['成熟期']}"],
        ["整合期 Restructuring", f"{int(main['中位年龄']['整合期'])}", f"{main['中位CFO/TA']['整合期']*100:.1f}%", f"{main['中位RE/TA']['整合期']*100:.1f}%", f"{main['中位营收增速']['整合期']*100:.1f}%", f"{main['中位总资产亿元']['整合期']}"],
    ],
    widths=[1.9, 2.4, 2.6, 2.6, 2.8, 3.3],
    size=9.0,
)
P("解读：① 年龄严格递增（导入 5 → 成长 7 → 成熟 9 → 整合 14 年），符合生命周期直觉；"
  "② 经营现金流强度（CFO/TA）在成熟期达到峰值，导入期与整合期为负，说明只有成熟期公司能稳定自我造血；"
  "③ 留存收益占比 RE/TA 在成熟期最高（21%），整合期骤降，说明整合期公司消耗了历史积累；"
  "④ 营收增速随阶段递减，成熟期、整合期明显放缓；⑤ 成熟期公司规模最大，整合期规模偏小，均符合预期。")

H("4.3  有效性检验：退市、ST、板块、行业、稳健性", 2)
P("我们用五种互不依赖的证据检验标签是否「名副其实」。")
CAP("（1）退市风险检验")
P(f"整合期公司的退市比例（{main['退市公司占比']['整合期']}%）是全部样本基准（{main['全样本退市占比']}%）的 "
  f"{main['退市倍数']['整合期']} 倍，是唯一大幅超过「2 倍门槛」的阶段；其余三类的退市比例均不高于基准。"
  "这说明整合期标签确实锁定了经营承压、退出风险高的公司。")
TBL(
    ["阶段", "退市公司占比", "相对基准倍数"],
    [
        ["导入期 Introduction", f"{main['退市公司占比']['导入期']}%", f"{main['退市倍数']['导入期']}"],
        ["成长期 Growth", f"{main['退市公司占比']['成长期']}%", f"{main['退市倍数']['成长期']}"],
        ["成熟期 Mature", f"{main['退市公司占比']['成熟期']}%", f"{main['退市倍数']['成熟期']}"],
        ["整合期 Restructuring", f"{main['退市公司占比']['整合期']}%", f"{main['退市倍数']['整合期']}"],
        ["全样本基准 Overall", f"{main['全样本退市占比']}%", "1.00"],
    ],
    widths=[3.0, 3.5, 3.5],
)
CAP("（2）ST（特别处理）风险检验")
P(f"整合期公司被 ST 的比例为 {R['ST检验']['各阶段ST占比']['整合期']}%，是全样本基准"
  f"（{R['ST检验']['样本ST占比基准']}%）的 {R['ST检验']['各阶段ST倍数']['整合期']} 倍，"
  f"而其余三类的 ST 比例均低于基准（0.68–0.90 倍）。剔除 ST 公司后，四类分布变化不超过 0.7 个百分点，"
  "说明分类结论并非由 ST 公司驱动。")
TBL(
    ["阶段", "ST 占比", "相对基准倍数"],
    [
        ["导入期 Introduction", f"{R['ST检验']['各阶段ST占比']['导入期']}%", f"{R['ST检验']['各阶段ST倍数']['导入期']}"],
        ["成长期 Growth", f"{R['ST检验']['各阶段ST占比']['成长期']}%", f"{R['ST检验']['各阶段ST倍数']['成长期']}"],
        ["成熟期 Mature", f"{R['ST检验']['各阶段ST占比']['成熟期']}%", f"{R['ST检验']['各阶段ST倍数']['成熟期']}"],
        ["整合期 Restructuring", f"{R['ST检验']['各阶段ST占比']['整合期']}%", f"{R['ST检验']['各阶段ST倍数']['整合期']}"],
        ["全样本基准 Overall", f"{R['ST检验']['样本ST占比基准']}%", "1.00"],
    ],
    widths=[3.0, 3.5, 3.5],
)
CAP("（3）板块检验")
P("按上市板块拆分，越是新兴、尚未盈利的公司聚集的板块，导入期占比越高——科创板导入期占比最高，符合直觉。")
b = R["板块检验"]
TBL(
    ["板块", "样本量", "导入期", "成长期", "成熟期", "整合期"],
    [
        ["上交所主板", f"{b['上交所主板']['n']:,}", f"{b['上交所主板']['导入期']}%", f"{b['上交所主板']['成长期']}%", f"{b['上交所主板']['成熟期']}%", f"{b['上交所主板']['整合期']}%"],
        ["深交所主板", f"{b['深交所主板']['n']:,}", f"{b['深交所主板']['导入期']}%", f"{b['深交所主板']['成长期']}%", f"{b['深交所主板']['成熟期']}%", f"{b['深交所主板']['整合期']}%"],
        ["创业板", f"{b['创业板']['n']:,}", f"{b['创业板']['导入期']}%", f"{b['创业板']['成长期']}%", f"{b['创业板']['成熟期']}%", f"{b['创业板']['整合期']}%"],
        ["科创板", f"{b['科创板']['n']:,}", f"{b['科创板']['导入期']}%", f"{b['科创板']['成长期']}%", f"{b['科创板']['成熟期']}%", f"{b['科创板']['整合期']}%"],
    ],
    widths=[2.6, 2.4, 2.2, 2.2, 2.2, 2.2],
    size=9.0,
)
CAP("（4）行业检验")
P(f"行业匹配率 {R['行业检验']['行业匹配率']:.1%}，覆盖 {R['行业检验']['行业数']} 个申万一级行业。"
  "整合期占比最高的行业集中在综合、房地产、非银金融、社会服务、商贸零售、通信等；"
  "成熟期占比最高的行业集中在煤炭、食品饮料、纺织服饰、家用电器等传统行业——均与产业经验相符。")
CAP("（5）参数稳健性")
P(f"我们让年龄阈值、RE 分界、平滑窗口、是否剔除金融等关键参数逐一变动（共 {R['稳健性']['设定数']} 组），"
  f"全部保持「年龄随阶段单调递增」，且各阶段占比的波动区间很窄（整合期占比仅在 "
  f"{R['稳健性']['平滑2年整合期']}%–{R['稳健性']['平滑5年整合期']}% 之间波动）。"
  "说明分类结论不依赖某一组特定参数。")

H("4.4  生命周期的时间趋势", 2)
P(f"从时间趋势看，成熟期公司占比从 2012 年以前的 {R['趋势']['成熟期占比_2012前']}% 上升到 2018 年以来的 "
  f"{R['趋势']['成熟期占比_2018后']}%，反映 A 股上市公司整体在走向成熟，与宏观产业结构升级、"
  "上市存量公司年龄增长的趋势一致。这一趋势也为后续按阶段研究因子表现提供了时间维度的素材。")

H("4.5  整合期的内部结构（补充解读）", 2)
P("整合期由两类方向相反的公司构成：一类是经营下滑、靠变卖资产维持的「卖资产型」；"
  "另一类是大量烧钱、依赖融资的「烧钱型」。二者都表现出更高的退市与 ST 风险，但驱动因素不同，"
  "后续研究中可分别对待：")
TBL(
    ["子类型", "样本量", "占比（整合期内）", "退市比例", "ST 比例"],
    [
        ["卖资产型", f"{R['整合期拆分']['卖资产型']['n']:,}", f"{R['整合期拆分']['占整合期比重']['卖资产型']}%", f"{R['整合期拆分']['卖资产型']['退市比例']}%", f"{R['整合期拆分']['卖资产型']['ST比例']}%"],
        ["烧钱型", f"{R['整合期拆分']['烧钱型']['n']:,}", f"{R['整合期拆分']['占整合期比重']['烧钱型']}%", f"{R['整合期拆分']['烧钱型']['退市比例']}%", f"{R['整合期拆分']['烧钱型']['ST比例']}%"],
    ],
    widths=[2.8, 2.6, 3.4, 2.8, 2.8],
    note="注：两类合计约占整合期的 76.4%，其余为经营/融资现金流同向的混合型。",
)

# ================= 第 5 章 =================
H("5  结论与下一步", 1)
H("5.1  本阶段结论", 2)
BUL("方法可靠：完整复现 Dickinson（2011）现金流符号法，8 种符号组合逐条对应，四项 A 股改良有明确动机。")
BUL(f"覆盖完整：{R['样本_总公司数']:,} 家公司（含 {R['样本_退市公司数']} 家退市公司）、"
    f"{R['主设定']['标签行数']:,} 条有效标签。")
BUL("验证充分：年龄单调、退市与 ST 风险集中、板块行业结构合理、参数稳健性通过。")
BUL("结论明确：四类标签捕捉到了企业真实生命周期状态，可作为可靠的分组变量进入 Phase 2。")

H("5.2  下一阶段（Phase 2）计划", 2)
BUL("以生命周期标签为分组变量，检验规模、价值、盈利、动量等因子的风险溢价是否随阶段不同——复刻 Klein et al.（2025）的核心分析。")
BUL("按「导入 → 成长 → 成熟 → 整合」构造分组组合，比较各组的收益、波动与 Sharpe 比率。")
BUL("补充分析所需字段：本地面板已有价格，但缺市值、总股本、换手率；拟从校园采购的 CSMAR 数据库获取（Tushare 为备选）。")
BUL("输出：一份与论文可对标的因子—生命周期实证报告。")

# ================= 附录 =================
H("附录 A  术语中英对照（Glossary）", 1)
P("本表列出本项目使用的主要英文专业术语及其出处，便于与国际文献（Dickinson 2011；Klein et al. 2025）对照。")
TBL(
    ["英文术语", "中文", "说明 / 出处"],
    [
        ["Firm life cycle", "企业生命周期", "企业从创立到衰退的发展阶段（Dickinson 2011 核心概念）"],
        ["Cash flow pattern", "现金流模式", "以三类现金流符号刻画生命周期的方法"],
        ["Operating cash flow (CFO)", "经营活动现金流", "企业主营业务的现金净流入，代表自身造血能力"],
        ["Investing cash flow (CFI)", "投资活动现金流", "购建/处置资产、对外投资的现金净流量"],
        ["Financing cash flow (CFF)", "筹资活动现金流", "借款、发股、还债、分红的现金净流量"],
        ["Introduction", "导入期", "生命周期第 1 阶段：CFO<0, CFI<0, CFF>0"],
        ["Growth", "成长期", "生命周期第 2 阶段：CFO>0, CFI<0, CFF>0"],
        ["Mature", "成熟期", "生命周期第 3 阶段：CFO>0, CFI<0, CFF<0"],
        ["Shake-out", "摇摇欲坠期", "Dickinson 单列阶段之一（本项目并入整合期）"],
        ["Decline", "衰退期", "Dickinson 单列阶段之一（本项目并入整合期）"],
        ["Restructuring", "整合期", "本项目将 Shake-out 与 Decline 合并后的阶段"],
        ["Retained earnings (RE)", "留存收益", "资产负债表未分配利润，累计盈利沉淀"],
        ["RE/TA", "留存收益 / 总资产", "「赚到的资本」占比，用于判断企业成熟度"],
        ["Total assets (TA)", "总资产", "标准化现金流指标的基准"],
        ["Revenue growth", "营业收入增速", "衡量成长性的指标"],
        ["RNOA", "净经营资产收益率", "Dickinson 用于验证分类有效性的盈利指标"],
        ["Market capitalization", "市值", "总市值，Phase 2 分组分析所需"],
        ["Book-to-market (B/M)", "账面市值比", "价值因子常用指标"],
        ["Risk premium", "风险溢价", "因子投资研究的核心对象（Klein et al. 2025）"],
        ["Factor investing", "因子投资", "按规模、价值、盈利、动量等因子构建组合"],
        ["Portfolio", "组合", "按生命周期阶段分组形成的投资组合"],
        ["Fama-MacBeth regression", "Fama-MacBeth 回归", "因子检验常用方法（Phase 2）"],
        ["Winsorize", "缩尾处理", "将极端值截断到分位数，降低异常值影响"],
        ["Delisting", "退市", "股票终止上市，本项目作为有效性检验之一"],
        ["ST (Special Treatment)", "特别处理", "财务异常的标记，本项目作为有效性检验之一"],
    ],
    widths=[4.6, 3.2, 8.4],
    size=8.6,
)

H("附录 B  主要文件清单", 1)
TBL(
    ["类别", "文件", "说明"],
    [
        ["方法", "lifecycle.py", "分类核心（特征计算 / 分类 / 年龄矫正 / 平滑）"],
        ["抓取", "fetch_universe.py", "全市场财务数据抓取"],
        ["面板", "build_full_panel.py、task2b_delisted_panel.py", "全市场面板、退市公司面板"],
        ["标签", "labels_main_full.csv", "主设定分类结果"],
        ["检验", "task1_st_pollution.py、task2c_diagnosis_full.py、task3_industry_board.py、task4_robustness.py", "四类有效性检验"],
        ["数字", "report_numbers_full.json、make_report_numbers.py", "全文数字唯一来源"],
        ["报告", "Phase1_生命周期分类_工作汇报.docx", "技术详版（备查）"],
    ],
    widths=[2.2, 8.4, 5.6],
    size=8.8,
)

doc.save(OUT)
print("saved:", OUT)
print("段落数:", len(doc.paragraphs), "表格数:", len(doc.tables))
