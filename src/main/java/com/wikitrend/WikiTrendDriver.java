package com.wikitrend;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.FileDescriptor;
import java.io.FileOutputStream;
import java.io.InputStreamReader;
import java.io.PrintStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;
import java.util.Locale;
import java.util.TreeSet;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.conf.Configured;
import org.apache.hadoop.fs.FileStatus;
import org.apache.hadoop.fs.FileSystem;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.mapreduce.Counter;
import org.apache.hadoop.mapreduce.CounterGroup;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.util.Tool;
import org.apache.hadoop.util.ToolRunner;

/**
 * Entry point. Chains the three MapReduce jobs:
 *
 * <pre>
 *   raw hourly dumps --[1 Aggregate]--> agg/hour=X --[2 SpikeDetection]--> spikes/hour=X --[3 TopSpikes]--> top/hour=X
 * </pre>
 *
 * Commands:
 * <pre>
 *   batch  &lt;rawDir&gt;  &lt;outDir&gt;            process every hourly file in rawDir (historical / full-day run)
 *   hour   &lt;rawFile&gt; &lt;outDir&gt;            process ONE newly arrived hour (real-time micro-batch);
 *                                           re-uses the already aggregated previous hours as the baseline
 *   show   &lt;outDir&gt;  &lt;hourLabel&gt; [n]      print the ranked spikes of an hour
 * </pre>
 * Each job writes to a private work directory; its hour=X partitions are then moved into place, so a
 * failed or re-run job never leaves half-written partitions behind (Hive sees only complete hours).
 */
public class WikiTrendDriver extends Configured implements Tool {

  /** Console output in UTF-8 regardless of the JVM's default charset (titles are in every script). */
  private static final PrintStream OUT = utf8Stdout();

  private static PrintStream utf8Stdout() {
    try {
      return new PrintStream(new FileOutputStream(FileDescriptor.out), true, "UTF-8");
    } catch (java.io.UnsupportedEncodingException e) {
      return System.out;
    }
  }

  public static void main(String[] args) throws Exception {
    System.exit(ToolRunner.run(new Configuration(), new WikiTrendDriver(), args));
  }

  @Override
  public int run(String[] args) throws Exception {
    if (args.length >= 3 && "batch".equals(args[0])) {
      return batch(new Path(args[1]), new Path(args[2]));
    }
    if (args.length >= 3 && "hour".equals(args[0])) {
      return hour(new Path(args[1]), new Path(args[2]));
    }
    if (args.length >= 3 && "show".equals(args[0])) {
      show(new Path(args[1]), args[2], args.length > 3 ? Integer.parseInt(args[3]) : 10);
      return 0;
    }
    System.err.println("Usage:\n"
        + "  hadoop jar wikitrend.jar batch <rawDir> <outDir>\n"
        + "  hadoop jar wikitrend.jar hour  <rawFile> <outDir>\n"
        + "  hadoop jar wikitrend.jar show  <outDir> <hourLabel e.g. 2022-09-08T17> [n]\n"
        + "Tuning (generic options, before the command arguments): -D wikitrend.window.hours=6 "
        + "-D wikitrend.z.threshold=4 -D wikitrend.min.ratio=3 -D wikitrend.min.views=1000 -D wikitrend.top.n=25");
    return 2;
  }

  // ---------------------------------------------------------------- batch mode

