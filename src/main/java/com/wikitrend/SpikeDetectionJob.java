package com.wikitrend;

import java.io.IOException;
import java.util.Arrays;
import java.util.Locale;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.NullWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.mapreduce.Mapper;
import org.apache.hadoop.mapreduce.Reducer;
import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
import org.apache.hadoop.mapreduce.lib.input.FileSplit;
import org.apache.hadoop.mapreduce.lib.output.FileOutputFormat;
import org.apache.hadoop.mapreduce.lib.output.LazyOutputFormat;
import org.apache.hadoop.mapreduce.lib.output.MultipleOutputs;
import org.apache.hadoop.mapreduce.lib.output.TextOutputFormat;

/**
 * Job 2 - Statistical spike (anomaly) detection with a sliding baseline window.
 *
 * Input : job 1 partitions {@code hour=X/} with lines {@code lang \t title \t views}.
 * Output: partitions {@code hour=X/} with one line per detected spike:
 *         {@code lang \t title \t views \t baseline_mean \t sigma \t z_score \t ratio \t excess_views}
 *
 * Uses a secondary sort (see {@link ArticleHourKey}) so each reduce() call receives one article's
 * complete hourly time series already sorted by time.
 */
public final class SpikeDetectionJob {

  private SpikeDetectionJob() {}

  public enum Counters { BELOW_NOISE_FLOOR, ARTICLES_SEEN, ARTICLES_SKIPPED_LOW_PEAK, HOURS_SCORED, SPIKES_FOUND }

  public static class SpikeMapper extends Mapper<LongWritable, Text, ArticleHourKey, LongWritable> {
    private final ArticleHourKey outKey = new ArticleHourKey();
    private final LongWritable outVal = new LongWritable();
    private long epochHour;
    private long noiseFloor;

    @Override
    protected void setup(Context context) {
      Path file = ((FileSplit) context.getInputSplit()).getPath();
      String label = HourUtil.labelFromPartitionPath(file);
      if (label == null) {
        throw new IllegalArgumentException("Input is not inside an hour=... partition: " + file);
      }
      epochHour = HourUtil.toEpochHour(label);
      noiseFloor = context.getConfiguration().getLong(Config.NOISE_FLOOR, Config.DEFAULT_NOISE_FLOOR);
    }

    @Override
    protected void map(LongWritable offset, Text value, Context context)
        throws IOException, InterruptedException {
      String line = value.toString();
      int last = line.lastIndexOf('\t');
      if (last <= 0) {
        return;
      }
      long views = Long.parseLong(line.substring(last + 1));
      if (views < noiseFloor) {
        context.getCounter(Counters.BELOW_NOISE_FLOOR).increment(1);
        return;
      }
      outKey.set(line.substring(0, last), epochHour);
      outVal.set(views);
      context.write(outKey, outVal);
    }
  }

  public static class SpikeReducer extends Reducer<ArticleHourKey, LongWritable, NullWritable, Text> {
    private long[] available;      // sorted epoch hours that have data
    private long[] scoreHours;     // sorted epoch hours to score
    private long[] series;         // views per available hour for the current article (reused)
    private long[] baseline;       // scratch buffer
    private int window;
    private int minHistory;
    private long minViews;
    private SpikeDetector detector;
    private final SpikeDetector.Score score = new SpikeDetector.Score();
    private MultipleOutputs<NullWritable, Text> out;
    private final Text line = new Text();

    @Override
    protected void setup(Context context) {
      Configuration conf = context.getConfiguration();
      available = parseHours(conf.get(Config.AVAILABLE_HOURS));
      scoreHours = parseHours(conf.get(Config.SCORE_HOURS));
      window = conf.getInt(Config.WINDOW_HOURS, Config.DEFAULT_WINDOW_HOURS);
      minHistory = conf.getInt(Config.MIN_HISTORY_HOURS, Config.DEFAULT_MIN_HISTORY_HOURS);
      minViews = conf.getLong(Config.MIN_VIEWS, Config.DEFAULT_MIN_VIEWS);
      detector = new SpikeDetector(minViews,
          conf.getDouble(Config.Z_THRESHOLD, Config.DEFAULT_Z_THRESHOLD),
          conf.getDouble(Config.MIN_RATIO, Config.DEFAULT_MIN_RATIO));
      series = new long[available.length];
      baseline = new long[window];
      out = new MultipleOutputs<>(context);
    }

