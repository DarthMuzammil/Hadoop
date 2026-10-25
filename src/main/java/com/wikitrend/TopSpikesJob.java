package com.wikitrend;

import java.io.IOException;
import java.util.ArrayList;
import java.util.Collections;
import java.util.Comparator;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.PriorityQueue;

import org.apache.hadoop.conf.Configuration;
import org.apache.hadoop.fs.Path;
import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.NullWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.mapreduce.Job;
import org.apache.hadoop.mapreduce.Mapper;
import org.apache.hadoop.mapreduce.Partitioner;
import org.apache.hadoop.mapreduce.Reducer;
import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
import org.apache.hadoop.mapreduce.lib.input.FileSplit;
import org.apache.hadoop.mapreduce.lib.output.FileOutputFormat;
import org.apache.hadoop.mapreduce.lib.output.LazyOutputFormat;
import org.apache.hadoop.mapreduce.lib.output.MultipleOutputs;
import org.apache.hadoop.mapreduce.lib.output.TextOutputFormat;

/**
 * Job 3 - Rank the detected spikes: Top-N trending articles per hour, ordered by excess views.
 *
 * Input : job 2 partitions {@code hour=X/}.
 * Output: partitions {@code hour=X/} with lines
 *         {@code rank \t lang \t title \t views \t baseline_mean \t z_score \t ratio \t excess_views}
 *
 * Top-N pattern: every mapper keeps only its local top N per hour (in-mapper combining, emitted in
 * cleanup), so at most N records per hour per mapper are shuffled. The reducer merges them into the
 * global top N. A custom partitioner spreads consecutive hours round-robin across reducers.
 */
public final class TopSpikesJob {

  private TopSpikesJob() {}

  /** One spike record; line holds the job-2 output fields (lang .. excess). */
  static final class Spike {
    final String line;
    final long excess;

    Spike(String line) {
      this.line = line;
      this.excess = Long.parseLong(line.substring(line.lastIndexOf('\t') + 1));
    }
  }

  static final Comparator<Spike> BY_EXCESS = new Comparator<Spike>() {
    @Override
    public int compare(Spike a, Spike b) {
      int c = Long.compare(a.excess, b.excess);
      return c != 0 ? c : a.line.compareTo(b.line);
    }
  };

  /** Bounded min-heap keeping the N largest spikes. */
  static void offer(PriorityQueue<Spike> heap, Spike s, int n) {
    heap.add(s);
    if (heap.size() > n) {
      heap.poll();
    }
  }

  public static class TopMapper extends Mapper<LongWritable, Text, Text, Text> {
    private final Map<String, PriorityQueue<Spike>> perHour = new HashMap<>();
    private String hour;
    private int n;

    @Override
    protected void setup(Context context) {
      Path file = ((FileSplit) context.getInputSplit()).getPath();
      hour = HourUtil.labelFromPartitionPath(file);
      if (hour == null) {
        throw new IllegalArgumentException("Input is not inside an hour=... partition: " + file);
      }
      n = context.getConfiguration().getInt(Config.TOP_N, Config.DEFAULT_TOP_N);
    }

    @Override
    protected void map(LongWritable offset, Text value, Context context) {
      PriorityQueue<Spike> heap = perHour.get(hour);
      if (heap == null) {
        heap = new PriorityQueue<>(n + 1, BY_EXCESS);
        perHour.put(hour, heap);
      }
      offer(heap, new Spike(value.toString()), n);
    }

    @Override
    protected void cleanup(Context context) throws IOException, InterruptedException {
      Text k = new Text();
      Text v = new Text();
      for (Map.Entry<String, PriorityQueue<Spike>> e : perHour.entrySet()) {
        k.set(e.getKey());
        for (Spike s : e.getValue()) {
          v.set(s.line);
          context.write(k, v);
        }
      }
    }
  }

  /** Round-robin by hour number so a day's 24 hours spread evenly over the reducers. */
  public static class HourPartitioner extends Partitioner<Text, Text> {
    @Override
    public int getPartition(Text hour, Text value, int numPartitions) {
      return (int) (HourUtil.toEpochHour(hour.toString()) % numPartitions);
    }
  }

  public static class TopReducer extends Reducer<Text, Text, NullWritable, Text> {
    private MultipleOutputs<NullWritable, Text> out;
    private final Text line = new Text();
    private int n;

    @Override
    protected void setup(Context context) {
      out = new MultipleOutputs<>(context);
      n = context.getConfiguration().getInt(Config.TOP_N, Config.DEFAULT_TOP_N);
    }

    @Override
    protected void reduce(Text hour, Iterable<Text> values, Context context)
        throws IOException, InterruptedException {
      PriorityQueue<Spike> heap = new PriorityQueue<>(n + 1, BY_EXCESS);
      for (Text v : values) {
        offer(heap, new Spike(v.toString()), n);
      }
      List<Spike> ranked = new ArrayList<>(heap);
      Collections.sort(ranked, Collections.reverseOrder(BY_EXCESS));
      String path = HourUtil.PARTITION_PREFIX + hour + "/part";
      int rank = 1;
      for (Spike s : ranked) {
        // job-2 fields: lang title views mean sigma z ratio excess -> drop sigma for the ranking table
        String[] f = s.line.split("\t");
        line.set(rank++ + "\t" + f[0] + '\t' + f[1] + '\t' + f[2] + '\t' + f[3] + '\t' + f[5] + '\t' + f[6]
            + '\t' + f[7]);
        out.write(NullWritable.get(), line, path);
      }
    }

    @Override
    protected void cleanup(Context context) throws IOException, InterruptedException {
      out.close();
    }
  }

  public static Job create(Configuration conf, Path[] inputs, Path output) throws IOException {
    Job job = Job.getInstance(conf, "WikiTrend-3-TopSpikes");
    job.setJarByClass(TopSpikesJob.class);
    for (Path in : inputs) {
      FileInputFormat.addInputPath(job, in);
    }
    FileOutputFormat.setOutputPath(job, output);
    LazyOutputFormat.setOutputFormatClass(job, TextOutputFormat.class);

    job.setMapperClass(TopMapper.class);
    job.setReducerClass(TopReducer.class);
    job.setPartitionerClass(HourPartitioner.class);
    job.setMapOutputKeyClass(Text.class);
    job.setMapOutputValueClass(Text.class);
    job.setOutputKeyClass(NullWritable.class);
    job.setOutputValueClass(Text.class);
    job.setNumReduceTasks(conf.getInt(Config.TOP_REDUCERS, 2));
    return job;
  }
}
