package com.wikitrend;

import java.io.DataInput;
import java.io.DataOutput;
import java.io.IOException;

import org.apache.hadoop.io.LongWritable;
import org.apache.hadoop.io.Text;
import org.apache.hadoop.io.WritableComparable;
import org.apache.hadoop.io.WritableComparator;
import org.apache.hadoop.mapreduce.Partitioner;

/**
 * Composite key for the secondary sort in job 2: (article, epochHour).
 *
 * - Sort order      : article, then hour ascending  -> the reducer sees each time series in time order.
 * - Partitioner     : article only                  -> all hours of an article reach the same reducer.
 * - Grouping        : article only                  -> one reduce() call per article, covering all its hours.
 */
public class ArticleHourKey implements WritableComparable<ArticleHourKey> {

  private final Text article = new Text();   // "lang \t title"
  private long hour;                         // epoch hour

  public ArticleHourKey() {}

  public void set(String articleId, long epochHour) {
    article.set(articleId);
    hour = epochHour;
  }

  public Text getArticle() {
    return article;
  }

  public long getHour() {
    return hour;
  }

  @Override
  public void write(DataOutput out) throws IOException {
    article.write(out);
    out.writeLong(hour);
  }

  @Override
  public void readFields(DataInput in) throws IOException {
    article.readFields(in);
    hour = in.readLong();
  }

  @Override
  public int compareTo(ArticleHourKey o) {
    int c = article.compareTo(o.article);
    return c != 0 ? c : Long.compare(hour, o.hour);
  }

  @Override
  public boolean equals(Object o) {
    return o instanceof ArticleHourKey && compareTo((ArticleHourKey) o) == 0;
  }

  @Override
  public int hashCode() {
    return article.hashCode() * 31 + Long.hashCode(hour);
  }

  @Override
  public String toString() {
    return article + "@" + hour;
  }

  /** Sends every hour of an article to the same reducer. */
  public static class ArticlePartitioner extends Partitioner<ArticleHourKey, LongWritable> {
    @Override
    public int getPartition(ArticleHourKey key, LongWritable value, int numPartitions) {
      return (key.article.hashCode() & Integer.MAX_VALUE) % numPartitions;
    }
  }

  /** Groups reducer input by article only, ignoring the hour. */
  public static class ArticleGroupingComparator extends WritableComparator {
    public ArticleGroupingComparator() {
      super(ArticleHourKey.class, true);
    }

    @Override
    @SuppressWarnings("rawtypes")
    public int compare(WritableComparable a, WritableComparable b) {
      return ((ArticleHourKey) a).article.compareTo(((ArticleHourKey) b).article);
    }
  }
}