    @Override
    protected void reduce(ArticleHourKey key, Iterable<LongWritable> values, Context context)
        throws IOException, InterruptedException {
      context.getCounter(Counters.ARTICLES_SEEN).increment(1);
      Arrays.fill(series, 0L);
      long peak = 0;
      // Secondary sort: values arrive in hour order, and Hadoop updates `key` in place while we
      // iterate, so key.getHour() is the hour of the current value.
      for (LongWritable v : values) {
        int idx = Arrays.binarySearch(available, key.getHour());
        if (idx >= 0) {
          series[idx] = v.get();
          peak = Math.max(peak, v.get());
        }
      }
      if (peak < minViews) {
        context.getCounter(Counters.ARTICLES_SKIPPED_LOW_PEAK).increment(1);
        return;   // can never be a spike: cheap early exit for the long tail
      }
      String article = key.getArticle().toString();

      for (long h : scoreHours) {
        int idx = Arrays.binarySearch(available, h);
        if (idx < 0) {
          continue;
        }
        int n = 0;
        for (int j = idx - 1; j >= 0 && available[j] >= h - window; j--) {
          baseline[n++] = series[j];
        }
        if (n < minHistory) {
          continue;
        }
        context.getCounter(Counters.HOURS_SCORED).increment(1);
        if (detector.score(series[idx], baseline, n, score)) {
          context.getCounter(Counters.SPIKES_FOUND).increment(1);
          line.set(article + '\t' + score.views + '\t' + fmt(score.mean) + '\t' + fmt(score.sigma)
              + '\t' + fmt(score.z) + '\t' + fmt(score.ratio) + '\t' + Math.round(score.excess));
          out.write(NullWritable.get(), line,
              HourUtil.PARTITION_PREFIX + HourUtil.fromEpochHour(h) + "/part");
        }
      }
    }

    @Override
    protected void cleanup(Context context) throws IOException, InterruptedException {
      out.close();
    }
  }

  static String fmt(double d) {
    return String.format(Locale.ROOT, "%.2f", d);
  }

  static long[] parseHours(String csv) {
    if (csv == null || csv.trim().isEmpty()) {
      throw new IllegalArgumentException("Missing hour list in job configuration");
    }
    String[] parts = csv.split(",");
    long[] hours = new long[parts.length];
    for (int i = 0; i < parts.length; i++) {
      hours[i] = Long.parseLong(parts[i].trim());
    }
    Arrays.sort(hours);
    return hours;
  }

  static String joinHours(long[] hours) {
    StringBuilder sb = new StringBuilder();
    for (long h : hours) {
      if (sb.length() > 0) {
        sb.append(',');
      }
      sb.append(h);
    }
    return sb.toString();
  }

  public static Job create(Configuration conf, Path[] inputs, Path output,
                           long[] availableHours, long[] scoreHours) throws IOException {
    Configuration c = new Configuration(conf);
    c.set(Config.AVAILABLE_HOURS, joinHours(availableHours));
    c.set(Config.SCORE_HOURS, joinHours(scoreHours));

    Job job = Job.getInstance(c, "WikiTrend-2-SpikeDetection");
    job.setJarByClass(SpikeDetectionJob.class);
    for (Path in : inputs) {
      FileInputFormat.addInputPath(job, in);
    }
    FileOutputFormat.setOutputPath(job, output);
    LazyOutputFormat.setOutputFormatClass(job, TextOutputFormat.class);

    job.setMapperClass(SpikeMapper.class);
    job.setReducerClass(SpikeReducer.class);
    job.setMapOutputKeyClass(ArticleHourKey.class);
    job.setMapOutputValueClass(LongWritable.class);
    job.setPartitionerClass(ArticleHourKey.ArticlePartitioner.class);
    job.setGroupingComparatorClass(ArticleHourKey.ArticleGroupingComparator.class);
    job.setOutputKeyClass(NullWritable.class);
    job.setOutputValueClass(Text.class);
    job.setNumReduceTasks(c.getInt(Config.SPIKE_REDUCERS, 4));
    return job;
  }
}
