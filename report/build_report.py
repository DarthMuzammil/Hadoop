#!/usr/bin/env python3
"""Builds the project report (report/WikiTrend_Report.html -> .pdf) from the real run outputs.

Inputs : results/*.tsv (Hive), results/charts/*.png, results/logs/*.log, report/team.json, source code.
usage  : python3 report/build_report.py && node report/html_to_pdf.js
"""
import base64
import csv
import html
import json
import os
import re

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
R = os.path.join(ROOT, "results")


def read_tsv(name):
    with open(os.path.join(R, name + ".tsv"), encoding="utf-8") as f:
        rows = list(csv.reader(f, delimiter="\t"))
    return [h.split(".")[-1] for h in rows[0]], rows[1:]


def img(name, caption):
    with open(os.path.join(R, "charts", name), "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f'<figure><img src="data:image/png;base64,{b64}"><figcaption>{caption}</figcaption></figure>'


def table(header, rows, caption=None, num_cols=(), max_rows=None):
    rows = rows[:max_rows] if max_rows else rows
    out = ["<table>"]
    if caption:
        out.append(f"<caption>{caption}</caption>")
    out.append("<tr>" + "".join(f"<th>{html.escape(h)}</th>" for h in header) + "</tr>")
    for r in rows:
        cells = []
        for i, c in enumerate(r):
            cls = ' class="num"' if i in num_cols else ""
            cells.append(f"<td{cls}>{html.escape(c)}</td>")
        out.append("<tr>" + "".join(cells) + "</tr>")
    out.append("</table>")
    return "\n".join(out)


def fmt_int(s):
    try:
        return f"{int(float(s)):,}"
    except ValueError:
        return s


def code(text, lang=""):
    return f'<pre class="code">{html.escape(text.rstrip())}</pre>'


def snippet(rel_path, start, end, include_end=True):
    """Text of a source file from the line containing `start` to the line containing `end`."""
    with open(os.path.join(ROOT, rel_path), encoding="utf-8") as f:
        lines = f.read().splitlines()
    i = next(k for k, l in enumerate(lines) if start in l)
    j = next(k for k in range(i, len(lines)) if end in lines[k])
    block = lines[i:j + 1] if include_end else lines[i:j]
    indent = min(len(l) - len(l.lstrip()) for l in block if l.strip())
    return "\n".join(l[indent:] for l in block)


def log_text(name):
    p = os.path.join(R, "logs", name)
    return open(p, encoding="utf-8").read() if os.path.exists(p) else ""


def counters(log):
    c = {}
    for m in re.finditer(r"^\s{6}([A-Z_]+)\s+([\d,]+)$", log, re.M):
        c.setdefault(m.group(1), m.group(2))
    return c


def job_times(log):
    return dict(re.findall(r"(WikiTrend-\d-\w+) done in ([\d.]+) s", log))


def top_block(log, hour, n=10):
    m = re.search(r"=== Trending on Wikipedia, hour " + re.escape(hour) + r" UTC ===\n(.*?)(?:\n\n|\Z)", log, re.S)
    if not m:
        return ""
    lines = m.group(1).splitlines()
    return f"--- hour {hour} UTC ---\n" + "\n".join(lines[: n + 1])


# ------------------------------------------------------------------ data
team = json.load(open(os.path.join(ROOT, "report", "team.json"), encoding="utf-8"))
batch_log = log_text("batch_run.log")
rt_log = log_text("realtime_demo.log")
show_log = log_text("show_hours.log")
C = counters(batch_log)
T = job_times(batch_log)
total_s = float(re.search(r"Pipeline finished in ([\d.]+) s", batch_log).group(1))
raw_lines = sum(int(C[k].replace(",", "")) for k in ("ACCEPTED", "NON_ARTICLE_PAGE", "NON_WIKIPEDIA_PROJECT"))

q1h, q1 = read_tsv("q1_top_stories")
q3h, q3 = read_tsv("q3_spikes_per_hour")
q4h, q4 = read_tsv("q4_languages_top_story")
q6h, q6 = read_tsv("q6_new_articles")

members_html = "".join(f"<tr><td>{html.escape(m['name'])}</td><td>{html.escape(m['usn'])}</td></tr>"
                       for m in team["members"])

# ------------------------------------------------------------------ diagrams (inline SVG)
ARCH_SVG = """
<svg viewBox="0 0 760 330" class="diagram" role="img" aria-label="Single-node Hadoop cluster">
 <defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#52514e"/></marker></defs>
 <rect x="10" y="10" width="740" height="310" rx="10" fill="#f4f3ef" stroke="#c9c7bf"/>
 <text x="24" y="34" class="t">Ubuntu VM  -  single-node (pseudo-distributed) Hadoop 3.3.6 cluster, Java 8</text>
 <rect x="30" y="50" width="330" height="150" rx="8" fill="#e3eefc" stroke="#2a78d6"/>
 <text x="45" y="72" class="h">HDFS (storage)</text>
 <rect x="45" y="85" width="140" height="48" rx="6" fill="#fff" stroke="#2a78d6"/><text x="115" y="106" class="c">NameNode</text><text x="115" y="122" class="s">metadata, :9870</text>
 <rect x="205" y="85" width="140" height="48" rx="6" fill="#fff" stroke="#2a78d6"/><text x="275" y="106" class="c">DataNode</text><text x="275" y="122" class="s">128 MB blocks, rf=1</text>
 <text x="45" y="158" class="s2">/wikitrend/raw      30 files, 5.6 GB, 60 blocks</text>
 <text x="45" y="176" class="s2">/wikitrend/out      agg/ spikes/ top/ (hour=X)</text>
 <text x="45" y="192" class="s2">/wikitrend/landing  /live  /archive   (real-time)</text>
 <rect x="400" y="50" width="330" height="150" rx="8" fill="#fde8de" stroke="#eb6834"/>
 <text x="415" y="72" class="h">YARN (compute)</text>
 <rect x="415" y="85" width="140" height="48" rx="6" fill="#fff" stroke="#eb6834"/><text x="485" y="106" class="c">ResourceManager</text><text x="485" y="122" class="s">scheduling, :8088</text>
 <rect x="575" y="85" width="140" height="48" rx="6" fill="#fff" stroke="#eb6834"/><text x="645" y="106" class="c">NodeManager</text><text x="645" y="122" class="s">6 GB, 4 vcores</text>
 <text x="415" y="158" class="s2">MapReduce tasks run in YARN containers</text>
 <text x="415" y="176" class="s2">map 1 GB, reduce 1.5 GB, AM 1 GB</text>
 <text x="415" y="192" class="s2">JobHistoryServer :19888 (logs, counters)</text>
 <rect x="30" y="225" width="330" height="80" rx="8" fill="#e1f5ec" stroke="#1baf7a"/>
 <text x="45" y="247" class="h">Client / driver</text>
 <text x="45" y="267" class="s2">hadoop jar wikitrend.jar batch | hour | show</text>
 <text x="45" y="285" class="s2">producer + consumer scripts (real-time)</text>
 <rect x="400" y="225" width="330" height="80" rx="8" fill="#fdf1d6" stroke="#eda100"/>
 <text x="415" y="247" class="h">Hive 3.1.3 (analysis)</text>
 <text x="415" y="267" class="s2">external partitioned tables over /wikitrend/out</text>
 <text x="415" y="285" class="s2">Derby metastore, RCFile table, Java UDFs</text>
 <line x1="360" y1="265" x2="398" y2="265" stroke="#52514e" marker-end="url(#a)"/>
 <line x1="195" y1="225" x2="195" y2="202" stroke="#52514e" marker-end="url(#a)"/>
 <line x1="565" y1="225" x2="565" y2="202" stroke="#52514e" marker-end="url(#a)"/>
 <line x1="362" y1="110" x2="398" y2="110" stroke="#52514e" marker-end="url(#a)"/>
 <line x1="398" y1="125" x2="362" y2="125" stroke="#52514e" marker-end="url(#a)"/>
</svg>"""

PIPE_SVG = """
<svg viewBox="0 0 760 250" class="diagram" role="img" aria-label="Three-job MapReduce pipeline">
 <defs><marker id="b" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#52514e"/></marker></defs>
 <g>
 <rect x="10" y="20" width="130" height="80" rx="8" fill="#f4f3ef" stroke="#c9c7bf"/>
 <text x="75" y="48" class="c">Raw hourly dumps</text><text x="75" y="66" class="s">HDFS /wikitrend/raw</text><text x="75" y="82" class="s">183 M lines</text>
 <rect x="165" y="20" width="175" height="80" rx="8" fill="#e3eefc" stroke="#2a78d6"/>
 <text x="252" y="44" class="c">Job 1  Aggregate</text><text x="252" y="62" class="s">parse, clean, filter</text><text x="252" y="78" class="s">combiner sums desktop+mobile</text><text x="252" y="94" class="s">MultipleOutputs: hour=X</text>
 <rect x="365" y="20" width="185" height="80" rx="8" fill="#e3eefc" stroke="#2a78d6"/>
 <text x="457" y="44" class="c">Job 2  SpikeDetection</text><text x="457" y="62" class="s">secondary sort (article,hour)</text><text x="457" y="78" class="s">6-hour sliding baseline</text><text x="457" y="94" class="s">z-score + ratio test</text>
 <rect x="575" y="20" width="175" height="80" rx="8" fill="#e3eefc" stroke="#2a78d6"/>
 <text x="662" y="44" class="c">Job 3  TopSpikes</text><text x="662" y="62" class="s">in-mapper Top-N</text><text x="662" y="78" class="s">HourPartitioner</text><text x="662" y="94" class="s">global Top-25 per hour</text>
 <line x1="140" y1="60" x2="163" y2="60" stroke="#52514e" marker-end="url(#b)"/>
 <line x1="340" y1="60" x2="363" y2="60" stroke="#52514e" marker-end="url(#b)"/>
 <line x1="550" y1="60" x2="573" y2="60" stroke="#52514e" marker-end="url(#b)"/>
 <text x="252" y="122" class="s">agg/ 132 M rows, 3.3 GB</text><text x="457" y="122" class="s">spikes/ 3,739 rows</text><text x="662" y="122" class="s">top/ ranked lists</text>
 <rect x="165" y="150" width="385" height="80" rx="8" fill="#fdf1d6" stroke="#eda100"/>
 <text x="357" y="175" class="c">Hive: external tables pageviews_hourly, spikes, top_trending</text>
 <text x="357" y="195" class="s">+ spikes_rc (RCFile) + UDFs wiki_url, pretty_title</text>
 <text x="357" y="213" class="s">6 analysis queries -> results/*.tsv -> charts</text>
 <line x1="252" y1="130" x2="252" y2="148" stroke="#52514e" marker-end="url(#b)"/>
 <line x1="457" y1="130" x2="457" y2="148" stroke="#52514e" marker-end="url(#b)"/>
 <line x1="662" y1="130" x2="545" y2="160" stroke="#52514e" marker-end="url(#b)"/>
 </g>
</svg>"""

RT_SVG = """
<svg viewBox="0 0 760 150" class="diagram" role="img" aria-label="Real-time micro-batch flow">
 <defs><marker id="c" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#52514e"/></marker></defs>
 <rect x="10" y="30" width="150" height="70" rx="8" fill="#e1f5ec" stroke="#1baf7a"/><text x="85" y="58" class="c">Producer</text><text x="85" y="76" class="s">new hourly dump</text><text x="85" y="91" class="s">every N seconds</text>
 <rect x="190" y="30" width="150" height="70" rx="8" fill="#f4f3ef" stroke="#c9c7bf"/><text x="265" y="58" class="c">HDFS landing/</text><text x="265" y="76" class="s">atomic rename</text><text x="265" y="91" class="s">(._COPYING_ hidden)</text>
 <rect x="370" y="30" width="190" height="70" rx="8" fill="#e3eefc" stroke="#2a78d6"/><text x="465" y="54" class="c">Consumer (polls 5 s)</text><text x="465" y="72" class="s">hadoop jar ... hour &lt;file&gt;</text><text x="465" y="88" class="s">Job1 -&gt; Job2 -&gt; Job3</text>
 <rect x="590" y="30" width="160" height="70" rx="8" fill="#fde8de" stroke="#eb6834"/><text x="670" y="58" class="c">Trending list</text><text x="670" y="76" class="s">console + live/top/</text><text x="670" y="91" class="s">file -&gt; archive/</text>
 <line x1="160" y1="65" x2="188" y2="65" stroke="#52514e" marker-end="url(#c)"/>
 <line x1="340" y1="65" x2="368" y2="65" stroke="#52514e" marker-end="url(#c)"/>
 <line x1="560" y1="65" x2="588" y2="65" stroke="#52514e" marker-end="url(#c)"/>
 <text x="465" y="128" class="s">state: previous 6 hours of live/agg/hour=X (kept in HDFS) form the baseline</text>
</svg>"""

# ------------------------------------------------------------------ code excerpts
code_mapper = snippet("src/main/java/com/wikitrend/AggregationJob.java",
                      "protected void map(LongWritable offset, Text line", "    }")
code_parse = snippet("src/main/java/com/wikitrend/PageviewParser.java",
                     "String domain = line.substring(0, s1);", "return Quality.NON_WIKIPEDIA_PROJECT;") + "\n}"
code_reduce = snippet("src/main/java/com/wikitrend/SpikeDetectionJob.java",
                      "protected void reduce(ArticleHourKey key", "/part\");")
code_score = snippet("src/main/java/com/wikitrend/SpikeDetector.java",
                     "double sum = 0;", "out.excess = views - mean;")
code_driver = snippet("src/main/java/com/wikitrend/SpikeDetectionJob.java",
                      "job.setMapperClass(SpikeMapper.class);", "job.setGroupingComparatorClass")
code_part = snippet("src/main/java/com/wikitrend/TopSpikesJob.java",
                    "public static class HourPartitioner", "  }\n", include_end=True) if False else snippet(
    "src/main/java/com/wikitrend/TopSpikesJob.java", "public static class HourPartitioner", "return (int)")
code_udf = snippet("hive/udf/com/wikitrend/hive/WikiUrlUDF.java", "public class WikiUrlUDF", "return \"https://")
hql_tables = snippet("hive/01_create_tables.hql", "CREATE EXTERNAL TABLE IF NOT EXISTS spikes (", "LOCATION '${hivevar:OUT}/spikes';")
hql_q4 = open(os.path.join(ROOT, "hive/queries/q4_languages_top_story.hql"), encoding="utf-8").read()

COMMANDS = """# --- one-time setup: Java 8, Maven, Hadoop 3.3.6, configs, hdfs namenode -format, mvn package
scripts/01_install_hadoop.sh
# --- start daemons (no SSH needed)
hdfs --daemon start namenode;        hdfs --daemon start datanode
yarn --daemon start resourcemanager; yarn --daemon start nodemanager
mapred --daemon start historyserver; jps
# --- data ingestion (curl https://dumps.wikimedia.org/other/pageviews/2022/2022-09/...)
scripts/03_download_data.sh
hdfs dfs -mkdir -p /wikitrend/raw
zcat pageviews-20220908-180000.gz | hdfs dfs -put - /wikitrend/raw/pageviews-20220908-180000
hdfs dfs -ls -h /wikitrend/raw
hdfs dfs -du -s -h /wikitrend/raw
hdfs fsck /wikitrend/raw
# --- build and run MapReduce ------------------------------------------------------
mvn package
hadoop jar target/wikitrend.jar batch /wikitrend/raw /wikitrend/out
hadoop jar target/wikitrend.jar show /wikitrend/out 2022-09-08T18 15
hadoop jar target/wikitrend.jar -D wikitrend.z.threshold=6 batch /wikitrend/raw /wikitrend/out2
hdfs dfs -ls /wikitrend/out/top
hdfs dfs -cat /wikitrend/out/top/hour=2022-09-08T18/part-r-00000 | head
# --- real-time mode ---------------------------------------------------------------
scripts/07_realtime_consumer.sh                      # polls: hdfs dfs -ls -C /wikitrend/landing
scripts/06_realtime_producer.sh 2022-09-08T12 2 60   # hdfs dfs -cp /wikitrend/raw/<hour> /wikitrend/landing/
hadoop jar target/wikitrend.jar hour /wikitrend/landing/pageviews-20220908-120000 /wikitrend/live
hdfs dfs -mv /wikitrend/landing/pageviews-20220908-120000 /wikitrend/archive/
# --- Hive -------------------------------------------------------------------------
scripts/08_install_hive.sh       # schematool -dbType derby -initSchema
hive/build_udf.sh                # javac -cp hive-exec-3.1.3.jar ...; jar cf wikitrend-udf.jar
hive --hivevar OUT=/wikitrend/out -f hive/01_create_tables.hql
hive -S --hivevar UDF_JAR=hive/wikitrend-udf.jar -i hive/init.hql \\
     -f hive/queries/q1_top_stories.hql
python3 viz/make_charts.py
# --- monitoring -------------------------------------------------------------------
yarn application -list
mapred job -status <job_id>
# Web UIs: NameNode :9870   ResourceManager :8088   JobHistory :19888"""

# ------------------------------------------------------------------ tables from logs
timing_rows = [
    ["Job 1 Aggregate", "30 raw files, 5.6 GB (60 splits)", "132,293,753 article-hours, 3.3 GB", f"{float(T['WikiTrend-1-Aggregate']):.0f}"],
    ["Job 2 SpikeDetection", "120 partition files, 3.3 GB", f"{C['SPIKES_FOUND']} spikes, 226 KB", f"{float(T['WikiTrend-2-SpikeDetection']):.0f}"],
    ["Job 3 TopSpikes", "spike partitions", "top-25 per hour, 34 KB", f"{float(T['WikiTrend-3-TopSpikes']):.0f}"],
    ["Total (batch)", "", "", f"{total_s:.0f}"],
]
counter_rows = [
    ["Raw lines read", f"{raw_lines:,}", "all 30 hourly files"],
    ["NON_WIKIPEDIA_PROJECT", C["NON_WIKIPEDIA_PROJECT"], "Wiktionary, Wikibooks, Commons, Wikidata ... dropped"],
    ["NON_ARTICLE_PAGE", C["NON_ARTICLE_PAGE"], "Special:, Talk:, File:, main pages ... dropped"],
    ["ACCEPTED", C["ACCEPTED"], "clean Wikipedia article records"],
    ["VIEWS_ACCEPTED", C["VIEWS_ACCEPTED"], "page views represented by accepted records"],
    ["ARTICLE_HOURS", C["ARTICLE_HOURS"], "(language, article, hour) rows after merging desktop + mobile"],
    ["BELOW_NOISE_FLOOR", C["BELOW_NOISE_FLOOR"], "rows with < 5 views, not shuffled in job 2"],
    ["ARTICLES_SEEN", C["ARTICLES_SEEN"], "distinct articles reaching the job-2 reducers"],
    ["ARTICLES_SKIPPED_LOW_PEAK", C["ARTICLES_SKIPPED_LOW_PEAK"], "never reach 1,000 views/hour: early exit"],
    ["HOURS_SCORED", C["HOURS_SCORED"], "article-hours tested with the z-score"],
    ["SPIKES_FOUND", C["SPIKES_FOUND"], "anomalies detected"],
]

q1_rows = [[r[0], r[1], r[2][-2:] + "h", r[3], fmt_int(r[4]), fmt_int(r[5]), r[6]] for r in q1[:15]]
q4_rows = [[r[0], r[1], fmt_int(r[2]), fmt_int(r[3]), fmt_int(r[4])] for r in q4[:14]]
q6_rows = [[r[0][-2:] + "h", r[1], r[2], fmt_int(r[3]), r[4]] for r in q6[:12]]

# ------------------------------------------------------------------ HTML
members_list = ", ".join(m["name"] for m in team["members"])
H = f"""<!doctype html><html><head><meta charset="utf-8"><title>WikiTrend Project Report</title>
<style>
@page {{ size: A4; margin: 18mm 16mm 18mm 16mm; }}
body {{ font-family: 'DejaVu Sans', Arial, sans-serif; font-size: 10.5pt; line-height: 1.5; color: #1a1a19; }}
h1 {{ font-size: 16pt; margin: 0 0 4mm; border-bottom: 2px solid #2a78d6; padding-bottom: 2mm; page-break-after: avoid; }}
h2 {{ font-size: 12.5pt; margin: 6mm 0 2mm; color: #1c5cab; page-break-after: avoid; }}
h3 {{ font-size: 11pt; margin: 4mm 0 1mm; page-break-after: avoid; }}
.cover {{ page-break-after: always; }}
.newpage {{ page-break-before: always; }}
p {{ margin: 0 0 2.5mm; }}
ul, ol {{ margin: 0 0 3mm; padding-left: 6mm; }}
li {{ margin-bottom: 1mm; }}
table {{ border-collapse: collapse; width: 100%; margin: 2mm 0 4mm; font-size: 9pt; page-break-inside: avoid; }}
caption {{ caption-side: top; text-align: left; font-weight: bold; font-size: 9.5pt; margin-bottom: 1mm; }}
th {{ background: #e3eefc; text-align: left; padding: 1.2mm 2mm; border: 1px solid #c9d8ee; }}
td {{ padding: 1mm 2mm; border: 1px solid #dcdad3; vertical-align: top; }}
td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
pre {{ font-family: 'DejaVu Sans Mono', monospace; font-size: 8pt; line-height: 1.35; background: #f4f3ef;
       border: 1px solid #dcdad3; border-radius: 4px; padding: 2.5mm; white-space: pre-wrap; page-break-inside: avoid; }}
figure {{ margin: 3mm 0 5mm; page-break-inside: avoid; text-align: center; }}
figure img {{ max-width: 100%; }}
figcaption {{ font-size: 9pt; color: #52514e; margin-top: 1mm; }}
.diagram {{ width: 100%; height: auto; margin: 2mm 0; }}
.diagram .t {{ font: bold 12px sans-serif; fill: #1a1a19; }}
.diagram .h {{ font: bold 12px sans-serif; fill: #1a1a19; }}
.diagram .c {{ font: bold 11px sans-serif; fill: #1a1a19; text-anchor: middle; }}
.diagram .s {{ font: 10px sans-serif; fill: #52514e; text-anchor: middle; }}
.diagram .s2 {{ font: 10.5px monospace; fill: #33322f; }}
.cover {{ text-align: center; padding-top: 25mm; }}
.cover .uni {{ font-size: 15pt; font-weight: bold; }}
.cover .dept {{ font-size: 11pt; margin-bottom: 18mm; }}
.cover .course {{ font-size: 11pt; color: #52514e; }}
.cover .title {{ font-size: 21pt; font-weight: bold; color: #1c5cab; margin: 10mm 10mm 4mm; line-height: 1.3; }}
.cover .sub {{ font-size: 11pt; margin-bottom: 16mm; }}
.cover table {{ width: 60%; margin: 0 auto 10mm; font-size: 10.5pt; }}
.kpi {{ display: flex; gap: 3mm; margin: 3mm 0 4mm; }}
.kpi div {{ flex: 1; border: 1px solid #c9d8ee; border-radius: 5px; padding: 2mm; text-align: center; background: #f7faff; }}
.kpi b {{ display: block; font-size: 14pt; color: #1c5cab; }}
.kpi span {{ font-size: 8.5pt; color: #52514e; }}
.note {{ background: #fdf1d6; border-left: 3px solid #eda100; padding: 2mm 3mm; margin: 2mm 0 4mm; font-size: 9.5pt; }}
.toc li {{ margin-bottom: 1.5mm; }}
pre.long {{ page-break-inside: auto; }}
</style></head><body>

<div class="cover">
  <div class="uni">KLE Technological University</div>
  <div class="dept">Department of Computer Science &amp; Engineering (AI)</div>
  <div class="course">Big Data Analytics (26ECAE417) &middot; Course Project<br>Implementation of a Real-Time Application using Hadoop</div>
  <div class="title">Real-Time Breaking-News Detection from Wikipedia Traffic Using Hadoop</div>
  <div class="sub">WikiTrend: Hadoop MapReduce &middot; HDFS &middot; YARN &middot; Hive</div>
  <table><tr><th>Team member</th><th>USN</th></tr>{members_html}</table>
  <div class="course">Under the guidance of: {html.escape(team['guide'])}<br>{html.escape(team['semester'])}</div>
</div>

<section>
<h1>Contents</h1>
<ol class="toc">
<li>Project Title</li><li>Abstract</li><li>Introduction</li><li>Problem Statement</li><li>Objectives</li>
<li>Dataset Description</li><li>Software &amp; Tools Used</li><li>Hadoop Architecture</li><li>Methodology</li>
<li>Implementation</li><li>Commands Used</li><li>Results / Output</li><li>Conclusion</li>
</ol>

<h1>1. Project Title</h1>
<p><b>Real-Time Breaking-News Detection from Wikipedia Traffic Using Hadoop</b> (short name: <i>WikiTrend</i>).</p>

<h1>2. Abstract</h1>
<p>When a major event happens, millions of people look it up on Wikipedia within minutes, so sudden surges in
article traffic are an early, language-independent signal of breaking news. This project builds
<b>WikiTrend</b>, a Hadoop-based system that ingests Wikimedia's public hourly pageview logs into <b>HDFS</b> and
processes them with a chain of three <b>Java MapReduce</b> jobs. The jobs clean and aggregate the logs,
learn every article's normal traffic level from a sliding six-hour baseline, flag statistically abnormal
surges with a <b>z-score anomaly test</b>, and rank the trending articles of each hour. The system runs in two
modes: a batch mode over the full dataset and a <b>real-time micro-batch mode</b> that processes each new
hourly file as soon as it lands in HDFS. The results are analysed with <b>Hive</b> (external partitioned tables,
an RCFile table, window functions and custom Java UDFs) and visualised as charts.</p>
<p>We evaluated the system on 30 hours of logs (7&ndash;8 September 2022, <b>5.6 GB, {raw_lines/1e6:.0f} million
records, 327 language editions</b>), which include the death of Queen Elizabeth II. The full pipeline ran in
{total_s/60:.0f} minutes on a single-node cluster and found {C['SPIKES_FOUND']} spikes. It detected the story at
<b>12:00 UTC, five and a half hours before the official announcement</b>, from reader behaviour alone. It then
tracked how the story spread to every major language edition. In real-time mode each new hour was fully
processed in under three minutes, and the output matched the batch results exactly.</p>
</section>

<section>
<h1>3. Introduction</h1>
<p>Wikipedia is one of the most visited websites in the world, receiving roughly 20&ndash;35 million article
views every hour. The Wikimedia Foundation publishes these counts openly: every hour a new file lists how many
times each page of each project and language was viewed. A single hour is about 6.8 million lines and
200 MB uncompressed, so a day is about 4.5 GB. That is too much for a spreadsheet or a single script to
analyse repeatedly, but well suited to the Hadoop ecosystem studied in this course.</p>
<p>Reader attention is a powerful real-time sensor. People turn to Wikipedia the moment they hear about an
event, often before detailed news coverage exists, so a surge in views of an article is a sign that something
newsworthy is happening. This works across all languages and topics, with no text analysis and no reliance on
any news source. Detecting such surges is a <b>big-data stream-analytics problem</b>: the data arrives
continuously (one file per hour), is large (Volume), is published every hour (Velocity), spans 300+ languages
and many kinds of pages (Variety), and contains noise from automated traffic, page renames and navigation
pages (Veracity).</p>
<p>WikiTrend implements this end-to-end on Hadoop. HDFS stores the raw logs and all intermediate results.
MapReduce on YARN does the cleaning, aggregation, statistical anomaly detection and ranking. Hive provides an
SQL layer for analysis. The project covers the course outcomes: big-data storage (HDFS, block storage,
replication, CO2), distributed processing with MapReduce (CO3, CO4), stream processing concepts such as sources,
sinks, sliding windows and stateful micro-batches (CO3), and analysis and visualisation with Hive (CO5).</p>

<h1>4. Problem Statement</h1>
<p>Given a continuous stream of hourly Wikipedia pageview logs (several GB per day, across 300+ language
editions), detect <b>as soon as each hour's data arrives</b> which articles are receiving abnormally high
attention compared with their own recent history, and rank them, so that breaking news and emerging trends can
be identified automatically. The solution must store the data in HDFS, process it with Hadoop MapReduce, scale
to the full volume of the logs, separate real surges from normal daily traffic swings, and make the results
available for further analysis.</p>
<p><b>Scope:</b> Wikipedia article pages only (desktop and mobile); hourly granularity (the publishing rate of the
source); detection based on view counts only (no text analysis); evaluated on a historical window replayed as a
live stream.</p>

<h1>5. Objectives</h1>
<ol>
<li>Collect a public real-world dataset of at least 4 GB (achieved: 5.6 GB) and store it in HDFS.</li>
<li>Design and implement a multi-stage Hadoop MapReduce pipeline in Java to clean, aggregate and analyse it,
using combiners, custom keys, partitioners, grouping comparators (secondary sort) and multiple outputs.</li>
<li>Implement a statistical anomaly detector (z-score against a sliding baseline window) that finds sudden
surges in attention and ignores normal daily traffic patterns.</li>
<li>Run the pipeline both as a batch job and as a real-time micro-batch application that processes each new
hourly file as it arrives.</li>
<li>Expose the results through Hive tables and queries, and visualise them.</li>
<li>Validate the system on a real event and measure its performance.</li>
</ol>
</section>

<section>
<h1>6. Dataset Description</h1>
<p><b>Source:</b> Wikimedia Foundation, <i>pageviews</i> dumps, <code>https://dumps.wikimedia.org/other/pageviews/</code>
(public domain / CC0, no registration needed). One gzip file is published per hour, named
<code>pageviews-YYYYMMDD-HH0000.gz</code>. Each line counts the views of one page in one project during that
hour (user traffic only; known automated traffic is excluded by Wikimedia).</p>
<table><caption>Table 6.1 Record format (space separated)</caption>
<tr><th>Field</th><th>Example</th><th>Meaning</th></tr>
<tr><td>domain_code</td><td><code>en</code>, <code>en.m</code>, <code>de.m</code>, <code>en.d</code></td><td>language + project; <code>.m</code> = mobile site; suffixes such as <code>.d</code> (Wiktionary) and <code>.b</code> (Wikibooks) mark other projects</td></tr>
<tr><td>page_title</td><td><code>Elizabeth_II</code></td><td>article title, spaces written as underscores</td></tr>
<tr><td>count_views</td><td><code>2221743</code></td><td>number of views in the hour</td></tr>
<tr><td>total_response_size</td><td><code>0</code></td><td>always 0 (kept for compatibility)</td></tr>
</table>
<pre>en Elizabeth_II 736731 0                  &lt;- desktop
en.m Elizabeth_II 1485012 0               &lt;- mobile (job 1 merges: 2,221,743 views at 18:00 UTC)
es.m Isabel_II_del_Reino_Unido 508242 0
en Special:Search 39399 0                 &lt;- non-article page, dropped
en.d dog 6 0                              &lt;- Wiktionary, dropped</pre>
<p>Real lines from <code>pageviews-20220908-180000</code>.</p>
<table><caption>Table 6.2 Dataset used in this project</caption>
<tr><th>Property</th><th>Value</th></tr>
<tr><td>Time window</td><td>2022-09-07 18:00 to 2022-09-08 23:00 UTC (30 consecutive hours)</td></tr>
<tr><td>Files</td><td>30 hourly files (1.5 GB compressed download)</td></tr>
<tr><td>Size in HDFS</td><td><b>5,611,859,442 bytes (5.6 GB)</b>, uncompressed, 60 blocks of 128 MB, status HEALTHY</td></tr>
<tr><td>Records</td><td>{raw_lines:,} lines (about 6.1 million per hour)</td></tr>
<tr><td>Coverage</td><td>327 Wikipedia language editions + other Wikimedia projects</td></tr>
<tr><td>Page views represented</td><td>{C['VIEWS_ACCEPTED']} article views after cleaning</td></tr>
<tr><td>Ground-truth event</td><td>death of Queen Elizabeth II: Palace statement on her health about 12:30 UTC, death announced 17:30 UTC on 8 Sep 2022</td></tr>
</table>
<p><b>Why this window:</b> it contains a globally known event with precisely documented timestamps, which lets us
check whether the detector finds the right articles at the right time. The six hours of 7 September give the
first hours of 8 September a full baseline. The same code runs unchanged on any other date via
<code>DATA_START</code> in <code>scripts/env.sh</code>.</p>
<p><b>Data quality issues handled:</b> other Wikimedia projects mixed into the same file; non-article pages
(Special:Search, Talk:, File:, main pages, including localised namespaces); the same article counted
separately for desktop and mobile; malformed lines; a long tail of millions of pages with 1&ndash;4 views; and
pages created or renamed during an event (no history).</p>

<h1>7. Software &amp; Tools Used</h1>
<table>
<tr><th>Component</th><th>Version</th><th>Role in the project</th></tr>
<tr><td>Ubuntu Linux (VM)</td><td>64-bit</td><td>operating system of the single-node cluster</td></tr>
<tr><td>OpenJDK</td><td>1.8</td><td>runtime and compiler (Hadoop 3.3 and Hive 3.1 require Java 8)</td></tr>
<tr><td>Apache Hadoop &ndash; HDFS</td><td>3.3.6</td><td>distributed storage of raw logs, intermediate and final results</td></tr>
<tr><td>Apache Hadoop &ndash; YARN</td><td>3.3.6</td><td>resource management and scheduling of MapReduce containers</td></tr>
<tr><td>Apache Hadoop &ndash; MapReduce</td><td>3.3.6</td><td>the three processing jobs (Java API, <code>org.apache.hadoop.mapreduce</code>)</td></tr>
<tr><td>Apache Hive</td><td>3.1.3</td><td>SQL analysis on HDFS output; Derby metastore; RCFile; UDFs</td></tr>
<tr><td>Apache Maven</td><td>3.x</td><td>build of <code>wikitrend.jar</code>, JUnit 4 unit tests</td></tr>
<tr><td>Python 3 + matplotlib</td><td>3.x</td><td>charts from the Hive query results</td></tr>
<tr><td>Bash, curl, Git</td><td>&ndash;</td><td>automation scripts, data download, version control</td></tr>
</table>
</section>

<section class="newpage">
<h1>8. Hadoop Architecture</h1>
<p>The project runs on a <b>pseudo-distributed (single-node) Hadoop cluster</b>: every Hadoop daemon runs as a
separate Java process on one Ubuntu VM and communicates over the network exactly as on a multi-node cluster,
so the same jar runs unchanged on a real cluster.</p>
{ARCH_SVG}
<h3>HDFS</h3>
<ul>
<li><b>NameNode</b> keeps the namespace (directories, files, block locations); <b>DataNode</b> stores the
128 MB blocks. Each hourly file of about 190 MB is split into 2 blocks, so 30 files = 60 blocks.</li>
<li><b>Replication factor 1</b>, since there is a single DataNode (on a multi-node cluster the default of 3
gives fault tolerance).</li>
<li>Files are stored <b>uncompressed</b> on purpose: gzip is not splittable, so a compressed hour would be read
by one mapper; uncompressed, each block gets its own mapper (60 parallel map tasks).</li>
<li>Results use Hive-style partition folders (<code>hour=2022-09-08T18</code>), so Hive can query them directly.</li>
</ul>
<h3>YARN and MapReduce</h3>
<ul>
<li>The <b>ResourceManager</b> schedules applications; the <b>NodeManager</b> offers 6 GB / 4 vcores of containers.
Each job gets an ApplicationMaster (1 GB) plus map (1 GB) and reduce (1.5 GB) containers.</li>
<li>Map output is compressed during the shuffle; <code>io.sort.mb</code> is 256 MB to reduce spills.</li>
<li>The <b>JobHistoryServer</b> keeps counters and logs of finished jobs (used for the numbers in this report).</li>
</ul>
<h3>Directory layout in HDFS</h3>
<pre>/wikitrend/raw/pageviews-20220907-180000 ... pageviews-20220908-230000     (input dataset, 5.6 GB)
/wikitrend/out/agg/hour=YYYY-MM-DDTHH/part-r-0000N                         (job 1)
/wikitrend/out/spikes/hour=.../part-r-0000N                                (job 2)
/wikitrend/out/top/hour=.../part-r-0000N                                   (job 3)
/wikitrend/landing  /wikitrend/live/{{agg,spikes,top}}  /wikitrend/archive   (real-time mode)
/user/hive/warehouse/wikitrend.db/spikes_rc                                (Hive RCFile table)</pre>
</section>

<section>
<h1>9. Methodology</h1>
{PIPE_SVG}
<h3>9.1 Ingestion</h3>
<p>The hourly dumps are downloaded from Wikimedia and decompressed directly into HDFS with
<code>zcat file.gz | hdfs dfs -put - /wikitrend/raw/file</code>, without a temporary copy on local disk. The hour
of each record is not stored inside the record; it is taken from the file name of the input split.</p>
<h3>9.2 Job 1: cleaning and aggregation</h3>
<ul>
<li><b>Filter projects:</b> keep only Wikipedia (<code>xx</code> = desktop, <code>xx.m</code> = mobile); drop Wiktionary,
Wikibooks, Commons, Wikidata and others (language code checked with a regular expression).</li>
<li><b>Filter pages:</b> drop non-article namespaces (Special:, Talk:, User:, File:, Category: ... and their
German, Spanish, French, Italian, Russian, Japanese, Polish, Portuguese and Dutch forms) and main pages.
Titles that merely contain a colon (e.g. <i>Star Wars: Andor</i>) are kept.</li>
<li><b>Merge</b> desktop and mobile views of the same article: key = <code>hour, lang, title</code>, value = views.
A <b>combiner</b> sums on the map side, so duplicates are merged before the shuffle.</li>
<li><b>Output</b> with <code>MultipleOutputs</code> into one partition folder per hour.</li>
<li>Hadoop <b>counters</b> record why each line was accepted or rejected (data-quality report).</li>
</ul>
<h3>9.3 Job 2: spike (anomaly) detection</h3>
<p>For every article the reducer needs its views for all hours, <b>in time order</b>. This is done with a
<b>secondary sort</b>: the map output key is the composite <code>(article, hour)</code>; a custom
<b>partitioner</b> and a <b>grouping comparator</b> use only the article, so one <code>reduce()</code> call receives the
article's whole time series already sorted by hour. For each hour <i>h</i> to be scored, with <i>v</i> views
and baseline <i>B</i> = views in the previous <i>W</i> = 6 hours:</p>
<pre>mean   = average(B)                       sigma = max( stddev(B), sqrt(mean + 1) )
z      = (v - mean) / sigma               ratio = v / (mean + 1)            excess = v - mean
spike  if  v &gt;= 1,000  and  z &gt;= 4  and  ratio &gt;= 3</pre>
<ul>
<li>The <b>z-score</b> measures how unusual this hour is for <i>this</i> article, so a page that always gets
1 M views is not flagged while a page that jumps from 300 to 12,000 is.</li>
<li>The <b>sqrt(mean+1) floor</b> (Poisson noise) avoids a zero standard deviation for flat baselines (e.g. 0, 0, 0),
which would make any visit infinitely surprising.</li>
<li>The <b>ratio</b> and <b>minimum views</b> conditions remove statistically significant but practically tiny
changes, as well as normal daily swings of popular pages.</li>
<li><b>Noise floor:</b> hourly counts below 5 are treated as 0 in the mapper. These rows are 84% of all rows
but cannot influence a detection at the 1,000-view threshold, so not shuffling them makes job 2 much
faster. Articles that never reach 1,000 views in any hour are skipped early in the reducer.</li>
<li>Missing hours (no views) count as 0; at least 3 history hours are required before an hour is scored.</li>
</ul>
<h3>9.4 Job 3: ranking</h3>
<p>Spikes are ranked by <b>excess views</b> (extra readers above the baseline), which measures the size of the
story. Each mapper keeps only its local top 25 per hour in a bounded min-heap (<b>in-mapper combining</b>, emitted
in <code>cleanup()</code>). A custom <b>HourPartitioner</b> spreads consecutive hours round-robin over the reducers,
which merge the candidates into the global top 25 per hour.</p>
<h3>9.5 Real-time micro-batch mode</h3>
{RT_SVG}
<p>Wikimedia publishes one file per hour, so the natural real-time unit is the hour, processed by
<b>micro-batching</b> (the model used by Spark Streaming). A producer drops each new file into
<code>/wikitrend/landing</code>. HDFS writes it under a temporary name and renames it atomically, so the consumer
never sees a partial file. The consumer polls the folder every 5 seconds and runs the three jobs on the new
hour only. The <b>state</b> of the stream (aggregated counts of the previous 6 hours) is kept in HDFS, so job 1
processes 1 file instead of 7. Job 2 is a <b>sliding-window, stateful</b> computation over the last 7 partitions.
Each job writes to a private work folder whose partitions are moved into place only after success, so a
failure or re-run never leaves half-written data (<b>idempotent</b> processing).</p>
<h3>9.6 Analysis and visualisation</h3>
<p>Hive <b>external partitioned tables</b> are declared over the three output folders (<code>MSCK REPAIR TABLE</code>
registers the hour partitions). Spikes are also copied into a columnar <b>RCFile</b> table. Two Java <b>UDFs</b>
(<code>wiki_url</code>, <code>pretty_title</code>) format the output. Six HiveQL queries (aggregations, a CTE + join,
window functions) produce the tables and charts in Section 12.</p>
</section>

<section>
<h1>10. Implementation</h1>
<table><caption>Table 10.1 Source code (Java 8, package com.wikitrend)</caption>
<tr><th>Class / file</th><th>Responsibility</th></tr>
<tr><td>WikiTrendDriver</td><td>entry point (Tool/ToolRunner); commands <code>batch</code>, <code>hour</code>, <code>show</code>; chains the jobs, publishes partitions atomically, prints counters</td></tr>
<tr><td>AggregationJob</td><td>Job 1: AggMapper, SumCombiner, AggReducer (MultipleOutputs, LazyOutputFormat)</td></tr>
<tr><td>PageviewParser</td><td>fast parsing and cleaning of one raw line; Quality enum used as counters</td></tr>
<tr><td>SpikeDetectionJob</td><td>Job 2: SpikeMapper (noise floor), SpikeReducer (sliding baseline window)</td></tr>
<tr><td>ArticleHourKey</td><td>composite WritableComparable key + ArticlePartitioner + ArticleGroupingComparator (secondary sort)</td></tr>
<tr><td>SpikeDetector</td><td>pure statistics (mean, sigma, z, ratio), unit-tested</td></tr>
<tr><td>TopSpikesJob</td><td>Job 3: TopMapper (in-mapper Top-N), HourPartitioner, TopReducer</td></tr>
<tr><td>HourUtil, Config</td><td>hour labels / epoch hours; tunable parameters (<code>-D wikitrend.*</code>)</td></tr>
<tr><td>WikiTrendTest</td><td>8 JUnit tests: parsing, filtering, hour labels, spike maths, zero-baseline edge case</td></tr>
<tr><td>hive/*.hql, WikiUrlUDF, PrettyTitleUDF</td><td>Hive tables, queries and UDFs</td></tr>
<tr><td>scripts/01..09_*.sh</td><td>installation, start-up, download, HDFS load, batch run, real-time producer/consumer, Hive</td></tr>
</table>
<h3>10.1 Job 1 mapper and cleaning</h3>
{code(code_mapper)}
{code(code_parse)}
<h3>10.2 Job 2: secondary sort configuration and the spike reducer</h3>
{code(code_driver)}
{code(code_reduce)}
<h3>10.3 Spike statistics</h3>
{code(code_score)}
<h3>10.4 Job 3 partitioner</h3>
{code(code_part)}
<h3>10.5 Hive table and UDF</h3>
{code(hql_tables)}
{code(code_udf)}
<h3>10.6 Hive window-function query (Q4)</h3>
{code(hql_q4)}
</section>

<section>
<h1>11. Commands Used</h1>
{code(COMMANDS)}
</section>

<section class="newpage">
<h1>12. Results / Output</h1>
<div class="kpi">
<div><b>5.6 GB</b><span>dataset in HDFS (60 blocks)</span></div>
<div><b>{raw_lines/1e6:.0f} M</b><span>records processed</span></div>
<div><b>{total_s/60:.0f} min</b><span>full 3-job pipeline</span></div>
<div><b>{C['SPIKES_FOUND']}</b><span>spikes detected</span></div>
<div><b>&lt; 3 min</b><span>per new hour (real-time)</span></div>
</div>
<h2>12.1 Performance (single-node cluster, 4 vcores, 6 GB YARN memory)</h2>
{table(["Job", "Input", "Output", "Time (s)"], timing_rows, num_cols=(3,))}
{table(["Counter", "Value", "Meaning"], counter_rows, caption="Table 12.2 Hadoop counters of the batch run (data quality and filtering)", num_cols=(1,))}
<p>Job 1 reads the full 5.6 GB and dominates the runtime. The noise floor and the early exit cut Job 2's work
from 132 M rows to about 22 M shuffled rows; only 4,058 of 2.9 M articles ever reach 1,000 views in an hour.</p>

<h2>12.2 Detection timeline of the event</h2>
{img("1_story_timeline.png", "Figure 12.1 Hourly views of the biggest English stories (log scale). The surge starts at 12:00 UTC, when the Palace said doctors were concerned, five and a half hours before the announcement.")}
<p>The detector's ranked output per hour (console output of the <code>show</code> command) tells the story:</p>
<pre>{html.escape(top_block(show_log, "2022-09-08T11", 4))}

{html.escape(top_block(show_log, "2022-09-08T12", 6))}

{html.escape(top_block(show_log, "2022-09-08T13", 6))}</pre>
<ul>
<li><b>11:00</b>: normal hour, small unrelated trends.</li>
<li><b>12:00</b>: <i>Elizabeth II</i> (z = 293), <i>Operation London Bridge</i> (the UK's plan for the Queen's death,
z = 827), <i>List of longest-reigning monarchs</i> and the French article are flagged. <b>The story is detected
5.5 hours before the official announcement</b>.</li>
<li><b>13:00</b>: <i>Balmoral Castle</i> (her residence), <i>Charles, Prince of Wales</i>, the Spanish article.</li>
</ul>
<pre>{html.escape(top_block(show_log, "2022-09-08T18", 12))}</pre>
<p>At <b>18:00</b>, the hour after the announcement, 8 of the top 11 places are the Queen's article in English,
Spanish, Polish, French, Russian, Italian, German and Portuguese. Rank 4, <i>Charles, King of the United Kingdom</i>,
had <b>no traffic at all</b> in the previous six hours: it is a new page name created by editors as the news broke.</p>
{img("2_spikes_per_hour.png", "Figure 12.2 Total excess views of all detected spikes per hour: a quantitative measure of news intensity.")}

<h2>12.3 Hive analysis</h2>
{table(["lang", "article", "first", "hours", "peak views", "max excess", "max z"], q1_rows, caption="Table 12.3 Q1: biggest stories of the period (ranked by largest hourly excess views)", num_cols=(3, 4, 5, 6))}
<p>Very large z values (e.g. 289,395) belong to pages with a zero baseline: with sigma floored at 1, z equals the
view count. This is why spikes are ranked by excess views rather than by z (see also Table 12.5).</p>
{img("3_top_stories.png", "Figure 12.3 Biggest stories across all languages, with the hour of first detection.")}
{table(["lang", "#1 trending article at 18:00 UTC", "views", "baseline", "excess"], q4_rows, caption="Table 12.4 Q4: the number-one story in each language edition at 18:00 UTC (window function ROW_NUMBER)", num_cols=(2, 3, 4))}
{table(["hour", "lang", "article", "views", "baseline"], q6_rows, caption="Table 12.5 Q6 (RCFile table): articles born during the event: new or renamed pages with no previous traffic", num_cols=(3, 4))}
{img("4_language_traffic.png", "Figure 12.4 Total article traffic of the largest language editions: the daily rhythm of each region and the jump at 18:00-19:00 UTC.")}

<h2>12.4 Real-time mode</h2>
<p>The producer published the 12:00 and 13:00 files one minute apart; the consumer detected each file and ran
the three jobs on it. Console output (excerpt):</p>
<pre class="long">{html.escape(rt_log)}</pre>
<p>Each hour was fully processed in under three minutes, well within the one-hour publishing interval of the
source (latency under 5% of the interval). The ranked lists are <b>identical</b> to the batch run, which confirms
that the incremental, stateful processing is correct.</p>
<div class="note"><b>Other events found without supervision</b> in the same 30 hours include the US Open tennis
quarter-finals (<i>Jessica Pegula</i>, <i>Iga &#346;wi&#261;tek</i>, <i>Jannik Sinner</i>, <i>Carlos Alcaraz</i> at night
UTC), the cricket Asia Cup (<i>Virat Kohli</i>, z = 43) and a monkeypox news item. They show that the detector is
general and not tuned to one event.</div>
</section>

<section>
<h1>13. Conclusion</h1>
<p>WikiTrend shows that reader traffic on Wikipedia is an early, language-independent signal of breaking news,
and that Hadoop can turn this large, noisy public log into a working real-time detection system. The project met
all the guideline requirements: a real-time application built on Hadoop, a 5.6 GB dataset stored in HDFS,
processing with Hadoop MapReduce, a working demonstration (batch and live), and this report.</p>
<p>Key outcomes:</p>
<ul>
<li>A three-stage MapReduce pipeline in Java that uses combiners, composite keys with secondary sort, custom
partitioners and grouping comparators, MultipleOutputs, in-mapper Top-N and counters. It processes 183 M
records in {total_s/60:.0f} minutes on a single node.</li>
<li>A statistical anomaly detector (z-score on a sliding 6-hour baseline with a Poisson floor) that found the
story <b>5.5 hours before the official announcement</b>, followed its spread across eight-plus languages and
also detected unrelated events (sport, health) without any tuning.</li>
<li>A real-time micro-batch mode with state kept in HDFS and idempotent, atomic outputs: each new hour is
processed in under 3 minutes, with results identical to the batch run.</li>
<li>A Hive layer (external partitioned tables, RCFile, CTE/join, window functions, Java UDFs) and charts for
analysis.</li>
</ul>
<h3>Limitations</h3>
<ul>
<li>Hourly granularity is set by the source: an event is detected within the hour, not within minutes.</li>
<li>When a story builds up over several hours (12:00&ndash;17:00), the baseline adapts, so the article is flagged
at the start of the story and again at the much larger jump (18:00), but not in every hour in between.</li>
<li>Page renames create "new" articles with no history (they are reported, correctly, as new pages).</li>
<li>The cluster is a single node; the code is cluster-ready, but scaling was not measured on multiple machines.</li>
</ul>
<h3>Future work</h3>
<ul>
<li>Group articles about the same event across languages using Wikidata IDs, to report one event instead of many articles.</li>
<li>Use the minute-level Wikimedia EventStreams API with Spark Structured Streaming for lower latency.</li>
<li>Seasonality-aware baselines (same hour last week) to further reduce false positives.</li>
<li>Push alerts and a live dashboard on top of the <code>top_trending</code> table.</li>
</ul>
<h3>References</h3>
<ol>
<li>Wikimedia Foundation, Pageview complete dumps documentation, https://dumps.wikimedia.org/other/pageviews/readme.html</li>
<li>Apache Hadoop 3.3.6 documentation: HDFS architecture, MapReduce tutorial, YARN, https://hadoop.apache.org/docs/r3.3.6/</li>
<li>Apache Hive 3.1 documentation: LanguageManual DDL, RCFile, UDFs, https://cwiki.apache.org/confluence/display/Hive</li>
<li>Seema Acharya, Subhashini Chellappan, <i>Big Data and Analytics</i>, 2nd ed., Wiley India, 2022.</li>
<li>Gerard Maas, Fran&ccedil;ois Garillot, <i>Stream Processing with Apache Spark</i>, O'Reilly, 2019.</li>
<li>J. Lin, C. Dyer, <i>Data-Intensive Text Processing with MapReduce</i> (secondary sort, in-mapper combining), Morgan &amp; Claypool, 2010.</li>
</ol>
</section>
</body></html>"""

out = os.path.join(ROOT, "report", "WikiTrend_Report.html")
with open(out, "w", encoding="utf-8") as f:
    f.write(H)
print("wrote", out)