  private int batch(Path rawDir, Path outDir) throws Exception {
    Configuration conf = getConf();
    FileSystem fs = outDir.getFileSystem(conf);

    TreeSet<Long> hours = new TreeSet<>();
    List<Path> rawFiles = new ArrayList<>();
    for (FileStatus st : rawDir.getFileSystem(conf).listStatus(rawDir)) {
      String label = HourUtil.labelFromFileName(st.getPath().getName());
      if (st.isFile() && label != null) {
        hours.add(HourUtil.toEpochHour(label));
        rawFiles.add(st.getPath());
      }
    }
    if (hours.isEmpty()) {
      System.err.println("No pageviews-YYYYMMDD-HH0000 files found in " + rawDir);
      return 1;
    }
    log("Batch run over %d hourly files (%s .. %s)", hours.size(),
        HourUtil.fromEpochHour(hours.first()), HourUtil.fromEpochHour(hours.last()));

    long t0 = System.currentTimeMillis();
    if (!runAndPublish(AggregationJob.create(conf, rawFiles.toArray(new Path[0]), work(outDir, "agg")),
        fs, outDir, "agg")) {
      return 1;
    }
    long[] all = toArray(hours);
    if (!runAndPublish(SpikeDetectionJob.create(conf, partitions(outDir, "agg", all), work(outDir, "spikes"), all, all),
        fs, outDir, "spikes")) {
      return 1;
    }
    Path[] spikeParts = existing(fs, partitions(outDir, "spikes", all));
    if (spikeParts.length == 0) {
      log("No spikes detected with the current thresholds.");
      return 0;
    }
    if (!runAndPublish(TopSpikesJob.create(conf, spikeParts, work(outDir, "top")), fs, outDir, "top")) {
      return 1;
    }
    log("Pipeline finished in %.1f s", (System.currentTimeMillis() - t0) / 1000.0);
    for (long h : all) {
      if (fs.exists(partition(outDir, "top", h))) {
        show(outDir, HourUtil.fromEpochHour(h), 3);
      }
    }
    return 0;
  }

  // ---------------------------------------------------------------- real-time (one hour) mode

  private int hour(Path rawFile, Path outDir) throws Exception {
    Configuration conf = getConf();
    FileSystem fs = outDir.getFileSystem(conf);
    String label = HourUtil.labelFromFileName(rawFile.getName());
    if (label == null) {
      System.err.println("Not an hourly pageview file: " + rawFile);
      return 1;
    }
    long h = HourUtil.toEpochHour(label);
    int window = conf.getInt(Config.WINDOW_HOURS, Config.DEFAULT_WINDOW_HOURS);
    log("New hour arrived: %s  (file %s)", label, rawFile);
    long t0 = System.currentTimeMillis();

    if (!runAndPublish(AggregationJob.create(conf, new Path[] {rawFile}, work(outDir, "agg")), fs, outDir, "agg")) {
      return 1;
    }

    // Baseline = the previous `window` hours that were already aggregated (state kept in HDFS).
    List<Long> avail = new ArrayList<>();
    for (long x = h - window; x <= h; x++) {
      if (fs.exists(partition(outDir, "agg", x))) {
        avail.add(x);
      }
    }
    long[] available = toArray(avail);
    log("Baseline hours available: %d of %d", available.length - 1, window);
    if (!runAndPublish(SpikeDetectionJob.create(conf, partitions(outDir, "agg", available), work(outDir, "spikes"),
        available, new long[] {h}), fs, outDir, "spikes")) {
      return 1;
    }
    Path spikes = partition(outDir, "spikes", h);
    if (!fs.exists(spikes)) {
      log("No spikes in %s (or not enough history yet).", label);
      return 0;
    }
    if (!runAndPublish(TopSpikesJob.create(conf, new Path[] {spikes}, work(outDir, "top")), fs, outDir, "top")) {
      return 1;
    }
    log("Hour %s processed in %.1f s", label, (System.currentTimeMillis() - t0) / 1000.0);
    show(outDir, label, 10);
    return 0;
  }

  // ---------------------------------------------------------------- show

