package com.wikitrend;

/**
 * Tunable parameters. All can be overridden on the command line with Hadoop generic options,
 * e.g. {@code hadoop jar wikitrend.jar batch -D wikitrend.z.threshold=5 ...}.
 */
public final class Config {

  private Config() {}

  /** Hours of history used as the baseline for each scored hour (sliding window). */
  public static final String WINDOW_HOURS = "wikitrend.window.hours";
  public static final int DEFAULT_WINDOW_HOURS = 6;

  /** Minimum number of history hours that must be available before an hour is scored. */
  public static final String MIN_HISTORY_HOURS = "wikitrend.min.history.hours";
  public static final int DEFAULT_MIN_HISTORY_HOURS = 3;

  /** A spike must have at least this many views in the hour. */
  public static final String MIN_VIEWS = "wikitrend.min.views";
  public static final long DEFAULT_MIN_VIEWS = 1000;

  /** A spike must be at least this many standard deviations above the baseline mean. */
  public static final String Z_THRESHOLD = "wikitrend.z.threshold";
  public static final double DEFAULT_Z_THRESHOLD = 4.0;

  /** A spike must be at least this many times the baseline mean. */
  public static final String MIN_RATIO = "wikitrend.min.ratio";
  public static final double DEFAULT_MIN_RATIO = 3.0;

  /** Hourly counts below this are treated as 0 (long-tail noise); cuts shuffle volume dramatically. */
  public static final String NOISE_FLOOR = "wikitrend.noise.floor";
  public static final long DEFAULT_NOISE_FLOOR = 5;

  /** How many spikes to keep per hour in the final ranking. */
  public static final String TOP_N = "wikitrend.top.n";
  public static final int DEFAULT_TOP_N = 25;

  /** Internal: comma-separated epoch hours whose aggregated data is available to job 2. */
  public static final String AVAILABLE_HOURS = "wikitrend.available.hours";
  /** Internal: comma-separated epoch hours that job 2 must score (emit spikes for). */
  public static final String SCORE_HOURS = "wikitrend.score.hours";

  public static final String AGG_REDUCERS = "wikitrend.agg.reducers";
  public static final String SPIKE_REDUCERS = "wikitrend.spike.reducers";
  public static final String TOP_REDUCERS = "wikitrend.top.reducers";
}
