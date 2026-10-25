package com.wikitrend;

/**
 * Pure statistics for one article's hourly time series (no Hadoop types, so it is unit-testable).
 *
 * For a scored hour h with views v and the baseline B = views in the previous W available hours:
 * <pre>
 *   mean   = avg(B)
 *   sigma  = max(stddev(B), sqrt(mean + 1))   // Poisson floor: a flat 0,0,0 baseline must not give sigma = 0
 *   z      = (v - mean) / sigma
 *   ratio  = v / (mean + 1)
 *   excess = v - mean                          // "extra readers" caused by the event; used for ranking
 * </pre>
 * The hour is a spike if v >= minViews AND z >= zThreshold AND ratio >= minRatio.
 */
public final class SpikeDetector {

  private final long minViews;
  private final double zThreshold;
  private final double minRatio;

  public SpikeDetector(long minViews, double zThreshold, double minRatio) {
    this.minViews = minViews;
    this.zThreshold = zThreshold;
    this.minRatio = minRatio;
  }

  /** Result of scoring one hour. */
  public static final class Score {
    public long views;
    public double mean;
    public double sigma;
    public double z;
    public double ratio;
    public double excess;
  }

  /**
   * Scores {@code views} against {@code baseline[0..n)}. Returns true (and fills {@code out}) if it is a spike.
   */
  public boolean score(long views, long[] baseline, int n, Score out) {
    if (views < minViews || n == 0) {
      return false;
    }
    double sum = 0;
    for (int i = 0; i < n; i++) {
      sum += baseline[i];
    }
    double mean = sum / n;
    double sq = 0;
    for (int i = 0; i < n; i++) {
      double d = baseline[i] - mean;
      sq += d * d;
    }
    double std = Math.sqrt(sq / n);
    double sigma = Math.max(std, Math.sqrt(mean + 1));
    double z = (views - mean) / sigma;
    double ratio = views / (mean + 1);
    if (z < zThreshold || ratio < minRatio) {
      return false;
    }
    out.views = views;
    out.mean = mean;
    out.sigma = sigma;
    out.z = z;
    out.ratio = ratio;
    out.excess = views - mean;
    return true;
  }
}