  private void show(Path outDir, String label, int n) throws IOException {
    FileSystem fs = outDir.getFileSystem(getConf());
    Path dir = new Path(new Path(outDir, "top"), HourUtil.PARTITION_PREFIX + label);
    if (!fs.exists(dir)) {
      OUT.println("No ranking for " + label);
      return;
    }
    List<String[]> rows = new ArrayList<>();
    for (FileStatus st : fs.listStatus(dir)) {
      if (!st.getPath().getName().startsWith("part")) {
        continue;
      }
      try (BufferedReader r = new BufferedReader(new InputStreamReader(fs.open(st.getPath()), StandardCharsets.UTF_8))) {
        String line;
        while ((line = r.readLine()) != null) {
          rows.add(line.split("\t"));
        }
      }
    }
    rows.sort((a, b) -> Integer.compare(Integer.parseInt(a[0]), Integer.parseInt(b[0])));
    OUT.println();
    OUT.println("=== Trending on Wikipedia, hour " + label + " UTC ===");
    OUT.println(String.format(Locale.ROOT, "%-4s %-5s %-45s %10s %10s %8s %8s",
        "#", "lang", "article", "views", "baseline", "z", "x"));
    for (String[] f : rows.subList(0, Math.min(n, rows.size()))) {
      String title = f[2].replace('_', ' ');
      if (title.length() > 45) {
        title = title.substring(0, 42) + "...";
      }
      OUT.println(String.format(Locale.ROOT, "%-4s %-5s %-45s %10s %10.0f %8s %8s",
          f[0], f[1], title, f[3], Double.parseDouble(f[4]), f[5], f[6]));
    }
  }

  // ---------------------------------------------------------------- helpers

  private boolean runAndPublish(Job job, FileSystem fs, Path outDir, String table) throws Exception {
    long t0 = System.currentTimeMillis();
    log("Running %s ...", job.getJobName());
    boolean ok = job.waitForCompletion(getConf().getBoolean("wikitrend.verbose", false));
    double secs = (System.currentTimeMillis() - t0) / 1000.0;
    if (!ok) {
      log("%s FAILED after %.1f s", job.getJobName(), secs);
      return false;
    }
    log("%s done in %.1f s", job.getJobName(), secs);
    printCounters(job);

    Path work = org.apache.hadoop.mapreduce.lib.output.FileOutputFormat.getOutputPath(job);
    Path target = new Path(outDir, table);
    fs.mkdirs(target);
    for (FileStatus st : fs.listStatus(work)) {
      String name = st.getPath().getName();
      if (st.isDirectory() && name.startsWith(HourUtil.PARTITION_PREFIX)) {
        Path dest = new Path(target, name);
        if (fs.exists(dest)) {
          fs.delete(dest, true);   // re-processing an hour replaces it (idempotent)
        }
        fs.rename(st.getPath(), dest);
      }
    }
    fs.delete(work, true);
    return true;
  }

  private void printCounters(Job job) throws IOException {
    for (String group : Arrays.asList(PageviewParser.Quality.class.getName(), AggregationJob.Counters.class.getName(),
        SpikeDetectionJob.Counters.class.getName())) {
      CounterGroup g = job.getCounters().getGroup(group);
      for (Counter c : g) {
        OUT.println(String.format(Locale.ROOT, "      %-28s %,15d", c.getName(), c.getValue()));
      }
    }
  }

  private static Path work(Path outDir, String table) {
    return new Path(outDir, "_work/" + table + "-" + System.currentTimeMillis());
  }

  private static Path partition(Path outDir, String table, long epochHour) {
    return new Path(new Path(outDir, table), HourUtil.PARTITION_PREFIX + HourUtil.fromEpochHour(epochHour));
  }

  private static Path[] partitions(Path outDir, String table, long[] hours) {
    Path[] p = new Path[hours.length];
    for (int i = 0; i < hours.length; i++) {
      p[i] = partition(outDir, table, hours[i]);
    }
    return p;
  }

  private static Path[] existing(FileSystem fs, Path[] paths) throws IOException {
    List<Path> out = new ArrayList<>();
    for (Path p : paths) {
      if (fs.exists(p)) {
        out.add(p);
      }
    }
    return out.toArray(new Path[0]);
  }

  private static long[] toArray(java.util.Collection<Long> c) {
    long[] a = new long[c.size()];
    int i = 0;
    for (long x : c) {
      a[i++] = x;
    }
    return a;
  }

  private static void log(String fmt, Object... args) {
    OUT.println("[WikiTrend] " + String.format(Locale.ROOT, fmt, args));
  }
}
