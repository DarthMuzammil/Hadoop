package com.wikitrend;

import java.io.IOException;

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
 * Job 1 - Clean and aggregate raw pageview logs.
 *
 * Input : raw hourly dump files (pageviews-YYYYMMDD-HH0000), one line per (project, page).
 * Output: one partition directory per hour, {@code hour=YYYY-MM-DDTHH/}, with lines
 *         {@code lang \t title \t views}  (desktop + mobile views merged).
 *
 * Key   : "hourLabel \t lang \t title"   Value: views
 * A combiner pre-sums views on the map side, so desktop+mobile rows of the same page are merged
 * before the shuffle.
 */
public final class AggregationJob {

  private AggregationJob() {}

  public static class AggMapper extends Mapper<LongWritable, Text, Text, LongWritable> {
    private final PageviewParser.Record rec = new PageviewParser.Record();
    private final Text outKey = new Text();
    private final LongWritable outVal = new LongWritable();
    private String hour;

    @Override
    protected void setup(Context context) {
      // The hour is not inside the records; it comes from the file name of the split.
      String fileName = ((FileSplit) context.getInputSplit()).getPath().getName();
      hour = HourUtil.labelFromFileName(fileName);
      if (hour == null) {
        throw new IllegalArgumentException("Unexpected input file name: " + fileName
            + " (expected pageviews-YYYYMMDD-HH0000)");
      }
    }

    @Override
    protected void map(LongWritable offset, Text line, Context context)
        throws IOException, InterruptedException {
      PageviewParser.Quality q = PageviewParser.parse(line.toString(), rec);
      context.getCounter(q).increment(1);
      if (q != PageviewParser.Quality.ACCEPTED) {
        return;
      }
      context.getCounter(Counters.VIEWS_ACCEPTED).increment(rec.views);
      outKey.set(hour + '\t' + rec.lang + '\t' + rec.title);
      outVal.set(rec.views);
      context.write(outKey, outVal);
    }
  }

  /** Combiner: same key, same hour -> sum. Output type equals input type, so it is safe to run 0..n times. */
  public static class SumCombiner extends Reducer<Text, LongWritable, Text, LongWritable> {
    private final LongWritable sum = new LongWritable();

    @Override
    protected void reduce(Text key, Iterable<LongWritable> values, Context context)
        throws IOException, InterruptedException {
      long total = 0;
      for (LongWritable v : values) {
        total += v.get();
      }
      sum.set(total);
      context.write(key, sum);
    }
  }

  /** Sums views and writes each record into its hour partition using MultipleOutputs. */
  public static class AggReducer extends Reducer<Text, LongWritable, NullWritable, Text> {
    private MultipleOutputs<NullWritable, Text> out;
    private final Text line = new Text();

    @Override
    protected void setup(Context context) {
      out = new MultipleOutputs<>(context);
    }

    @Override
    protected void reduce(Text key, Iterable<LongWritable> values, Context context)
        throws IOException, InterruptedException {
      long total = 0;
      for (LongWritable v : values) {
        total += v.get();
      }
      String k = key.toString();
      int tab = k.indexOf('\t');
      String hour = k.substring(0, tab);
      line.set(k.substring(tab + 1) + '\t' + total);
      context.getCounter(Counters.ARTICLE_HOURS).increment(1);
      out.write(NullWritable.get(), line, HourUtil.PARTITION_PREFIX + hour + "/part");
    }

    @Override
    protected void cleanup(Context context) throws IOException, InterruptedException {
      out.close();
    }
  }

  public enum Counters { VIEWS_ACCEPTED, ARTICLE_HOURS }

  public static Job create(Configuration conf, Path[] inputs, Path output) throws IOException {
    Job job = Job.getInstance(conf, "WikiTrend-1-Aggregate");
    job.setJarByClass(AggregationJob.class);

    for (Path in : inputs) {
      FileInputFormat.addInputPath(job, in);
    }
    FileOutputFormat.setOutputPath(job, output);
    // Only create part files that MultipleOutputs actually writes to (no empty part-r-* files).
    LazyOutputFormat.setOutputFormatClass(job, TextOutputFormat.class);

    job.setMapperClass(AggMapper.class);
    job.setCombinerClass(SumCombiner.class);
    job.setReducerClass(AggReducer.class);
    job.setMapOutputKeyClass(Text.class);
    job.setMapOutputValueClass(LongWritable.class);
    job.setOutputKeyClass(NullWritable.class);
    job.setOutputValueClass(Text.class);
    job.setNumReduceTasks(conf.getInt(Config.AGG_REDUCERS, 4));
    return job;
  }
}
